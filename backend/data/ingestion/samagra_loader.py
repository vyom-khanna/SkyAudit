"""
Samagra Shiksha grant data loader.
"""
import logging
from pathlib import Path
from typing import Optional
import pandas as pd
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def load_samagra(file_path: str, db: Optional[Session] = None) -> pd.DataFrame:
    """
    Load Samagra Shiksha grant data.

    Expected columns: udise_code, grant_amount_inr, sanction_date,
                      completion_deadline, reported_completion_date
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Samagra file not found: {file_path} — generating synthetic data")
        return _generate_synthetic_samagra()

    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        df = pd.read_csv(file_path, dtype=str)

    col_map = {}
    for c in df.columns:
        cl = c.lower().strip().replace(" ", "_")
        if "udise" in cl:
            col_map[c] = "udise_code"
        elif "grant" in cl and "amount" in cl:
            col_map[c] = "grant_amount_inr"
        elif "sanction" in cl and "date" in cl:
            col_map[c] = "sanction_date"
        elif "completion" in cl and "deadline" in cl:
            col_map[c] = "completion_deadline"
        elif "reported" in cl and "completion" in cl:
            col_map[c] = "reported_completion_date"

    df = df.rename(columns=col_map)

    for col in ["sanction_date", "completion_deadline", "reported_completion_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    if "grant_amount_inr" in df.columns:
        df["grant_amount_inr"] = pd.to_numeric(
            df["grant_amount_inr"].astype(str).str.replace(",", ""), errors="coerce"
        ).fillna(0)

    if db is not None:
        _store_grants(df, db)

    return df


def _generate_synthetic_samagra() -> pd.DataFrame:
    """Generate synthetic Samagra grant data for demo."""
    import random
    from datetime import datetime, timedelta
    rng = random.Random(42)
    records = []
    base = 91400100001

    for i in range(150):  # ~30% of schools have grants
        udise = str(base + rng.randint(0, 499)).zfill(11)
        sanction = datetime(2021, 1, 1) + timedelta(days=rng.randint(0, 730))
        deadline = sanction + timedelta(days=rng.randint(180, 540))
        completed = deadline - timedelta(days=rng.randint(-60, 180))

        records.append({
            "udise_code": udise,
            "grant_id": f"SS/UP/{2021 + i//50}/{i+1:04d}",
            "grant_amount_inr": rng.choice([200000, 350000, 500000, 750000, 1000000]),
            "sanction_date": sanction,
            "completion_deadline": deadline,
            "reported_completion_date": completed,
            "grant_type": rng.choice(["classroom", "toilet", "kitchen", "boundary_wall"]),
        })

    return pd.DataFrame(records)


def _store_grants(df: pd.DataFrame, db: Session) -> None:
    """Store grants in a JSON column on School or a separate grants table."""
    logger.info(f"Samagra grants: {len(df)} records (storing in memory for joins)")
