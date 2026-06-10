"""
Composite teacher risk scoring (no telecom data required).
Combines enrollment, outcome, infrastructure and CAG signals.
"""
import logging
from typing import Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

WEIGHTS = {
    "enrollment_anomaly_score": 0.30,
    "outcome_anomaly_score": 0.30,
    "infrastructure_score_inverted": 0.20,
    "historical_cag_flag": 0.20,
}


def compute_teacher_risk(school_row: Dict[str, Any]) -> float:
    """
    Compute composite teacher risk score (0-1).

    Inputs from school_row:
        enrollment_anomaly_score  (float 0-1)
        outcome_anomaly_score     (float 0-1)
        infrastructure_score      (float 0-1, higher = better infra)
        historical_cag_flag       (bool/int: 1 if CAG found a finding)

    Returns risk_score (float 0-1, 1 = highest risk).
    """
    enrollment_score = float(school_row.get("enrollment_anomaly_score", 0.0))
    outcome_score = float(school_row.get("outcome_anomaly_score", 0.0))
    infra = float(school_row.get("infrastructure_score", 0.5))
    cag_flag = float(school_row.get("historical_cag_flag", 0))

    infra_inverted = 1.0 - infra  # Low infra → higher risk

    raw_score = (
        enrollment_score * WEIGHTS["enrollment_anomaly_score"]
        + outcome_score * WEIGHTS["outcome_anomaly_score"]
        + infra_inverted * WEIGHTS["infrastructure_score_inverted"]
        + cag_flag * WEIGHTS["historical_cag_flag"]
    )

    return round(float(np.clip(raw_score, 0.0, 1.0)), 3)


def batch_score(schools_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute teacher risk scores for all schools in DataFrame.
    Returns schools_df with added column: teacher_risk_score
    """
    required_cols = {
        "enrollment_anomaly_score": 0.0,
        "outcome_anomaly_score": 0.0,
        "infrastructure_score": 0.5,
        "historical_cag_flag": 0,
    }
    for col, default in required_cols.items():
        if col not in schools_df.columns:
            schools_df[col] = default

    schools_df["teacher_risk_score"] = schools_df.apply(
        lambda row: compute_teacher_risk(row.to_dict()), axis=1
    )

    # Categorise
    def _categorise(score: float) -> str:
        if score >= 0.7:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    schools_df["teacher_risk_category"] = schools_df["teacher_risk_score"].apply(_categorise)
    logger.info(
        f"Scored {len(schools_df)} schools — "
        f"high risk: {(schools_df['teacher_risk_score'] >= 0.7).sum()}"
    )
    return schools_df
