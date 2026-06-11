"""
Module 7: Budget Efficiency Analyzer
Ranks districts on per-child spend vs outcomes; flags low-efficiency outliers.
"""
import logging
from typing import Dict, Any, Optional
import numpy as np

logger = logging.getLogger(__name__)

MODULE_ID = 7
MODULE_NAME = "Budget Efficiency Analysis"

# Outcome component weights
OUTCOME_WEIGHTS = {
    "pass_rate": 0.50,
    "aser_score": 0.30,
    "nas_score": 0.20,
}

BOTTOM_QUARTILE_THRESHOLD = 0.25  # bottom 25% efficiency
HIGH_SPEND_THRESHOLD = 0.50       # above median spend


def run(
    district_data: Dict[str, Any],
    verified_outcomes: Dict[str, Any],
    expenditure_data: Dict[str, Any],
    national_distribution: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Compute district budget efficiency and flag bottom-quartile + high-spend districts.

    Args:
        district_data: district row with district_code, district_name, verified_enrollment
        verified_outcomes: dict with pass_rate, aser_score, nas_score (0-1 each)
        expenditure_data: dict with total_budget_inr, verified_enrollment
        national_distribution: dict with efficiency percentiles for national ranking

    Returns standardised module result dict.
    """
    district_code = district_data.get("district_code", "")
    district_name = district_data.get("district_name", "")

    verified_enrollment = int(
        district_data.get("verified_enrollment")
        or expenditure_data.get("verified_enrollment", 1)
    )
    total_budget = float(expenditure_data.get("total_budget_inr", 0))

    if verified_enrollment == 0 or total_budget == 0:
        return _pending_result("Insufficient expenditure or enrollment data")

    per_child_spend = total_budget / verified_enrollment

    # Outcome composite score (0-1)
    pass_rate = float(verified_outcomes.get("pass_rate", 0.6))
    aser_score = float(verified_outcomes.get("aser_score", 0.5))
    nas_score = float(verified_outcomes.get("nas_score", 0.5))

    outcome_score = (
        pass_rate * OUTCOME_WEIGHTS["pass_rate"]
        + aser_score * OUTCOME_WEIGHTS["aser_score"]
        + nas_score * OUTCOME_WEIGHTS["nas_score"]
    )

    # Normalise efficiency: outcome per 10,000 INR spent per child
    raw_efficiency = outcome_score / (per_child_spend / 10_000)
    efficiency_score = float(np.clip(raw_efficiency / 5.0, 0.0, 1.0))

    # National ranking position
    national_percentile = 0.50  # default: median
    national_rank = None
    national_total = None
    spend_percentile = 0.50

    if national_distribution:
        eff_p25 = float(national_distribution.get("efficiency_p25", 0.2))
        eff_median = float(national_distribution.get("efficiency_median", 0.4))
        spend_median = float(national_distribution.get("spend_median", 8000))
        national_rank = national_distribution.get("rank")
        national_total = national_distribution.get("total_districts")

        if efficiency_score < eff_p25:
            national_percentile = 0.10
        elif efficiency_score < eff_median:
            national_percentile = 0.35
        else:
            national_percentile = 0.70

        spend_percentile = 0.60 if per_child_spend > spend_median else 0.40

    # Flag: bottom quartile efficiency AND above-median spend
    is_flagged = (
        national_percentile <= BOTTOM_QUARTILE_THRESHOLD
        and spend_percentile >= HIGH_SPEND_THRESHOLD
    )

    rank_str = (
        f"{national_rank} of {national_total} districts nationally"
        if national_rank and national_total
        else f"~{100-int(national_percentile*100)}th percentile nationally"
    )

    if is_flagged:
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": 0.72,
            "reported_value": (
                f"₹{per_child_spend:,.0f}/child/year, "
                f"outcome score {outcome_score:.2f}"
            ),
            "verified_value": (
                f"Efficiency score {efficiency_score:.2f} — "
                f"bottom quartile with above-median spend"
            ),
            "discrepancy_amount_inr": None,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"{district_name} spends ₹{per_child_spend:,.0f}/child/year "
                f"(above median) but achieves only {outcome_score:.0%} composite outcome. "
                f"Efficiency rank: {rank_str}. "
                f"High spend with low outcomes suggests fund leakage or misallocation."
            ),
            "per_child_spend_inr": round(per_child_spend, 0),
            "outcome_score": round(outcome_score, 3),
            "efficiency_score": round(efficiency_score, 3),
            "national_percentile": national_percentile,
        }

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": 0.65,
        "reported_value": f"₹{per_child_spend:,.0f}/child/year",
        "verified_value": f"Efficiency score {efficiency_score:.2f} — within acceptable range",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": (
            f"{district_name} spends ₹{per_child_spend:,.0f}/child/year "
            f"with outcome score {outcome_score:.0%}. "
            f"Efficiency rank: {rank_str}."
        ),
        "per_child_spend_inr": round(per_child_spend, 0),
        "outcome_score": round(outcome_score, 3),
        "efficiency_score": round(efficiency_score, 3),
        "national_percentile": national_percentile,
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
