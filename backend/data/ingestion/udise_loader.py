"""
UDISE+ Excel/CSV loader with coordinate validation and upsert logic.
"""
import re
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# India bounding box
LAT_MIN, LAT_MAX = 8.4, 37.6
LNG_MIN, LNG_MAX = 68.7, 97.25

HINDI_COLUMN_ALIASES = {
    "udise_code": ["udise code", "udise_code", "school code", "विद्यालय कोड"],
    "name": ["school name", "name", "विद्यालय का नाम", "school_name"],
    "district_code": ["district code", "dist_code", "district_id", "जिला कोड"],
    "block": ["block", "block name", "ब्लॉक"],
    "latitude": ["latitude", "lat", "अक्षांश"],
    "longitude": ["longitude", "lon", "lng", "देशांतर"],
    "reported_enrollment": ["total enrolment", "enrollment", "enrolment", "नामांकन"],
    "reported_teachers": ["total teachers", "teachers", "शिक्षक"],
    "reported_building_exists": ["building available", "pucca building", "भवन"],
    "reported_kitchen_exists": ["kitchen available", "kitchen shed", "रसोई"],
    "reported_meals_daily": ["mdm meals", "meals per day", "भोजन"],
    "management_type": ["management", "school management", "प्रबंधन"],
}


def _normalise_column(col: str) -> str:
    return re.sub(r"\s+", " ", col.lower().strip())


def _map_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map UDISE column names (including Hindi variants) to standardised names."""
    col_map = {}
    normalised = {_normalise_column(c): c for c in df.columns}

    for standard, aliases in HINDI_COLUMN_ALIASES.items():
        for alias in aliases:
            if _normalise_column(alias) in normalised:
                col_map[normalised[_normalise_column(alias)]] = standard
                break

    return df.rename(columns=col_map)


def _validate_coords(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows with invalid or missing coordinates."""
    df["lat_valid"] = (
        df["latitude"].notna()
        & df["latitude"].between(LAT_MIN, LAT_MAX)
    )
    df["lng_valid"] = (
        df["longitude"].notna()
        & df["longitude"].between(LNG_MIN, LNG_MAX)
    )
    df["coords_valid"] = df["lat_valid"] & df["lng_valid"]

    # Flag zero coordinates (often default placeholders)
    df["coords_valid"] = df["coords_valid"] & (df["latitude"] != 0) & (df["longitude"] != 0)
    return df


def load_udise(
    file_path: str,
    district_code: Optional[str] = None,
    db: Optional[Session] = None,
) -> dict:
    """
    Load UDISE+ Excel or CSV into the schools table.

    Args:
        file_path: path to UDISE+ Excel or CSV file
        district_code: filter to this district only (if None, load all)
        db: SQLAlchemy session (if None, returns DataFrame without persisting)

    Returns stats dict.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"UDISE file not found: {file_path}")

    logger.info(f"Loading UDISE data from {file_path}")

    if path.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(file_path, dtype=str)
    elif path.suffix.lower() == ".csv":
        # Try UTF-8, then latin-1 for Hindi characters
        try:
            df = pd.read_csv(file_path, dtype=str, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, dtype=str, encoding="latin-1")
    else:
        raise ValueError(f"Unsupported file format: {path.suffix}")

    logger.info(f"Raw rows: {len(df)}, columns: {list(df.columns)}")

    df = _map_columns(df)

    # Filter to district
    if district_code and "district_code" in df.columns:
        df = df[df["district_code"].astype(str).str.strip() == str(district_code)]
        logger.info(f"After district filter ({district_code}): {len(df)} rows")

    # Convert numeric columns
    for col in ["latitude", "longitude", "reported_enrollment", "reported_teachers",
                "reported_meals_daily"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Convert boolean columns
    for col in ["reported_building_exists", "reported_kitchen_exists"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.lower().isin(
                ["yes", "1", "true", "available", "हाँ"]
            )

    # Normalise management type
    if "management_type" in df.columns:
        df["management_type"] = df["management_type"].astype(str).str.lower().str.strip()
        df["management_type"] = df["management_type"].replace(
            {"govt": "government", "state govt": "government", "pvt": "private"}
        )
        df.loc[~df["management_type"].isin(["government", "private", "aided"]), "management_type"] = "government"

    df = _validate_coords(df)

    # Statistics
    total = len(df)
    invalid_coords = (~df["coords_valid"]).sum()
    duplicates = df.duplicated(subset=["udise_code"], keep="first").sum()

    logger.warning(f"Invalid coordinates: {invalid_coords} rows")
    logger.warning(f"Duplicate UDISE codes: {duplicates} rows")

    df = df.drop_duplicates(subset=["udise_code"], keep="first")

    if db is not None:
        _upsert_schools(df, db)

    stats = {
        "total_loaded": total,
        "after_dedup": len(df),
        "invalid_coords": int(invalid_coords),
        "duplicates": int(duplicates),
        "district_code": district_code,
    }
    logger.info(f"UDISE load complete: {stats}")
    return stats


def _upsert_schools(df: pd.DataFrame, db: Session) -> None:
    """Insert or update school records using SQLAlchemy."""
    from app.models import School
    from datetime import datetime
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point

    inserted = 0
    updated = 0

    for _, row in df.iterrows():
        udise_code = str(row.get("udise_code", "")).strip()
        if not udise_code or len(udise_code) < 8:
            continue

        existing = db.query(School).filter(School.udise_code == udise_code).first()

        lat = row.get("latitude")
        lng = row.get("longitude")
        geom = None
        if pd.notna(lat) and pd.notna(lng) and row.get("coords_valid", False):
            try:
                geom = from_shape(Point(float(lng), float(lat)), srid=4326)
            except Exception:
                pass

        if existing:
            existing.name = str(row.get("name", existing.name))
            existing.block = str(row.get("block", existing.block or ""))
            existing.reported_enrollment = int(row.get("reported_enrollment") or 0)
            existing.reported_teachers = int(row.get("reported_teachers") or 0)
            existing.reported_building_exists = bool(row.get("reported_building_exists", False))
            existing.reported_kitchen_exists = bool(row.get("reported_kitchen_exists", False))
            existing.reported_meals_daily = int(row.get("reported_meals_daily") or 0)
            if geom:
                existing.latitude = float(lat)
                existing.longitude = float(lng)
                existing.geom = geom
            updated += 1
        else:
            school = School(
                udise_code=udise_code,
                name=str(row.get("name", "Unknown School")),
                district_code=str(row.get("district_code", "")),
                block=str(row.get("block", "")),
                latitude=float(lat) if pd.notna(lat) else None,
                longitude=float(lng) if pd.notna(lng) else None,
                reported_enrollment=int(row.get("reported_enrollment") or 0),
                reported_teachers=int(row.get("reported_teachers") or 0),
                reported_building_exists=bool(row.get("reported_building_exists", False)),
                reported_kitchen_exists=bool(row.get("reported_kitchen_exists", False)),
                reported_meals_daily=int(row.get("reported_meals_daily") or 0),
                management_type=row.get("management_type", "government"),
                geom=geom,
            )
            db.add(school)
            inserted += 1

        if (inserted + updated) % 500 == 0:
            db.commit()
            logger.info(f"Committed {inserted + updated} schools...")

    db.commit()
    logger.info(f"UDISE upsert complete: {inserted} inserted, {updated} updated")
