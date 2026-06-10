"""
XGBoost model predicting expected board exam pass rates.
Flags schools where reported pass rate far exceeds model prediction.
"""
import os
import logging
import joblib
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

MODEL_PATH = os.getenv("OUTCOME_MODEL_PATH", "/tmp/outcome_model.joblib")
ANOMALY_STD_THRESHOLD = 2.0

FEATURE_COLS = [
    "infrastructure_score",
    "teacher_student_ratio",
    "per_child_spend",
    "district_poverty_index",
    "historical_pass_rate_3yr",
]


def _build_synthetic_training_data(n: int = 5000) -> pd.DataFrame:
    """
    Generate synthetic training data for initial model bootstrap.
    In production this is replaced by actual UDISE + board results data.
    """
    rng = np.random.default_rng(42)
    infra = rng.uniform(0.2, 1.0, n)
    tsr = rng.uniform(15, 60, n)  # teacher-student ratio
    spend = rng.uniform(3000, 25000, n)  # INR per child per year
    poverty = rng.uniform(0.1, 0.9, n)  # 0=rich, 1=poor
    hist = rng.uniform(0.3, 0.95, n)

    # Realistic pass rate formula
    base = (
        infra * 0.25
        + (1 / (1 + tsr / 30)) * 0.20
        + np.log1p(spend / 5000) / 5 * 0.20
        + (1 - poverty) * 0.15
        + hist * 0.20
    )
    noise = rng.normal(0, 0.04, n)
    pass_rate = np.clip(base + noise, 0.1, 0.99)

    return pd.DataFrame(
        {
            "infrastructure_score": infra,
            "teacher_student_ratio": tsr,
            "per_child_spend": spend,
            "district_poverty_index": poverty,
            "historical_pass_rate_3yr": hist,
            "pass_rate": pass_rate,
        }
    )


def train(df: Optional[pd.DataFrame] = None) -> Any:
    """
    Train XGBoost model on school features.
    If df is None, uses synthetic training data.
    Saves model to MODEL_PATH.
    """
    try:
        from xgboost import XGBRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error
    except ImportError:
        logger.error("XGBoost not available — using fallback linear model")
        return _train_fallback()

    if df is None:
        df = _build_synthetic_training_data()

    df = df.dropna(subset=FEATURE_COLS + ["pass_rate"])
    X = df[FEATURE_COLS]
    y = df["pass_rate"]

    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.15, random_state=42)

    model = XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric="mae",
    )
    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    val_pred = model.predict(X_val)
    mae = mean_absolute_error(y_val, val_pred)
    logger.info(f"Outcome model trained — MAE: {mae:.4f}")

    joblib.dump(model, MODEL_PATH)
    return model


def _train_fallback():
    """Lightweight linear fallback when XGBoost unavailable."""
    from sklearn.linear_model import Ridge
    df = _build_synthetic_training_data()
    model = Ridge()
    model.fit(df[FEATURE_COLS], df["pass_rate"])
    joblib.dump(model, MODEL_PATH)
    return model


def _load_model():
    """Load trained model, training if necessary."""
    if os.path.exists(MODEL_PATH):
        try:
            return joblib.load(MODEL_PATH)
        except Exception:
            pass
    return train()


_model = None


def predict_expected_rate(school_features: Dict[str, float]) -> float:
    """
    Predict expected pass rate for a school given its features.
    Returns float 0-1.
    """
    global _model
    if _model is None:
        _model = _load_model()

    row = pd.DataFrame(
        [
            {
                "infrastructure_score": school_features.get("infrastructure_score", 0.5),
                "teacher_student_ratio": school_features.get("teacher_student_ratio", 30),
                "per_child_spend": school_features.get("per_child_spend", 8000),
                "district_poverty_index": school_features.get("district_poverty_index", 0.5),
                "historical_pass_rate_3yr": school_features.get("historical_pass_rate_3yr", 0.6),
            }
        ]
    )

    prediction = float(_model.predict(row)[0])
    return float(np.clip(prediction, 0.05, 0.99))


def flag_outcome_anomalies(
    schools_df: pd.DataFrame,
    results_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compare predicted vs reported pass rates; flag outliers.

    Merges schools_df (with feature columns) with results_df (with reported_pass_rate).
    Flags schools where reported > predicted + 2 * district_std.

    Returns enriched DataFrame with:
        predicted_pass_rate, outcome_anomaly_score, outcome_flagged, outcome_flag_reason
    """
    global _model
    if _model is None:
        _model = _load_model()

    merged = schools_df.merge(
        results_df[["udise_code", "reported_pass_rate", "year"]],
        on="udise_code",
        how="left",
    )

    for col in FEATURE_COLS:
        if col not in merged.columns:
            merged[col] = merged.get(col, 0.5)

    # Fill defaults
    merged["infrastructure_score"] = merged.get("infrastructure_score", 0.5).fillna(0.5)
    merged["teacher_student_ratio"] = merged.get("teacher_student_ratio", 30).fillna(30)
    merged["per_child_spend"] = merged.get("per_child_spend", 8000).fillna(8000)
    merged["district_poverty_index"] = merged.get("district_poverty_index", 0.5).fillna(0.5)
    merged["historical_pass_rate_3yr"] = merged.get("historical_pass_rate_3yr", 0.6).fillna(0.6)

    X = merged[FEATURE_COLS].fillna(0.5)
    merged["predicted_pass_rate"] = np.clip(_model.predict(X), 0.05, 0.99)

    # Compute district-level std of residuals
    merged["residual"] = merged["reported_pass_rate"] - merged["predicted_pass_rate"]
    district_std = merged.groupby("district_code")["residual"].std().fillna(0.1).rename("district_std")
    merged = merged.join(district_std, on="district_code")

    def _score(row):
        reported = row.get("reported_pass_rate", np.nan)
        predicted = row.get("predicted_pass_rate", 0.6)
        std = max(float(row.get("district_std", 0.1)), 0.01)
        if pd.isna(reported):
            return pd.Series({"outcome_anomaly_score": 0.0, "outcome_flagged": False, "outcome_flag_reason": "no_data"})
        z = (reported - predicted) / std
        score = min(1.0, max(0.0, (z - ANOMALY_STD_THRESHOLD) / 3.0)) if z > 0 else 0.0
        flagged = z > ANOMALY_STD_THRESHOLD
        reason = f"reported={reported:.2f} predicted={predicted:.2f} z={z:.1f}" if flagged else ""
        return pd.Series({"outcome_anomaly_score": round(score, 3), "outcome_flagged": flagged, "outcome_flag_reason": reason})

    flags = merged.apply(_score, axis=1)
    return pd.concat([merged, flags], axis=1)
