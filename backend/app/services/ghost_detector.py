"""
Module 1: Ghost School Detector
Detects schools that exist on paper but have no physical building.
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from app.ml.building_detector import detect_building_at_coordinate
from app.services.satellite import export_thumbnail

logger = logging.getLogger(__name__)

MODULE_ID = 1
MODULE_NAME = "Ghost School Detection"

# Annual costs used to estimate funds at risk
TEACHER_ANNUAL_SALARY_INR = 350_000
MDM_COST_PER_MEAL_INR = 8.17  # current MDM unit cost
SCHOOL_DAYS_PER_YEAR = 220


def run(school_row: Dict[str, Any], mdm_data: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Detect whether a physical school building exists at reported coordinates.

    Args:
        school_row: dict with keys: udise_code, latitude, longitude,
                    reported_building_exists, reported_enrollment,
                    reported_teachers, reported_meals_daily
        mdm_data:   Optional dict with keys: meals_claimed_annual

    Returns standardised module result dict.
    """
    udise_code = school_row.get("udise_code", "")
    lat = school_row.get("latitude")
    lng = school_row.get("longitude")
    reported_building = school_row.get("reported_building_exists", True)
    reported_enrollment = int(school_row.get("reported_enrollment", 0))
    reported_teachers = int(school_row.get("reported_teachers", 0))
    reported_meals = int(school_row.get("reported_meals_daily", 0))

    # Cannot verify without coordinates
    if lat is None or lng is None:
        return _pending_result("No GPS coordinates available for satellite verification")

    # Run building detection
    detection = detect_building_at_coordinate(lat, lng)
    building_exists = detection["building_exists"]
    confidence = detection["confidence"]
    footprint = detection["footprint_sqm"]

    satellite_url = export_thumbnail(lat, lng)

    # Ghost school: reported active, no building detected or critically small building (<20 sqm)
    if reported_building and (not building_exists or footprint < 20):
        funds_at_risk = _estimate_funds_at_risk(
            reported_teachers, reported_enrollment, reported_meals, mdm_data
        )
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "ghost",
            "confidence": confidence,
            "footprint_sqm": footprint,
            "reported_value": f"Building exists, {reported_enrollment} students enrolled",
            "verified_value": f"No building detected or footprint critically small ({footprint:.0f} sqm) within 100m",
            "discrepancy_amount_inr": funds_at_risk,
            "satellite_image_url": satellite_url,
            "evidence_url": satellite_url,
            "summary": (
                f"Satellite imagery shows no building or critically small footprint ({footprint:.0f} sqm) at reported coordinates. "
                f"School claims {reported_enrollment} students and {reported_teachers} teachers. "
                f"Estimated ₹{funds_at_risk/100_000:.1f}L in annual public funds at risk."
            ),
        }

    # Correctly detected as having no building AND not reporting one
    if not building_exists and not reported_building:
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "verified",
            "confidence": confidence,
            "footprint_sqm": footprint,
            "reported_value": "No building reported",
            "verified_value": "No building detected — consistent with report",
            "discrepancy_amount_inr": None,
            "satellite_image_url": satellite_url,
            "evidence_url": satellite_url,
            "summary": "School correctly reports no permanent building. Consistent with satellite data.",
        }

    # Building found, school reports building
    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": confidence,
        "footprint_sqm": footprint,
        "reported_value": f"Building exists, {reported_enrollment} students",
        "verified_value": f"Building detected ({footprint:.0f} sqm footprint)",
        "discrepancy_amount_inr": None,
        "satellite_image_url": satellite_url,
        "evidence_url": satellite_url,
        "summary": (
            f"Building confirmed at coordinates with {footprint:.0f} sqm footprint "
            f"({confidence*100:.0f}% confidence)."
        ),
    }


def _estimate_funds_at_risk(
    teachers: int,
    enrollment: int,
    meals_daily: int,
    mdm_data: Optional[Dict],
) -> float:
    """Estimate total annual public funds flowing to a ghost school."""
    # Teacher salaries
    salary_risk = teachers * TEACHER_ANNUAL_SALARY_INR

    # MDM meals (use claimed data if available)
    if mdm_data and "meals_claimed_annual" in mdm_data:
        meal_risk = mdm_data["meals_claimed_annual"] * MDM_COST_PER_MEAL_INR
    else:
        meal_risk = meals_daily * SCHOOL_DAYS_PER_YEAR * MDM_COST_PER_MEAL_INR

    # Samagra grants (conservative estimate)
    infra_risk = 200_000  # ₹2L baseline annual maintenance grant

    return salary_risk + meal_risk + infra_risk


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
