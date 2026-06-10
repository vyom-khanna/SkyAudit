"""
ASER district-level learning outcomes loader (2006-2023).
Computes trend slope (improving/declining) per district.
"""
import logging
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

ASER_COLS = {
    "district": ["district", "district_name", "dist"],
    "year": ["year", "survey_year"],
    "pct_can_read_std2": ["std2_read", "pct_read_std2", "read_level_2", "std_ii_read"],
    "pct_can_do_division": ["division", "pct_division", "arithmetic_division"],
}


def load_aser(file_path: str) -> pd.DataFrame:
    """
    Load ASER district CSV for all available years.

    Returns DataFrame with district, year, pct_can_read_std2,
    pct_can_do_division, trend_slope, trend_direction.
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"ASER file not found: {file_path} — using synthetic data")
        return _generate_synthetic_aser()

    df = pd.read_csv(file_path, dtype=str)
    df = _standardise_columns(df)

    for col in ["pct_can_read_std2", "pct_can_do_division"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["year"] = pd.to_numeric(df.get("year", 2022), errors="coerce").fillna(2022).astype(int)

    df = _compute_trends(df)
    return df


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    col_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    rename = {}
    for std, variants in ASER_COLS.items():
        for v in variants:
            if v in col_lower:
                rename[col_lower[v]] = std
                break
    return df.rename(columns=rename)


def _compute_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Compute linear trend slope for each district across years."""
    results = []
    for district, group in df.groupby("district"):
        group = group.sort_values("year")
        years = group["year"].values
        reads = group["pct_can_read_std2"].dropna().values

        slope = 0.0
        if len(reads) >= 2 and len(years) >= 2:
            try:
                slope = float(np.polyfit(years[-len(reads):], reads, 1)[0])
            except Exception:
                slope = 0.0

        direction = "improving" if slope > 0.5 else ("declining" if slope < -0.5 else "stable")

        for _, row in group.iterrows():
            r = row.to_dict()
            r["trend_slope"] = round(slope, 3)
            r["trend_direction"] = direction
            results.append(r)

    return pd.DataFrame(results)


def _generate_synthetic_aser() -> pd.DataFrame:
    """Generate realistic synthetic ASER data for UP districts."""
    import random
    rng = random.Random(42)
    years = list(range(2006, 2024, 2))
    districts = [
        "Sitapur", "Lucknow", "Kanpur Nagar", "Agra", "Varanasi",
        "Allahabad", "Gorakhpur", "Bareilly", "Moradabad", "Aligarh",
        "Firozabad", "Meerut", "Ghaziabad", "Mathura", "Bijnor",
    ]
    records = []
    for dist in districts:
        base_read = rng.uniform(20, 55)
        base_div = rng.uniform(10, 35)
        trend = rng.uniform(-0.5, 1.5)

        for i, yr in enumerate(years):
            noise_r = rng.gauss(0, 2)
            noise_d = rng.gauss(0, 1.5)
            records.append({
                "district": dist,
                "year": yr,
                "pct_can_read_std2": round(max(5, min(95, base_read + trend * i + noise_r)), 1),
                "pct_can_do_division": round(max(2, min(80, base_div + trend * 0.6 * i + noise_d)), 1),
                "trend_slope": round(trend, 3),
                "trend_direction": "improving" if trend > 0.5 else ("declining" if trend < -0.5 else "stable"),
            })

    return pd.DataFrame(records)


def get_district_aser(district_name: str, df: pd.DataFrame, year: int = 2022) -> Optional[Dict]:
    """Retrieve latest ASER data for a district."""
    matches = df[df["district"].str.lower().str.contains(district_name.lower(), na=False)]
    if matches.empty:
        return None
    latest = matches[matches["year"] <= year].sort_values("year").iloc[-1]
    return latest.to_dict()
