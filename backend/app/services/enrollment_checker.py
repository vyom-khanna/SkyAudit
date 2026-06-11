"""
Module 3: Enrollment Inflation Checker
Cross-references reported enrollment against building capacity and census ceilings.
"""
import logging
from typing import Dict, Any, Optional

from app.ml.enrollment_model import compute_anomaly_score

logger = logging.getLogger(__name__)

MODULE_ID = 3
MODULE_NAME = "Enrollment Verification"

INFLATION_THRESHOLD = 1.20
MDM_COST_PER_MEAL_INR = 8.17
SCHOOL_DAYS = 220


def run(
    school_row: Dict[str, Any],
    building_result: Dict[str, Any],
    district_ceiling_ratio: float,
) -> Dict[str, Any]:
    """
    Check enrollment inflation using building capacity + census ceiling.

    Args:
        school_row: dict with udise_code, reported_enrollment, reported_meals_daily
        building_result: from ghost_detector / building_detector with estimated_capacity
        district_ceiling_ratio: computed from census (total_reported / ceiling)

    Returns standardised module result dict.
    """
    reported = int(school_row.get("reported_enrollment", 0))
    reported_meals = int(school_row.get("reported_meals_daily", 0))
    estimated_capacity = int(building_result.get("estimated_capacity", 0))
    building_exists = building_result.get("building_exists", True)

    # If building doesn't exist, ghost detector handles it; enrollment is trivially inflated
    if not building_exists:
        excess_meals_cost = reported * SCHOOL_DAYS * MDM_COST_PER_MEAL_INR
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": building_result.get("confidence", 0.8),
            "reported_value": f"{reported} students enrolled",
            "verified_value": "0 — no building exists",
            "discrepancy_amount_inr": excess_meals_cost,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"Ghost school detected — {reported} enrolled students "
                f"cannot attend a non-existent facility. "
                f"₹{excess_meals_cost/100_000:.1f}L annual MDM funds at risk."
            ),
        }

    if estimated_capacity == 0 or reported == 0:
        return _pending_result(f"Insufficient data — capacity: {estimated_capacity}, reported: {reported}")

    capacity_ratio = reported / estimated_capacity
    anomaly_score = compute_anomaly_score(reported, estimated_capacity, district_ceiling_ratio)

    if capacity_ratio > INFLATION_THRESHOLD or district_ceiling_ratio > INFLATION_THRESHOLD:
        excess_students = max(0, reported - estimated_capacity)
        meal_overpayment = (
            excess_students * SCHOOL_DAYS * MDM_COST_PER_MEAL_INR
            if excess_students > 0
            else 0
        )
        per_child_grant = 1200  # approx SSA per-child grant INR/year
        grant_inflation = excess_students * per_child_grant

        total_at_risk = meal_overpayment + grant_inflation

        reasons = []
        if capacity_ratio > INFLATION_THRESHOLD:
            reasons.append(
                f"building fits ≈{estimated_capacity} children "
                f"but {reported} reported ({capacity_ratio:.1f}x)"
            )
        if district_ceiling_ratio > INFLATION_THRESHOLD:
            reasons.append(
                f"district-wide enrollment {district_ceiling_ratio:.1f}x census ceiling"
            )

        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": min(0.92, anomaly_score + 0.3),
            "reported_value": f"{reported} students",
            "verified_value": f"≈{estimated_capacity} capacity (building size)",
            "discrepancy_amount_inr": total_at_risk,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"Enrollment inflation detected: {'; '.join(reasons)}. "
                f"~{excess_students} phantom students generating ₹{total_at_risk/100_000:.1f}L risk."
            ),
            "inflation_ratio": round(capacity_ratio, 2),
            "anomaly_score": anomaly_score,
        }

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": 0.75,
        "reported_value": f"{reported} students enrolled",
        "verified_value": f"Consistent with building capacity (~{estimated_capacity})",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": (
            f"Enrollment ({reported}) is within expected range for a building "
            f"with ~{estimated_capacity} capacity (ratio {capacity_ratio:.1f}x, "
            f"threshold {INFLATION_THRESHOLD}x)."
        ),
    }


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
