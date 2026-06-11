"""
Module 2: Construction Tracker
Checks whether Samagra-funded construction actually happened via NDBI change detection.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.ml.change_detection import compute_ndbi_change

logger = logging.getLogger(__name__)

MODULE_ID = 2
MODULE_NAME = "Construction Verification"


def run(
    school_row: Dict[str, Any],
    grants: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Verify construction grants using satellite NDBI change detection.

    Args:
        school_row: dict with lat/lng/udise_code
        grants: list of grant dicts with keys:
                grant_id, grant_amount_inr, sanction_date,
                completion_deadline, reported_completion_date

    Returns standardised module result dict.
    """
    udise_code = school_row.get("udise_code", "")
    lat = school_row.get("latitude")
    lng = school_row.get("longitude")

    if not grants:
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "verified",
            "confidence": 1.0,
            "reported_value": "No construction grants on record",
            "verified_value": "No grants to verify",
            "discrepancy_amount_inr": None,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": "No Samagra construction grants associated with this school.",
        }

    if lat is None or lng is None:
        return _pending_result("No GPS coordinates for satellite verification")

    flagged_grants = []
    total_at_risk = 0.0
    best_before_url = None
    best_after_url = None

    today = datetime.utcnow()

    for grant in grants:
        sanction_date = _parse_date(grant.get("sanction_date"))
        deadline = _parse_date(grant.get("completion_deadline"))
        grant_amount = float(grant.get("grant_amount_inr", 0))

        if sanction_date is None or deadline is None:
            continue

        # Only check if past deadline
        if deadline >= today:
            continue

        check = compute_ndbi_change(lat, lng, sanction_date, deadline)

        if best_before_url is None:
            best_before_url = check.get("before_url")
            best_after_url = check.get("after_url")

        if not check["construction_detected"]:
            months_overdue = (today - deadline).days // 30
            flagged_grants.append(
                {
                    "grant_id": grant.get("grant_id", ""),
                    "grant_amount_inr": grant_amount,
                    "deadline": deadline.strftime("%Y-%m-%d"),
                    "months_overdue": months_overdue,
                    "ndbi_delta": check["ndbi_delta"],
                    "confidence": check["confidence"],
                }
            )
            total_at_risk += grant_amount

    if not flagged_grants:
        total_grant = sum(float(g.get("grant_amount_inr", 0)) for g in grants)
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "verified",
            "confidence": 0.80,
            "reported_value": f"₹{total_grant/100_000:.1f}L in grants, construction reported complete",
            "verified_value": "NDBI change detected — construction confirmed",
            "discrepancy_amount_inr": None,
            "satellite_image_url": best_before_url,
            "evidence_url": best_after_url,
            "summary": (
                f"Satellite NDBI analysis confirms construction activity for "
                f"{len(grants)} grant(s) totalling ₹{total_grant/100_000:.1f}L."
            ),
        }

    # Some grants flagged
    overdue_grants = ", ".join(
        f"₹{g['grant_amount_inr']/100_000:.1f}L ({g['months_overdue']}mo overdue)"
        for g in flagged_grants
    )

    severity_confidence = min(0.95, max(g["confidence"] for g in flagged_grants))

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "anomaly",
        "confidence": severity_confidence,
        "reported_value": f"{len(grants)} grant(s), construction reported complete",
        "verified_value": f"{len(flagged_grants)} grant(s) with no satellite-detected construction",
        "discrepancy_amount_inr": total_at_risk,
        "satellite_image_url": best_before_url,
        "evidence_url": best_after_url,
        "summary": (
            f"No construction activity detected for {len(flagged_grants)} "
            f"overdue grant(s): {overdue_grants}. "
            f"₹{total_at_risk/100_000:.1f}L in funds at risk."
        ),
        "flagged_grants": flagged_grants,
        "before_url": best_before_url,
        "after_url": best_after_url,
    }


def _parse_date(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        import pandas as pd
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _pending_result(reason: str) -> Dict[str, Any]:
    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "pending",
        "confidence": 0.0,
        "reported_value": "Unknown",
        "verified_value": "Verification pending",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": reason,
    }
