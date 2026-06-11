"""
Module 6: Teacher Presence Risk Scorer
Composite risk score using enrollment, outcome, infrastructure, and CAG signals.
"""
import logging
from typing import Dict, Any, Optional, List

from app.ml.teacher_risk_model import compute_teacher_risk

logger = logging.getLogger(__name__)

MODULE_ID = 6
MODULE_NAME = "Teacher Presence Verification"

# District average teacher-student ratio (RTE norm: 1:30 primary, 1:35 upper primary)
RTE_RATIO_PRIMARY = 30
RTE_RATIO_UPPER = 35


def run(
    school_row: Dict[str, Any],
    module_results: List[Dict[str, Any]],
    cag_findings: Optional[List[Dict[str, Any]]] = None,
    district_avg_ratio: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute teacher presence risk using composite signals.

    Args:
        school_row: dict with reported_teachers, reported_enrollment, udise_code
        module_results: list of results from modules 1-5
        cag_findings: list of CAG audit findings for the district
        district_avg_ratio: average teacher-student ratio in district

    Returns standardised module result dict.
    """
    reported_teachers = int(school_row.get("reported_teachers", 0))
    reported_enrollment = int(school_row.get("reported_enrollment", 0))
    udise_code = school_row.get("udise_code", "")

    # Extract anomaly scores from previous modules
    enrollment_score = _extract_module_score(module_results, module_id=3)
    outcome_score = _extract_module_score(module_results, module_id=5)
    infra_score = float(school_row.get("infrastructure_score", 0.5))

    # CAG historical flag
    cag_flag = 0
    cag_summary = ""
    if cag_findings:
        district_findings = [f for f in cag_findings if f.get("severity") in ("high", "critical")]
        if district_findings:
            cag_flag = 1
            cag_summary = (
                f" CAG has flagged this district for: "
                + "; ".join(f.get("finding_type", "") for f in district_findings[:2])
            )

    risk_score = compute_teacher_risk(
        {
            "enrollment_anomaly_score": enrollment_score,
            "outcome_anomaly_score": outcome_score,
            "infrastructure_score": infra_score,
            "historical_cag_flag": cag_flag,
        }
    )

    # Teacher-student ratio check
    ratio_warning = ""
    ratio_anomaly = False
    if reported_teachers > 0 and reported_enrollment > 0:
        actual_ratio = reported_enrollment / reported_teachers
        norm_ratio = RTE_RATIO_PRIMARY
        district_ratio = district_avg_ratio or norm_ratio

        if actual_ratio > district_ratio * 1.5:
            ratio_warning = (
                f" Ratio {actual_ratio:.0f}:1 is {actual_ratio/district_ratio:.1f}x "
                f"district average ({district_ratio:.0f}:1)."
            )
            ratio_anomaly = True
        elif actual_ratio < 10:
            ratio_warning = (
                f" Suspiciously low ratio {actual_ratio:.0f}:1 "
                f"({reported_teachers} teachers for {reported_enrollment} students)."
            )
            ratio_anomaly = True

    is_anomaly = risk_score >= 0.55 or ratio_anomaly

    if is_anomaly:
        return {
            "module_id": MODULE_ID,
            "module_name": MODULE_NAME,
            "status": "anomaly",
            "confidence": min(0.88, 0.4 + risk_score * 0.6),
            "reported_value": (
                f"{reported_teachers} teachers, {reported_enrollment} students "
                f"(ratio {reported_enrollment/max(1,reported_teachers):.0f}:1)"
            ),
            "verified_value": f"High-risk composite score: {risk_score:.2f}/1.00",
            "discrepancy_amount_inr": None,
            "satellite_image_url": None,
            "evidence_url": None,
            "summary": (
                f"Teacher presence risk score: {risk_score:.2f}/1.00 (high). "
                f"Driven by: enrollment anomaly ({enrollment_score:.2f}), "
                f"outcome anomaly ({outcome_score:.2f}), "
                f"infra score ({infra_score:.2f}).{ratio_warning}{cag_summary}"
            ),
            "risk_score": round(risk_score, 3),
        }

    return {
        "module_id": MODULE_ID,
        "module_name": MODULE_NAME,
        "status": "verified",
        "confidence": 0.70,
        "reported_value": (
            f"{reported_teachers} teachers, {reported_enrollment} students"
        ),
        "verified_value": f"Risk score: {risk_score:.2f}/1.00 (acceptable)",
        "discrepancy_amount_inr": None,
        "satellite_image_url": None,
        "evidence_url": None,
        "summary": (
            f"Teacher presence risk is within acceptable range (score: {risk_score:.2f}). "
            f"No strong anomaly signals from correlated modules.{ratio_warning}"
        ),
        "risk_score": round(risk_score, 3),
    }


def _extract_module_score(module_results: List[Dict], module_id: int) -> float:
    """Extract anomaly confidence from a specific module result."""
    for r in module_results:
        if r.get("module_id") == module_id:
            if r.get("status") in ("anomaly", "ghost"):
                return float(r.get("confidence", 0.5))
            return 0.0
    return 0.0
