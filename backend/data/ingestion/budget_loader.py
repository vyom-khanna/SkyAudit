"""
Open Budgets India education expenditure loader.
Computes per-child spend and district efficiency scores.
"""
import logging
from pathlib import Path
from typing import Optional, Dict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def load_budget(file_path: str, enrollment_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Load Open Budgets India education expenditure CSV.

    Args:
        file_path: path to OBI education expenditure CSV
        enrollment_df: optional DataFrame with district verified_enrollment

    Returns:
        DataFrame with district_code, total_budget_inr, verified_enrollment,
        per_child_spend, efficiency_score
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Budget file not found: {file_path} — generating synthetic data")
        return _generate_synthetic_budget(enrollment_df)

    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        df = pd.read_csv(file_path, dtype=str)

    df = _standardise_columns(df)
    df = _compute_per_child(df, enrollment_df)
    df = _compute_efficiency(df)

    return df


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_map = {}
    for c in df.columns:
        cl = c.lower().strip().replace(" ", "_")
        if "district_code" in cl or "dist_code" in cl:
            col_map[c] = "district_code"
        elif "district" in cl and "name" in cl:
            col_map[c] = "district_name"
        elif "expenditure" in cl or "budget" in cl or "spend" in cl:
            col_map[c] = "total_budget_inr"
        elif "year" in cl:
            col_map[c] = "year"
    df = df.rename(columns=col_map)

    if "total_budget_inr" in df.columns:
        df["total_budget_inr"] = pd.to_numeric(
            df["total_budget_inr"].astype(str).str.replace(",", ""),
            errors="coerce"
        ).fillna(0)

    return df


def _compute_per_child(df: pd.DataFrame, enrollment_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if enrollment_df is not None and "district_code" in df.columns:
        df = df.merge(
            enrollment_df[["district_code", "verified_enrollment"]],
            on="district_code",
            how="left",
        )
    else:
        df["verified_enrollment"] = 5000  # default

    df["verified_enrollment"] = df["verified_enrollment"].fillna(5000).astype(int)
    df["per_child_spend"] = (
        df["total_budget_inr"] / df["verified_enrollment"].replace(0, 1)
    ).round(2)

    return df


def _compute_efficiency(df: pd.DataFrame) -> pd.DataFrame:
    """Compute efficiency score and rank districts."""
    if "per_child_spend" not in df.columns:
        df["efficiency_score"] = 0.5
        df["efficiency_rank"] = 0
        return df

    # Efficiency quartiles
    p25 = df["per_child_spend"].quantile(0.25)
    p75 = df["per_child_spend"].quantile(0.75)
    median = df["per_child_spend"].median()

    df["spend_quartile"] = pd.cut(
        df["per_child_spend"],
        bins=[0, p25, median, p75, float("inf")],
        labels=["Q1_low", "Q2", "Q3", "Q4_high"],
    )

    # Normalise spend into 0-1 (higher spend = lower score if outcomes unchanged)
    max_spend = df["per_child_spend"].max()
    min_spend = df["per_child_spend"].min()
    if max_spend > min_spend:
        df["efficiency_score"] = 1 - (
            (df["per_child_spend"] - min_spend) / (max_spend - min_spend)
        )
    else:
        df["efficiency_score"] = 0.5

    df["efficiency_rank"] = df["efficiency_score"].rank(ascending=False).astype(int)
    df["national_percentile"] = (
        df["efficiency_score"].rank(pct=True) * 100
    ).round(1)

    return df


def _generate_synthetic_budget(enrollment_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    """Generate synthetic budget data for UP districts."""
    import random
    rng = random.Random(42)

    up_district_codes = [f"0{9000 + i}" for i in range(1, 76)]

    records = []
    for code in up_district_codes:
        enrollment = rng.randint(15000, 80000)
        per_child = rng.uniform(4000, 22000)
        total_budget = enrollment * per_child

        verified_enrollment = enrollment
        if enrollment_df is not None:
            row = enrollment_df[enrollment_df["district_code"] == code]
            if not row.empty:
                verified_enrollment = int(row.iloc[0].get("verified_enrollment", enrollment))

        records.append({
            "district_code": code,
            "total_budget_inr": round(total_budget, 0),
            "verified_enrollment": verified_enrollment,
            "per_child_spend": round(per_child, 2),
            "year": 2023,
            "source": "synthetic",
        })

    df = pd.DataFrame(records)
    return _compute_efficiency(df)


def get_district_budget(district_code: str, budget_df: pd.DataFrame) -> Dict:
    """Retrieve budget info for a specific district."""
    row = budget_df[budget_df["district_code"] == district_code]
    if row.empty:
        return {
            "district_code": district_code,
            "total_budget_inr": 50_000_000,
            "verified_enrollment": 5000,
            "per_child_spend": 10_000,
            "efficiency_score": 0.5,
        }
    return row.iloc[0].to_dict()
