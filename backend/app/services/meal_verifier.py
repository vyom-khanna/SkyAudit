"""
Module 4: Mid-Day Meal Fraud Verifier
Cross-checks PM Poshan meal claims against verified enrollment.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MODULE_ID = 4
MODULE_NAME = "Mid-Day Meal Verification"

MDM_COST_PER_MEAL_INR = 8.17
SCHOOL_DAYS = 220
TOLERANCE_RATIO = 1.10  # 10% tolerance


def run(
    school_row: Dict[str, Any],
    mdm_data: Optional[Dict[str, Any]],
    verified_enrollment: int,
) -> Dict[str, Any]:
    """
    Verify Mid-Day Meal claims against satellite-verified enrollment.

    Args:
        school_row: dict with reported_meals_daily, udise_code
        mdm_data: dict with meals_claimed_monthly, meals_claimed_annual
                  (from PM Poshan portal scrape)
        verified_enrollment: enrollment count from Module 3

    Returns standardised module result dict.
    """
    reported_meals_daily = int(school_row.get("reported_meals_daily", 0))

    if mdm_data is None:
        # Fall back to UDISE-reported meals
        if reported_meals_daily == 0:
            return _pending_result("No MDM data available from PM Poshan portal")

        mdm_annual = reported_meals_daily * SCHOOL_DAYS
        meals_daily_claimed = reported_meals_daily
    else:
        mdm_annual = float(mdm_data.get("meals_claimed_annual", 0))
        meals_daily_claimed = mdm_annual / SCHOOL_DAYS if SCHOOL_DAYS > 0 else reported_meals_daily

    if verified_enrollment == 0:
        return _pending_result("Verified enrollment is zero — meal check deferred to enrollment module")

    expected_daily = verified_enrollment
    expected_annual = verified_enrollment * SCHOOL_DAYS

    ratio = meals_daily_claimed / expected_daily if expected_daily > 0 else 0

    if ratio > TOLERANCE_RATIO:
        excess_daily = meals_daily_claimed - expected_daily
        excess_annual = mdm_annual - expected_annual
        funds_at_risk = excess_annual * MDM_COST_PER_MEAL_INR

        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": min(0.92, 0.5 + (ratio - 1) * 0.5),
            "reported_value": f"{meals_daily_claimed:.0f} meals/day ({mdm_annual:.0f} annual)",
            "verified_value": f"{expected_daily} meals/day (= verified students)",
            "discrepancy_amount_inr": funds_at_risk,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"MDM claims {meals_daily_claimed:.0f} meals/day but verified enrollment "
                f"is only {expected_daily}. {ratio:.1f}x overclaiming. "
                f"~{excess_daily:.0f} excess meals/day → "
                f"₹{funds_at_risk/100_000:.1f}L annual risk."
            ),
            "meals_ratio": round(ratio, 2),
            "excess_meals_daily": round(excess_daily, 0),
        }

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": 0.80,
        "reported_value": f"{meals_daily_claimed:.0f} meals/day",
        "verified_value": f"Consistent with {expected_daily} verified students",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": (
            f"Meal claims ({meals_daily_claimed:.0f}/day) are consistent with "
            f"verified enrollment ({expected_daily}). Ratio: {ratio:.2f}x (threshold: {TOLERANCE_RATIO}x)."
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
