"""
WhatsApp bot via Twilio — handles UDISE lookups, district queries, rankings.
Supports Hindi and English responses.
"""
import os
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

RATE_LIMIT_WINDOW = 24 * 3600  # 24 hours in seconds
RATE_LIMIT_MAX = 10

# In-memory rate limit store (use Redis in production)
_rate_limit_store: Dict[str, list] = {}

STATUS_EMOJI = {
    "verified": "✅",
    "anomaly": "🔴",
    "ghost": "☠️",
    "pending": "⚠️",
}

MODULE_LABELS = {
    1: "Building",
    2: "Construction",
    3: "Enrollment",
    4: "Mid-Day Meals",
    5: "Pass Rate",
    6: "Teachers",
    7: "Budget",
}


def handle_message(from_number: str, body: str, db) -> str:
    """
    Process incoming WhatsApp message and return response text.

    Handles:
    - 11-digit UDISE codes → school verification summary
    - "district [name]" → district score
    - "rank [district]" → national rank
    - "help" → command list
    """
    if not _check_rate_limit(from_number):
        return (
            "⚠️ You have exceeded the daily limit of 10 queries. "
            "Please try again tomorrow.\n\n"
            "अधिकतम 10 प्रश्न प्रतिदिन। कल पुनः प्रयास करें।"
        )

    body_clean = body.strip()
    is_hindi = _detect_hindi(body_clean)

    # Match 11-digit UDISE code
    udise_match = re.search(r"\b(\d{11})\b", body_clean)
    if udise_match:
        udise_code = udise_match.group(1)
        return _school_lookup(udise_code, db, hindi=is_hindi)

    body_lower = body_clean.lower()

    if body_lower.startswith("district "):
        district_name = body_clean[9:].strip()
        return _district_lookup(district_name, db, hindi=is_hindi)

    if body_lower.startswith("rank "):
        district_name = body_clean[5:].strip()
        return _district_rank(district_name, db, hindi=is_hindi)

    if body_lower in ("help", "मदद", "सहायता", "/start"):
        return _help_message(hindi=is_hindi)

    return _unknown_command(body_clean, hindi=is_hindi)


def _school_lookup(udise_code: str, db, hindi: bool) -> str:
    """Generate school verification summary for WhatsApp."""
    from app.models import School, Verification, Anomaly, District

    school = db.query(School).filter(School.udise_code == udise_code).first()
    if not school:
        if hindi:
            return f"❌ विद्यालय कोड {udise_code} नहीं मिला। कृपया सही UDISE कोड दर्ज करें।"
        return f"❌ School with UDISE code {udise_code} not found. Please check the code."

    district = db.query(District).filter(District.district_code == school.district_code).first()
    district_name = district.district_name if district else school.district_code
    state_name = district.state_name if district else ""

    verifications = (
        db.query(Verification)
        .filter(Verification.udise_code == udise_code)
        .order_by(Verification.module_id)
        .all()
    )

    total_funds = sum(
        v.discrepancy_amount_inr for v in verifications if v.discrepancy_amount_inr
    )

    last_checked = school.last_verified_at
    if last_checked:
        days_ago = (datetime.utcnow() - last_checked).days
        checked_str = f"{days_ago} day{'s' if days_ago != 1 else ''} ago"
    else:
        checked_str = "not yet verified"

    # Build module rows
    module_lines = []
    for v in verifications:
        emoji = STATUS_EMOJI.get(v.status.value if v.status else "pending", "⚠️")
        label = MODULE_LABELS.get(v.module_id, f"Module {v.module_id}")
        funds_str = ""
        if v.discrepancy_amount_inr and v.discrepancy_amount_inr > 0:
            funds_str = f"\n   ₹{v.discrepancy_amount_inr/100_000:.1f}L at risk"

        module_lines.append(
            f"{emoji} {label}: {v.status.value.title() if v.status else 'Pending'}"
            f"\n   Reported: {v.reported_value[:40] if v.reported_value else 'N/A'}"
            f"\n   Verified: {v.verified_value[:40] if v.verified_value else 'Pending'}"
            f"{funds_str}"
        )

    modules_text = "\n".join(module_lines) if module_lines else "⏳ Verification in progress"

    funds_str = f"₹{total_funds/100_000:.1f}L" if total_funds > 0 else "None flagged"

    response = (
        f"🏫 {school.name}\n"
        f"📍 {school.block or 'N/A'}, {district_name}, {state_name}\n"
        f"📋 UDISE: {udise_code}\n\n"
        f"{modules_text}\n\n"
        f"💰 Flagged funds: {funds_str}\n"
        f"🕐 Last checked: {checked_str}\n\n"
        f"📊 Full report: schooltruth.in/{udise_code}"
    )

    if hindi:
        response = _translate_key_phrases(response)

    return response


def _district_lookup(district_name: str, db, hindi: bool) -> str:
    """Return district accountability score."""
    from app.models import District
    from sqlalchemy import func

    district = (
        db.query(District)
        .filter(District.district_name.ilike(f"%{district_name}%"))
        .first()
    )

    if not district:
        msg = f"❌ District '{district_name}' not found."
        return msg if not hindi else f"❌ '{district_name}' जिला नहीं मिला।"

    score = district.accountability_score
    emoji = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"

    response = (
        f"📍 {district.district_name}, {district.state_name}\n\n"
        f"{emoji} Accountability Score: {score:.1f}/100\n"
        f"🏫 Total Schools: {district.total_schools}\n"
        f"✅ Verified: {district.verified_schools}\n"
        f"⚠️ Flagged: {district.flagged_schools}\n\n"
        f"Full report: schooltruth.in/district/{district.district_code}"
    )

    return response


def _district_rank(district_name: str, db, hindi: bool) -> str:
    """Return national rank for a district."""
    from app.models import District
    from sqlalchemy import func

    all_districts = (
        db.query(District)
        .order_by(District.accountability_score.desc())
        .all()
    )

    target = next(
        (d for d in all_districts if district_name.lower() in d.district_name.lower()),
        None,
    )

    if not target:
        return f"❌ District '{district_name}' not found."

    rank = next(
        (i + 1 for i, d in enumerate(all_districts) if d.district_code == target.district_code),
        None,
    )

    total = len(all_districts)
    percentile = round((1 - rank / total) * 100) if rank else 0

    response = (
        f"🏆 {target.district_name}, {target.state_name}\n\n"
        f"National Rank: #{rank} of {total} districts\n"
        f"Better than {percentile}% of districts\n"
        f"Score: {target.accountability_score:.1f}/100\n\n"
        f"schooltruth.in/district/{target.district_code}"
    )
    return response


def _help_message(hindi: bool) -> str:
    eng = (
        "📚 SchoolTruth — Government School Accountability\n\n"
        "Commands:\n"
        "• Send any 11-digit UDISE code → school report\n"
        "• 'district [name]' → district score\n"
        "• 'rank [district]' → national rank\n"
        "• 'help' → this message\n\n"
        "Limit: 10 queries per day\n"
        "Website: schooltruth.in"
    )
    hin = (
        "📚 स्कूलट्रूथ — सरकारी विद्यालय जवाबदेही\n\n"
        "कमांड:\n"
        "• 11 अंकों का UDISE कोड भेजें → विद्यालय रिपोर्ट\n"
        "• 'district [नाम]' → जिला स्कोर\n"
        "• 'rank [जिला]' → राष्ट्रीय रैंक\n"
        "• 'help' → यह संदेश\n\n"
        "सीमा: प्रतिदिन 10 प्रश्न\n"
        "वेबसाइट: schooltruth.in"
    )
    return hin if hindi else eng


def _unknown_command(body: str, hindi: bool) -> str:
    if hindi:
        return (
            f"❓ आपका संदेश समझ नहीं आया: '{body[:30]}'\n"
            "UDISE कोड (11 अंक) या 'help' टाइप करें।"
        )
    return (
        f"❓ Unrecognised command: '{body[:30]}'\n"
        "Send an 11-digit UDISE code or type 'help'."
    )


def _detect_hindi(text: str) -> bool:
    """Detect if message contains Devanagari characters."""
    return bool(re.search(r"[\u0900-\u097F]", text))


def _translate_key_phrases(text: str) -> str:
    """Replace key English phrases with Hindi equivalents in response."""
    replacements = {
        "Reported:": "रिपोर्ट:",
        "Verified:": "सत्यापित:",
        "Flagged funds:": "संदिग्ध राशि:",
        "Last checked:": "अंतिम जांच:",
        "Full report:": "पूरी रिपोर्ट:",
        "days ago": "दिन पहले",
        "day ago": "दिन पहले",
        "not yet verified": "अभी सत्यापित नहीं",
        "at risk": "जोखिम में",
        "None flagged": "कोई संदिग्ध राशि नहीं",
    }
    for eng, hin in replacements.items():
        text = text.replace(eng, hin)
    return text


def _check_rate_limit(from_number: str) -> bool:
    """Return True if within limit, False if exceeded."""
    now = datetime.utcnow().timestamp()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_limit_store.get(from_number, [])
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= RATE_LIMIT_MAX:
        return False
    timestamps.append(now)
    _rate_limit_store[from_number] = timestamps
    return True


def send_whatsapp_reply(to_number: str, body: str) -> bool:
    """Send reply via Twilio WhatsApp API."""
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        logger.warning("Twilio credentials not configured — reply skipped")
        return False

    try:
        from twilio.rest import Client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}",
            body=body[:4096],  # WhatsApp message limit
        )
        logger.info(f"WhatsApp reply sent to {to_number}: SID={message.sid}")
        return True
    except Exception as exc:
        logger.error(f"Twilio send failed: {exc}")
        return False
