"""
Module 5: Outcome Authenticator
Flags schools where reported exam pass rates exceed ML-predicted rates by >2 std dev.
"""
import logging
from typing import Dict, Any, Optional

from app.ml.outcome_model import predict_expected_rate

logger = logging.getLogger(__name__)

MODULE_ID = 5
MODULE_NAME = "Learning Outcome Verification"

ANOMALY_STD_THRESHOLD = 2.0


def run(
    school_row: Dict[str, Any],
    board_results: Optional[Dict[str, Any]],
    aser_data: Optional[Dict[str, Any]],
    district_std: float = 0.12,
) -> Dict[str, Any]:
    """
    Compare predicted vs reported board exam pass rate.

    Args:
        school_row: dict with feature columns for the ML model
        board_results: dict with reported_pass_rate, year, total_appeared, total_passed
        aser_data: dict with district pct_can_read_std2, pct_can_do_division
        district_std: standard deviation of residuals in district (default 0.12)

    Returns standardised module result dict.
    """
    if board_results is None:
        return _pending_result("No board results data available for this school")

    reported_pass_rate = float(board_results.get("reported_pass_rate", 0))
    total_appeared = int(board_results.get("total_appeared", 0))
    total_passed = int(board_results.get("total_passed", 0))
    result_year = board_results.get("year", "")

    if total_appeared < 5:
        return _pending_result(f"Insufficient data: only {total_appeared} students appeared")

    # Build feature dict for ML model
    features = {
        "infrastructure_score": float(school_row.get("infrastructure_score", 0.5)),
        "teacher_student_ratio": (
            float(school_row.get("reported_teachers", 2))
            / max(1, float(school_row.get("reported_enrollment", 100)))
            * 100
        ),
        "per_child_spend": float(school_row.get("per_child_spend", 8000)),
        "district_poverty_index": float(school_row.get("district_poverty_index", 0.5)),
        "historical_pass_rate_3yr": float(school_row.get("historical_pass_rate_3yr", reported_pass_rate)),
    }

    predicted = predict_expected_rate(features)
    residual = reported_pass_rate - predicted
    z_score = residual / max(district_std, 0.01)

    # Cross-validate with ASER district learning levels
    aser_warning = ""
    if aser_data:
        pct_read = float(aser_data.get("pct_can_read_std2", 0.5))
        pct_div = float(aser_data.get("pct_can_do_division", 0.3))
        aser_composite = (pct_read + pct_div) / 2
        aser_expected_pass = aser_composite * 0.8 + 0.2  # rough calibration
        if reported_pass_rate > aser_expected_pass + 0.20:
            aser_warning = (
                f" ASER district learning level ({aser_composite:.0%}) "
                f"is inconsistent with {reported_pass_rate:.0%} pass rate."
            )

    if z_score > ANOMALY_STD_THRESHOLD:
        gap_pct = (reported_pass_rate - predicted) * 100
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": min(0.90, 0.50 + (z_score - 2) * 0.10),
            "reported_value": f"{reported_pass_rate:.0%} pass rate ({result_year})",
            "verified_value": f"Predicted {predicted:.0%} based on school characteristics",
            "discrepancy_amount_inr": None,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"Board results appear inflated: school reports {reported_pass_rate:.0%} "
                f"but model predicts {predicted:.0%} ({gap_pct:+.1f}pp, z={z_score:.1f}σ). "
                f"{aser_warning}"
            ),
            "z_score": round(z_score, 2),
            "predicted_pass_rate": round(predicted, 3),
            "reported_pass_rate": round(reported_pass_rate, 3),
        }

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": 0.75,
        "reported_value": f"{reported_pass_rate:.0%} pass rate ({result_year})",
        "verified_value": f"Consistent with model prediction ({predicted:.0%})",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": (
            f"Pass rate ({reported_pass_rate:.0%}) is within expected range. "
            f"Model prediction: {predicted:.0%} (z={z_score:.1f}σ).{aser_warning}"
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
