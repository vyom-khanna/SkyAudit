"""
Census 2011 C-13 table loader with CAGR projection to current year.
Produces district_code → estimated_school_age_population mapping.
"""
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

CENSUS_YEAR = 2011
ANNUAL_GROWTH_RATE = 0.012  # 1.2% CAGR
SCHOOL_AGE_MIN = 6
SCHOOL_AGE_MAX = 14


def load_census(file_path: str, output_path: Optional[str] = None) -> pd.DataFrame:
    """
    Load Census 2011 C-13 age group table and project to current year.

    Args:
        file_path: path to Census C-13 CSV/Excel
        output_path: optional path to save enriched CSV

    Returns:
        DataFrame with district_code, district_name, school_age_population_2011,
        school_age_population_projected columns
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning(f"Census file not found: {file_path} — generating synthetic data")
        return _generate_synthetic_census()

    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    else:
        df = pd.read_csv(file_path, dtype=str)

    logger.info(f"Census raw rows: {len(df)}, columns: {list(df.columns)}")

    df = _normalise_census_columns(df)
    df = _extract_school_age_population(df)
    df = _project_to_current_year(df)

    if output_path:
        df.to_csv(output_path, index=False)
        logger.info(f"Projected census saved to {output_path}")

    return df


def _normalise_census_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map Census C-13 column names to standardised names."""
    col_lower = {c.lower().strip().replace(" ", "_"): c for c in df.columns}

    rename_map = {}
    for std, variants in {
        "district_code": ["district_code", "dist_code", "location_code", "area_code"],
        "district_name": ["district_name", "district", "area_name", "name"],
        "state_code": ["state_code", "state_no"],
        "total_population": ["total_persons", "total", "persons"],
        "age_6": ["age_6", "6_years", "age_group_6"],
        "age_7": ["age_7", "7_years"],
        "age_8": ["age_8", "8_years"],
        "age_9": ["age_9", "9_years"],
        "age_10": ["age_10", "10_years"],
        "age_11": ["age_11", "11_years"],
        "age_12": ["age_12", "12_years"],
        "age_13": ["age_13", "13_years"],
        "age_14": ["age_14", "14_years"],
    }.items():
        for v in variants:
            if v in col_lower:
                rename_map[col_lower[v]] = std
                break

    return df.rename(columns=rename_map)


def _extract_school_age_population(df: pd.DataFrame) -> pd.DataFrame:
    """Sum age 6-14 columns into school_age_population_2011."""
    age_cols = [f"age_{i}" for i in range(SCHOOL_AGE_MIN, SCHOOL_AGE_MAX + 1)]
    available_age_cols = [c for c in age_cols if c in df.columns]

    if available_age_cols:
        for col in available_age_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df["school_age_population_2011"] = df[available_age_cols].sum(axis=1)
    elif "total_population" in df.columns:
        # Fallback: estimate ~18% of population is 6-14
        df["total_population"] = pd.to_numeric(df["total_population"], errors="coerce").fillna(0)
        df["school_age_population_2011"] = (df["total_population"] * 0.18).astype(int)
        logger.warning("Age-group columns not found — estimating 18% of total population")
    else:
        df["school_age_population_2011"] = 0
        logger.error("Cannot extract school-age population — no usable columns")

    return df


def _project_to_current_year(df: pd.DataFrame) -> pd.DataFrame:
    """Apply CAGR to project 2011 population to current year."""
    current_year = datetime.utcnow().year
    years_elapsed = current_year - CENSUS_YEAR
    growth_factor = (1 + ANNUAL_GROWTH_RATE) ** years_elapsed

    df["projection_year"] = current_year
    df["growth_factor"] = round(growth_factor, 4)
    df["school_age_population_projected"] = (
        df["school_age_population_2011"] * growth_factor
    ).astype(int)

    logger.info(
        f"Projected {CENSUS_YEAR} → {current_year} "
        f"({years_elapsed} years, factor {growth_factor:.3f})"
    )
    return df


def _generate_synthetic_census() -> pd.DataFrame:
    """Generate realistic synthetic census data for UP districts."""
    import random
    rng = random.Random(42)

    up_districts = [
        ("09001", "Agra"), ("09002", "Aligarh"), ("09003", "Allahabad"),
        ("09004", "Ambedkar Nagar"), ("09005", "Amethi"), ("09006", "Amroha"),
        ("09007", "Auraiya"), ("09008", "Azamgarh"), ("09009", "Baghpat"),
        ("09010", "Bahraich"), ("09011", "Ballia"), ("09012", "Balrampur"),
        ("09013", "Banda"), ("09014", "Barabanki"), ("09015", "Bareilly"),
        ("09016", "Basti"), ("09017", "Bijnor"), ("09018", "Budaun"),
        ("09019", "Bulandshahr"), ("09020", "Chandauli"), ("09021", "Chitrakoot"),
        ("09022", "Deoria"), ("09023", "Etah"), ("09024", "Etawah"),
        ("09025", "Faizabad"), ("09026", "Farrukhabad"), ("09027", "Fatehpur"),
        ("09028", "Firozabad"), ("09029", "Gautam Buddha Nagar"), ("09030", "Ghaziabad"),
        ("09031", "Ghazipur"), ("09032", "Gonda"), ("09033", "Gorakhpur"),
        ("09034", "Hamirpur"), ("09035", "Hapur"), ("09036", "Hardoi"),
        ("09037", "Hathras"), ("09038", "Jalaun"), ("09039", "Jaunpur"),
        ("09040", "Jhansi"), ("09041", "Kannauj"), ("09042", "Kanpur Dehat"),
        ("09043", "Kanpur Nagar"), ("09044", "Kasganj"), ("09045", "Kaushambi"),
        ("09046", "Kheri"), ("09047", "Kushinagar"), ("09048", "Lalitpur"),
        ("09049", "Lucknow"), ("09050", "Maharajganj"), ("09051", "Mahoba"),
        ("09052", "Mainpuri"), ("09053", "Mathura"), ("09054", "Mau"),
        ("09055", "Meerut"), ("09056", "Mirzapur"), ("09057", "Moradabad"),
        ("09058", "Muzaffarnagar"), ("09059", "Pilibhit"), ("09060", "Pratapgarh"),
        ("09061", "Raebareli"), ("09062", "Rampur"), ("09063", "Saharanpur"),
        ("09064", "Sambhal"), ("09065", "Sant Kabir Nagar"), ("09066", "Sant Ravidas Nagar"),
        ("09067", "Shahjahanpur"), ("09068", "Shamli"), ("09069", "Shrawasti"),
        ("09070", "Siddharthnagar"), ("09071", "Sitapur"), ("09072", "Sonbhadra"),
        ("09073", "Sultanpur"), ("09074", "Unnao"), ("09075", "Varanasi"),
    ]

    current_year = datetime.utcnow().year
    years_elapsed = current_year - CENSUS_YEAR
    growth_factor = (1 + ANNUAL_GROWTH_RATE) ** years_elapsed

    records = []
    for code, name in up_districts:
        pop_2011 = rng.randint(80_000, 350_000)
        projected = int(pop_2011 * growth_factor)
        records.append({
            "district_code": code,
            "district_name": name,
            "state_code": "09",
            "state_name": "Uttar Pradesh",
            "school_age_population_2011": pop_2011,
            "school_age_population_projected": projected,
            "projection_year": current_year,
            "growth_factor": round(growth_factor, 4),
        })

    return pd.DataFrame(records)


def get_district_ceiling(district_code: str, census_df: pd.DataFrame) -> Optional[int]:
    """Quick helper to get projected school-age population for a district."""
    row = census_df[census_df["district_code"] == district_code]
    if row.empty:
        return None
    return int(row.iloc[0]["school_age_population_projected"])
