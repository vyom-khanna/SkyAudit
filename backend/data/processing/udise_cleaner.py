"""
UDISE data cleaning pipeline.
Handles encoding issues, coordinate validation, and deduplication.
"""
import re
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

LAT_MIN, LAT_MAX = 8.4, 37.6
LNG_MIN, LNG_MAX = 68.7, 97.25


def clean_udise_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, dict]:
    """
    Full cleaning pipeline for a raw UDISE DataFrame.

    Returns:
        (cleaned_df, stats_dict)
    """
    original_count = len(df)
    stats = {'original_rows': original_count}

    # ── Step 1: Fix encoding issues in string columns ─────────────────────
    df = _fix_encoding(df)

    # ── Step 2: Standardise column names ──────────────────────────────────
    df = _standardise_columns(df)

    # ── Step 3: Validate and clean UDISE codes ────────────────────────────
    df, bad_udise = _clean_udise_codes(df)
    stats['invalid_udise'] = bad_udise

    # ── Step 4: Validate coordinates ──────────────────────────────────────
    df = _validate_coordinates(df)
    stats['invalid_coords'] = (~df.get('coords_valid', pd.Series([True] * len(df)))).sum()

    # ── Step 5: Clean numeric fields ──────────────────────────────────────
    df = _clean_numeric_fields(df)

    # ── Step 6: Clean boolean fields ──────────────────────────────────────
    df = _clean_boolean_fields(df)

    # ── Step 7: Normalise management type ─────────────────────────────────
    df = _normalise_management_type(df)

    # ── Step 8: Remove exact duplicates ───────────────────────────────────
    before_dedup = len(df)
    df = df.drop_duplicates(subset=['udise_code'], keep='first')
    stats['duplicates_removed'] = before_dedup - len(df)

    # ── Step 9: Flag suspicious enrollment values ─────────────────────────
    df = _flag_suspicious_values(df)
    stats['suspicious_enrollment'] = df.get('suspicious_enrollment', pd.Series([])).sum()

    stats['cleaned_rows'] = len(df)
    stats['retention_pct'] = round(len(df) / max(original_count, 1) * 100, 1)

    logger.info(
        f"UDISE cleaning complete: {original_count} → {len(df)} rows "
        f"({stats['retention_pct']}% retained)"
    )
    return df, stats


def _fix_encoding(df: pd.DataFrame) -> pd.DataFrame:
    """Fix common encoding issues in UDISE data (Hindi/regional language fields)."""
    for col in df.select_dtypes(include='object').columns:
        try:
            df[col] = df[col].astype(str).apply(_fix_string_encoding)
        except Exception:
            pass
    return df


def _fix_string_encoding(s: str) -> str:
    """Attempt to fix mojibake and normalise whitespace."""
    if not isinstance(s, str):
        return str(s)
    s = s.strip()
    # Remove null characters
    s = s.replace('\x00', '').replace('\ufffd', '')
    # Normalise multiple spaces
    s = re.sub(r'\s+', ' ', s)
    return s


def _standardise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Convert column names to lowercase snake_case."""
    df.columns = [
        re.sub(r'[\s\-/]+', '_', col.lower().strip())
        for col in df.columns
    ]
    return df


def _clean_udise_codes(df: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """Validate UDISE codes: must be exactly 11 digits."""
    if 'udise_code' not in df.columns:
        return df, 0

    df['udise_code'] = df['udise_code'].astype(str).str.strip().str.replace(r'\D', '', regex=True)

    valid_mask = df['udise_code'].str.match(r'^\d{11}$')
    bad_count = (~valid_mask).sum()

    if bad_count > 0:
        logger.warning(f"Dropping {bad_count} rows with invalid UDISE codes")

    df = df[valid_mask].copy()
    return df, int(bad_count)


def _validate_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Validate lat/lng within India bounding box."""
    if 'latitude' not in df.columns or 'longitude' not in df.columns:
        df['coords_valid'] = False
        return df

    df['latitude'] = pd.to_numeric(df['latitude'], errors='coerce')
    df['longitude'] = pd.to_numeric(df['longitude'], errors='coerce')

    lat_valid = (
        df['latitude'].notna()
        & df['latitude'].between(LAT_MIN, LAT_MAX)
        & (df['latitude'] != 0)
    )
    lng_valid = (
        df['longitude'].notna()
        & df['longitude'].between(LNG_MIN, LNG_MAX)
        & (df['longitude'] != 0)
    )
    df['coords_valid'] = lat_valid & lng_valid

    # Zero out invalid coordinates (keep rows but mark them)
    invalid_mask = ~df['coords_valid']
    df.loc[invalid_mask, 'latitude'] = None
    df.loc[invalid_mask, 'longitude'] = None

    return df


def _clean_numeric_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Convert and clip numeric enrollment/teacher fields."""
    numeric_fields = {
        'reported_enrollment': (0, 5000),
        'reported_teachers': (0, 200),
        'reported_meals_daily': (0, 5000),
    }
    for field, (min_val, max_val) in numeric_fields.items():
        if field in df.columns:
            df[field] = (
                pd.to_numeric(df[field].astype(str).str.replace(',', ''), errors='coerce')
                .fillna(0)
                .clip(min_val, max_val)
                .astype(int)
            )
    return df


def _clean_boolean_fields(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise boolean fields."""
    bool_fields = ['reported_building_exists', 'reported_kitchen_exists']
    truthy = {'yes', '1', 'true', 'available', 'y', 'हाँ', 'ha', 'pucca', 'kutcha'}
    for field in bool_fields:
        if field in df.columns:
            df[field] = df[field].astype(str).str.lower().str.strip().isin(truthy)
    return df


def _normalise_management_type(df: pd.DataFrame) -> pd.DataFrame:
    """Map management type variants to government/private/aided."""
    if 'management_type' not in df.columns:
        df['management_type'] = 'government'
        return df

    mapping = {
        'govt': 'government', 'state govt': 'government',
        'central govt': 'government', 'local body': 'government',
        'pvt': 'private', 'private unaided': 'private',
        'private aided': 'aided', 'aided': 'aided',
        'central tibetan': 'government',
    }
    df['management_type'] = (
        df['management_type']
        .astype(str).str.lower().str.strip()
        .map(lambda x: mapping.get(x, 'government' if 'govt' in x else ('private' if 'pvt' in x or 'private' in x else 'government')))
    )
    df.loc[~df['management_type'].isin(['government', 'private', 'aided']), 'management_type'] = 'government'
    return df


def _flag_suspicious_values(df: pd.DataFrame) -> pd.DataFrame:
    """Flag rows with statistically suspicious enrollment or teacher counts."""
    if 'reported_enrollment' in df.columns and 'reported_teachers' in df.columns:
        # More than 200 students per teacher is suspicious
        df['teacher_student_ratio'] = (
            df['reported_enrollment'] / df['reported_teachers'].replace(0, np.nan)
        ).fillna(0)

        # Enrollment > 1500 is extremely unusual for a government primary school
        df['suspicious_enrollment'] = (
            (df['reported_enrollment'] > 1500)
            | (df['teacher_student_ratio'] > 200)
            | ((df['reported_enrollment'] > 0) & (df['reported_teachers'] == 0))
        )
    else:
        df['suspicious_enrollment'] = False

    return df


def save_cleaned(df: pd.DataFrame, output_path: str) -> str:
    """Save cleaned DataFrame to CSV."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    logger.info(f"Cleaned data saved to {output_path} ({len(df)} rows)")
    return output_path
