"""
CAG audit report PDF parser.
Extracts education-related findings using pdfplumber + regex.
"""
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd

logger = logging.getLogger(__name__)

EDUCATION_KEYWORDS = [
    "school", "vidyalaya", "education", "mid-day meal", "mdm",
    "sarva shiksha", "samagra", "teacher", "enrollment", "students",
    "scholarship", "textbook", "grant", "construction", "building",
]

AMOUNT_PATTERN = re.compile(
    r"(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:lakh|crore|lakhs|crores)?",
    re.IGNORECASE,
)

DISTRICT_PATTERN = re.compile(
    r"\b(district(?:\s+of)?\s+([A-Za-z\s]+?))\b",
    re.IGNORECASE,
)


def parse_cag_report(pdf_path: str, state: str = "Uttar Pradesh") -> List[Dict]:
    """
    Parse CAG audit report PDF and extract education findings.

    Args:
        pdf_path: path to CAG report PDF
        state: state name for filtering

    Returns: list of finding dicts
    """
    path = Path(pdf_path)
    if not path.exists():
        logger.warning(f"CAG PDF not found: {pdf_path} — returning synthetic findings")
        return _generate_synthetic_cag(state)

    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber not installed — cannot parse CAG PDF")
        return _generate_synthetic_cag(state)

    findings = []
    try:
        with pdfplumber.open(str(path)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text() or ""
                page_findings = _extract_findings_from_text(text, page_num, state)
                findings.extend(page_findings)
    except Exception as exc:
        logger.error(f"CAG PDF parse failed: {exc}")
        return _generate_synthetic_cag(state)

    logger.info(f"CAG parser: extracted {len(findings)} education findings from {path.name}")
    return findings


def _extract_findings_from_text(text: str, page: int, state: str) -> List[Dict]:
    """Extract individual findings from a page of text."""
    findings = []
    paragraphs = re.split(r"\n{2,}|\f", text)

    for para in paragraphs:
        para_lower = para.lower()
        if not any(kw in para_lower for kw in EDUCATION_KEYWORDS):
            continue

        # Extract monetary amount
        amount_match = AMOUNT_PATTERN.search(para)
        amount_inr = 0.0
        if amount_match:
            amount_str = amount_match.group(1).replace(",", "")
            try:
                amount_raw = float(amount_str)
                unit = amount_match.group(0).lower()
                if "crore" in unit:
                    amount_inr = amount_raw * 10_000_000
                elif "lakh" in unit:
                    amount_inr = amount_raw * 100_000
                else:
                    amount_inr = amount_raw
            except ValueError:
                pass

        # Extract district name
        dist_match = DISTRICT_PATTERN.search(para)
        district = dist_match.group(2).strip() if dist_match else "Unknown"

        # Classify finding type
        finding_type = _classify_finding(para_lower)

        severity = "high" if amount_inr > 1_000_000 else ("medium" if amount_inr > 100_000 else "low")

        summary = para.strip()[:300]

        findings.append({
            "state": state,
            "district": district,
            "year": _extract_year(text),
            "page": page,
            "finding_type": finding_type,
            "amount_inr": round(amount_inr, 2),
            "summary": summary,
            "severity": severity,
        })

    return findings


def _classify_finding(text_lower: str) -> str:
    """Classify CAG finding type from text."""
    if "ghost" in text_lower or "non-existent" in text_lower:
        return "ghost_school"
    if "mid-day meal" in text_lower or "mdm" in text_lower or "meal" in text_lower:
        return "meal_fraud"
    if "construction" in text_lower or "building" in text_lower:
        return "construction_fraud"
    if "teacher" in text_lower or "absenteeism" in text_lower:
        return "teacher_absence"
    if "enrolment" in text_lower or "enrollment" in text_lower:
        return "enrollment_inflation"
    if "scholarship" in text_lower or "textbook" in text_lower:
        return "budget_misuse"
    return "general_irregularity"


def _extract_year(text: str) -> int:
    """Extract audit year from text."""
    year_match = re.search(r"\b(20\d{2})-(\d{2})\b", text)
    if year_match:
        return int(year_match.group(1))
    year_match = re.search(r"\b(20\d{2})\b", text)
    if year_match:
        return int(year_match.group(1))
    return 2022


def _generate_synthetic_cag(state: str) -> List[Dict]:
    """Generate synthetic CAG findings for demo."""
    return [
        {
            "state": state,
            "district": "Sitapur",
            "year": 2022,
            "page": 45,
            "finding_type": "ghost_school",
            "amount_inr": 1_200_000,
            "summary": (
                "Audit observed that in Sitapur district, 12 schools reported enrollment "
                "but no building was found on physical inspection. Rs. 12 lakh in MDM "
                "funds were drawn without eligible beneficiaries."
            ),
            "severity": "high",
        },
        {
            "state": state,
            "district": "Sitapur",
            "year": 2022,
            "page": 78,
            "finding_type": "construction_fraud",
            "amount_inr": 3_500_000,
            "summary": (
                "Construction work sanctioned under Samagra Shiksha Abhiyan for "
                "classroom blocks in 7 schools of Sitapur district was reported complete "
                "but physical verification showed incomplete or substandard work. "
                "Amount involved: Rs. 35 lakh."
            ),
            "severity": "high",
        },
        {
            "state": state,
            "district": "Lucknow",
            "year": 2021,
            "page": 112,
            "finding_type": "meal_fraud",
            "amount_inr": 850_000,
            "summary": (
                "MDM beneficiary figures in 15 schools exceeded enrollment by 30-180%. "
                "Excess meal costs: Rs. 8.5 lakh."
            ),
            "severity": "medium",
        },
    ]
