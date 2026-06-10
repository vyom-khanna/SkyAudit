"""
Satellite data processing pipeline.
Batches NDBI computation and building detection across a district,
caching results in the satellite_captures table.
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 90


def process_district_satellite(
    district_code: str,
    schools_df: pd.DataFrame,
    db,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Run satellite processing for all schools in a district DataFrame.

    For each school:
    1. Check if a fresh capture exists in satellite_captures table
    2. If not (or force_refresh), fetch new imagery and compute NDBI
    3. Run building detection
    4. Persist to satellite_captures

    Returns schools_df enriched with satellite columns.
    """
    from app.models import SatelliteCapture
    from app.services.satellite import get_sentinel2_image
    from app.ml.building_detector import detect_building_at_coordinate, estimate_capacity

    cutoff_date = date.today() - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    results = []

    for _, school in schools_df.iterrows():
        udise = school.get('udise_code', '')
        lat = school.get('latitude')
        lng = school.get('longitude')

        if lat is None or lng is None:
            results.append(_null_satellite_row(udise))
            continue

        # Check cache
        if not force_refresh and db is not None:
            cached = _get_cached_capture(db, udise, cutoff_date)
            if cached:
                results.append({
                    'udise_code': udise,
                    'image_url': cached.image_url,
                    'ndbi_score': cached.ndbi_score,
                    'building_detected': cached.building_detected,
                    'building_confidence': cached.building_confidence,
                    'building_footprint_sqm': cached.building_footprint_sqm or 0.0,
                    'estimated_capacity': estimate_capacity(cached.building_footprint_sqm or 0.0),
                    'capture_date': str(cached.capture_date),
                    'source': cached.source,
                    'from_cache': True,
                })
                continue

        # Fetch fresh imagery
        today_str = datetime.utcnow().strftime('%Y-%m-%d')
        start_str = (datetime.utcnow() - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime('%Y-%m-%d')

        sat_result = get_sentinel2_image(float(lat), float(lng), start_str, today_str)
        detection = detect_building_at_coordinate(float(lat), float(lng))

        row = {
            'udise_code': udise,
            'image_url': sat_result.get('image_url', ''),
            'ndbi_score': float(sat_result.get('ndbi', 0.0)),
            'building_detected': detection['building_exists'],
            'building_confidence': float(detection['confidence']),
            'building_footprint_sqm': float(detection.get('footprint_sqm', 0.0)),
            'estimated_capacity': estimate_capacity(detection.get('footprint_sqm', 0.0)),
            'capture_date': today_str,
            'source': sat_result.get('source', 'sentinel2'),
            'from_cache': False,
        }

        # Persist to database
        if db is not None:
            _persist_capture(db, udise, row)

        results.append(row)
        logger.info(
            f"Satellite processed {udise}: building={detection['building_exists']} "
            f"ndbi={sat_result.get('ndbi', 0.0):.4f}"
        )

    sat_df = pd.DataFrame(results)
    return schools_df.merge(sat_df, on='udise_code', how='left')


def _get_cached_capture(db, udise_code: str, cutoff_date: date):
    """Return fresh cached capture if available."""
    from app.models import SatelliteCapture
    return (
        db.query(SatelliteCapture)
        .filter(
            SatelliteCapture.udise_code == udise_code,
            SatelliteCapture.capture_date >= cutoff_date,
        )
        .order_by(SatelliteCapture.capture_date.desc())
        .first()
    )


def _persist_capture(db, udise_code: str, row: dict) -> None:
    """Save satellite capture to database."""
    from app.models import SatelliteCapture
    from datetime import date as date_type
    cap = SatelliteCapture(
        udise_code=udise_code,
        capture_date=date_type.fromisoformat(row['capture_date']) if isinstance(row['capture_date'], str) else row['capture_date'],
        image_url=row['image_url'],
        ndbi_score=row['ndbi_score'],
        building_detected=row['building_detected'],
        building_confidence=row['building_confidence'],
        building_footprint_sqm=row['building_footprint_sqm'],
        source=row['source'],
    )
    db.add(cap)
    try:
        db.commit()
    except Exception:
        db.rollback()


def _null_satellite_row(udise_code: str) -> dict:
    return {
        'udise_code': udise_code,
        'image_url': None,
        'ndbi_score': None,
        'building_detected': None,
        'building_confidence': None,
        'building_footprint_sqm': None,
        'estimated_capacity': 0,
        'capture_date': None,
        'source': None,
        'from_cache': False,
    }


def compute_district_ndbi_stats(sat_df: pd.DataFrame) -> dict:
    """
    Compute district-level satellite statistics from processed DataFrame.
    """
    if sat_df.empty or 'ndbi_score' not in sat_df.columns:
        return {}

    valid = sat_df.dropna(subset=['ndbi_score'])
    if valid.empty:
        return {}

    return {
        'mean_ndbi': float(valid['ndbi_score'].mean()),
        'schools_with_building': int(valid['building_detected'].sum()),
        'schools_without_building': int((~valid['building_detected']).sum()),
        'ghost_rate': round(float((~valid['building_detected']).mean()), 4),
        'avg_building_confidence': float(valid['building_confidence'].mean()),
        'total_schools_processed': len(valid),
    }
