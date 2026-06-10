"""
Satellite-based construction change detection using NDBI analysis.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
import pandas as pd

from app.services.satellite import get_sentinel2_image

logger = logging.getLogger(__name__)

NDBI_CHANGE_THRESHOLD = 0.05  # Positive delta → new construction


def compute_ndbi_change(
    lat: float,
    lng: float,
    date_before: datetime,
    date_after: datetime,
) -> Dict[str, Any]:
    """
    Compare NDBI before and after a date to detect construction.

    Returns:
        construction_detected (bool)
        confidence (float 0-1)
        ndbi_before (float)
        ndbi_after (float)
        before_url (str)
        after_url (str)
    """
    fmt = "%Y-%m-%d"

    # Before window: 90 days ending on date_before
    before_start = (date_before - timedelta(days=90)).strftime(fmt)
    before_end = date_before.strftime(fmt)

    # After window: 30 to 365 days after date_after
    after_start = (date_after + timedelta(days=30)).strftime(fmt)
    after_end = (date_after + timedelta(days=365)).strftime(fmt)

    before_result = get_sentinel2_image(lat, lng, before_start, before_end)
    after_result = get_sentinel2_image(lat, lng, after_start, after_end)

    ndbi_before = float(before_result.get("ndbi", 0.0))
    ndbi_after = float(after_result.get("ndbi", 0.0))
    delta = ndbi_after - ndbi_before

    if delta > NDBI_CHANGE_THRESHOLD:
        detected = True
        confidence = min(0.95, 0.5 + delta * 5)
    elif delta > 0:
        detected = False
        confidence = 0.3
    else:
        detected = False
        confidence = 0.8  # High confidence no construction

    return {
        "construction_detected": detected,
        "confidence": round(confidence, 3),
        "ndbi_before": round(ndbi_before, 4),
        "ndbi_after": round(ndbi_after, 4),
        "ndbi_delta": round(delta, 4),
        "before_url": before_result.get("image_url", ""),
        "after_url": after_result.get("image_url", ""),
    }


def batch_construction_check(grants_df: pd.DataFrame) -> pd.DataFrame:
    """
    Check construction for every grant in the DataFrame.

    Expects columns:
        udise_code, latitude, longitude,
        sanction_date, completion_deadline, grant_amount_inr

    Returns grants_df enriched with:
        construction_detected, confidence, ndbi_delta,
        flagged (bool — no construction detected past deadline)
        funds_at_risk_inr
    """
    today = datetime.utcnow()
    results = []

    for _, row in grants_df.iterrows():
        lat = row.get("latitude")
        lng = row.get("longitude")
        sanction_date = pd.to_datetime(row.get("sanction_date"))
        completion_deadline = pd.to_datetime(row.get("completion_deadline"))
        grant_amount = float(row.get("grant_amount_inr", 0))

        if lat is None or lng is None:
            results.append(
                {
                    "udise_code": row["udise_code"],
                    "construction_detected": False,
                    "confidence": 0.0,
                    "ndbi_delta": 0.0,
                    "flagged": False,
                    "funds_at_risk_inr": 0.0,
                }
            )
            continue

        # Only check if past completion deadline
        if completion_deadline > today:
            results.append(
                {
                    "udise_code": row["udise_code"],
                    "construction_detected": None,
                    "confidence": 0.0,
                    "ndbi_delta": 0.0,
                    "flagged": False,
                    "funds_at_risk_inr": 0.0,
                }
            )
            continue

        check = compute_ndbi_change(lat, lng, sanction_date, completion_deadline)
        flagged = not check["construction_detected"] and completion_deadline < today

        results.append(
            {
                "udise_code": row["udise_code"],
                "construction_detected": check["construction_detected"],
                "confidence": check["confidence"],
                "ndbi_delta": check["ndbi_delta"],
                "before_url": check["before_url"],
                "after_url": check["after_url"],
                "flagged": flagged,
                "funds_at_risk_inr": grant_amount if flagged else 0.0,
            }
        )
        logger.info(
            f"Construction check {row['udise_code']}: detected={check['construction_detected']}, "
            f"δNDBI={check['ndbi_delta']:.4f}"
        )

    result_df = pd.DataFrame(results)
    return grants_df.merge(result_df, on="udise_code", how="left")
