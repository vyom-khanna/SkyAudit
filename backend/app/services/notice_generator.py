"""
Notice Generator: creates official PDFs, sends via email, handles escalation.
"""
import os
import io
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.models import Anomaly, Notice, School, District, PulseEvent, AnomalyStatus

logger = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "notices@schooltruth.in")
STORAGE_BASE = os.getenv("NOTICE_STORAGE_PATH", "/tmp/notices")

ESCALATION_DAYS = {1: 30, 2: 60, 3: 90}

OFFICER_EMAILS = {
    "DEO": os.getenv("DEO_EMAIL_TEMPLATE", "deo-{district}@education.gov.in"),
    "State": os.getenv("STATE_EDUCATION_EMAIL", "education-secretary@state.gov.in"),
    "Ministry": "education-ministry@nic.in",
}


def generate_notice(anomaly_id: int, db: Session) -> int:
    """
    Generate official notice PDF, email it to correct officer, persist to DB.

    Returns notice_id.
    """
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise ValueError(f"Anomaly {anomaly_id} not found")

    school = db.query(School).filter(School.udise_code == anomaly.udise_code).first()
    district = (
        db.query(District).filter(District.district_code == school.district_code).first()
        if school
        else None
    )

    severity = anomaly.severity.value if anomaly.severity else "medium"
    sent_to, cc_list = _determine_recipients(severity, district)

    pdf_bytes = _generate_pdf(anomaly, school, district, sent_to)
    pdf_url = _save_pdf(pdf_bytes, anomaly_id)

    response_deadline = datetime.utcnow() + timedelta(days=30)
    notice = Notice(
        anomaly_id=anomaly_id,
        sent_to=sent_to,
        sent_at=datetime.utcnow(),
        response_deadline=response_deadline,
        response_received=False,
        cc_list=cc_list,
        escalation_level=1,
    )
    db.add(notice)

    anomaly.notice_sent_at = datetime.utcnow()
    anomaly.response_due_at = response_deadline
    anomaly.status = AnomalyStatus.noticed
    db.commit()
    db.refresh(notice)

    _send_email(
        to_email=sent_to,
        cc_list=cc_list,
        subject=_build_subject(anomaly, school, district),
        body_html=_build_email_html(anomaly, school, district, notice),
        attachment_bytes=pdf_bytes,
        attachment_name=f"SchoolTruth_Notice_{anomaly_id}.pdf",
    )

    return notice.id


def check_escalations(db: Session) -> int:
    """
    Find overdue notices and escalate per schedule.
    Called daily by the scheduler.

    Returns count of escalations triggered.
    """
    now = datetime.utcnow()
    escalated = 0

    overdue_notices = (
        db.query(Notice)
        .filter(
            Notice.response_received == False,
            Notice.response_deadline < now,
        )
        .all()
    )

    for notice in overdue_notices:
        anomaly = db.query(Anomaly).filter(Anomaly.id == notice.anomaly_id).first()
        if not anomaly:
            continue

        days_overdue = (now - notice.response_deadline).days
        current_level = notice.escalation_level

        if days_overdue >= 60 and current_level < 3:
            _escalate_to_level(notice, anomaly, 3, "Ministry", db)
            generate_rti(anomaly.id, db)
            escalated += 1
        elif days_overdue >= 30 and current_level < 2:
            _escalate_to_level(notice, anomaly, 2, "State", db)
            escalated += 1

    db.commit()
    return escalated


def _escalate_to_level(
    notice: Notice,
    anomaly: Anomaly,
    level: int,
    recipient: str,
    db: Session,
) -> None:
    notice.escalation_level = level
    notice.sent_to = recipient

    school = db.query(School).filter(School.udise_code == anomaly.udise_code).first()
    district = (
        db.query(District).filter(District.district_code == school.district_code).first()
        if school
        else None
    )

    level_labels = {2: "State Education Secretary", 3: "Ministry of Education + RTI"}
    logger.warning(
        f"Escalating anomaly {anomaly.id} to level {level} ({level_labels.get(level, recipient)})"
    )

    if level == 3:
        # Add to public pulse event as "Hall of Shame"
        event = PulseEvent(
            anomaly_id=anomaly.id,
            event_type="hall_of_shame",
            headline=f"UNRESOLVED 90 DAYS: {school.name if school else anomaly.udise_code}",
            summary=(
                f"Anomaly detected {anomaly.detected_at.strftime('%b %Y')} "
                f"remains unresolved after 90 days of official notices."
            ),
            funds_mentioned_inr=anomaly.funds_at_risk_inr,
            school_name=school.name if school else anomaly.udise_code,
            district_name=district.district_name if district else "",
            state_name=district.state_name if district else "",
            created_at=datetime.utcnow(),
            is_published=True,
        )
        db.add(event)


def generate_rti(anomaly_id: int, db: Session) -> str:
    """
    Auto-generate RTI application text for an unresolved anomaly.
    Returns formatted RTI text.
    """
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        return ""

    school = db.query(School).filter(School.udise_code == anomaly.udise_code).first()
    district = (
        db.query(District).filter(District.district_code == school.district_code).first()
        if school
        else None
    )

    district_name = district.district_name if district else "Unknown"
    state_name = district.state_name if district else "Unknown"
    school_name = school.name if school else anomaly.udise_code
    detected_date = anomaly.detected_at.strftime("%d %B %Y")

    rti_text = f"""
RIGHT TO INFORMATION ACT, 2005 — APPLICATION

To,
The Public Information Officer,
Department of School Education,
{state_name}

Subject: Information regarding government school {school_name} 
         (UDISE Code: {anomaly.udise_code}), {district_name} — 
         Anomaly Type: {anomaly.anomaly_type.value.replace('_', ' ').title()}

Sir/Madam,

Under the Right to Information Act, 2005, I hereby request the following 
information regarding Government School {school_name} (UDISE Code: {anomaly.udise_code}),
located in {district_name} district, {state_name}:

1. Attendance records for all enrolled students for the past 12 months.
2. Salary disbursement records for all {school.reported_teachers if school else 'N/A'} 
   listed teachers for the past 12 months.
3. Mid-Day Meal claim records and beneficiary lists for the past 12 months.
4. Construction completion certificates for all Samagra Shiksha grants sanctioned 
   to this school in the past 5 years.
5. Physical inspection reports if any have been conducted in the past 3 years.
6. Copies of all utilisation certificates submitted for government grants.

Background: SchoolTruth platform detected a potential 
{anomaly.anomaly_type.value.replace('_', ' ')} anomaly on {detected_date} 
with estimated ₹{anomaly.funds_at_risk_inr/100_000:.1f} lakh in public funds at risk 
(confidence: {anomaly.confidence*100:.0f}%).

Evidence:
- Satellite imagery: {anomaly.satellite_before_url or 'Available on request'}
- Reported enrollment: per UDISE+ database
- Anomaly description: {anomaly.description[:200] if anomaly.description else 'See attached notice'}

I am willing to pay the prescribed fee for obtaining this information.

Yours faithfully,
SchoolTruth Platform (automated RTI)
schooltruth.in
Date: {datetime.utcnow().strftime('%d %B %Y')}
"""
    return rti_text.strip()


# ── PDF generation ───────────────────────────────────────────────────────────

def _generate_pdf(
    anomaly: Anomaly,
    school: Optional[School],
    district: Optional[District],
    recipient: str,
) -> bytes:
    """Generate official notice PDF using reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.lib import colors

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()

        elements = []

        # Header
        elements.append(Paragraph("<b>SCHOOLTRUTH ACCOUNTABILITY PLATFORM</b>", styles["Title"]))
        elements.append(Paragraph("Official Irregularity Notice", styles["Heading2"]))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.red))
        elements.append(Spacer(1, 0.3*cm))

        # Notice metadata
        meta_data = [
            ["Notice Date:", datetime.utcnow().strftime("%d %B %Y")],
            ["Reference No:", f"ST-{anomaly.id:06d}"],
            ["Addressed To:", recipient],
            ["Severity:", anomaly.severity.value.upper() if anomaly.severity else "MEDIUM"],
            ["Confidence:", f"{anomaly.confidence*100:.0f}%"],
        ]
        meta_table = Table(meta_data, colWidths=[4*cm, 12*cm])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 0.5*cm))

        # School info
        elements.append(Paragraph("<b>School Details</b>", styles["Heading3"]))
        school_data = [
            ["School Name:", school.name if school else anomaly.udise_code],
            ["UDISE Code:", anomaly.udise_code],
            ["District:", district.district_name if district else "Unknown"],
            ["State:", district.state_name if district else "Unknown"],
            ["Block:", school.block if school else "Unknown"],
        ]
        school_table = Table(school_data, colWidths=[4*cm, 12*cm])
        school_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("BACKGROUND", (0, 0), (-1, -1), colors.lightyellow),
        ]))
        elements.append(school_table)
        elements.append(Spacer(1, 0.5*cm))

        # Anomaly details
        elements.append(Paragraph("<b>Anomaly Details</b>", styles["Heading3"]))
        anomaly_data = [
            ["Type:", anomaly.anomaly_type.value.replace("_", " ").title()],
            ["Detected:", anomaly.detected_at.strftime("%d %B %Y")],
            ["Funds at Risk:", f"₹{anomaly.funds_at_risk_inr:,.0f}"],
            ["Description:", anomaly.description[:300] if anomaly.description else "See evidence"],
        ]
        anomaly_table = Table(anomaly_data, colWidths=[4*cm, 12*cm])
        anomaly_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightcoral),
        ]))
        elements.append(anomaly_table)
        elements.append(Spacer(1, 0.5*cm))

        # Evidence
        if anomaly.satellite_before_url:
            elements.append(Paragraph(
                f"<b>Satellite Evidence:</b> {anomaly.satellite_before_url}",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 0.3*cm))

        # Required action
        elements.append(Paragraph("<b>Required Action</b>", styles["Heading3"]))
        elements.append(Paragraph(
            "The responsible officer is required to submit a written response within "
            "<b>30 days</b> of receipt of this notice. Failure to respond will result in "
            "escalation to the State Education Secretary on Day 30, RTI filing on Day 60, "
            "and public listing on SchoolTruth Hall of Shame on Day 90.",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 0.5*cm))

        elements.append(Paragraph(
            "Send response to: <b>notices@schooltruth.in</b> | schooltruth.in",
            styles["Normal"]
        ))

        doc.build(elements)
        return buf.getvalue()

    except ImportError:
        logger.warning("reportlab not available — returning empty PDF placeholder")
        return b"%PDF-1.4 placeholder"


def _save_pdf(pdf_bytes: bytes, anomaly_id: int) -> str:
    """Save PDF to storage and return URL."""
    os.makedirs(STORAGE_BASE, exist_ok=True)
    filename = f"notice_{anomaly_id}_{datetime.utcnow().strftime('%Y%m%d')}.pdf"
    path = os.path.join(STORAGE_BASE, filename)
    with open(path, "wb") as f:
        f.write(pdf_bytes)
    return f"https://schooltruth.in/notices/{filename}"


def _determine_recipients(severity: str, district: Optional[District]):
    district_code = district.district_code if district else "unknown"
    if severity == "critical":
        sent_to = "Ministry"
        cc_list = [
            OFFICER_EMAILS["DEO"].format(district=district_code),
            OFFICER_EMAILS["State"],
            OFFICER_EMAILS["Ministry"],
        ]
    elif severity == "high":
        sent_to = "State"
        cc_list = [
            OFFICER_EMAILS["DEO"].format(district=district_code),
            OFFICER_EMAILS["State"],
        ]
    else:
        sent_to = "DEO"
        cc_list = [OFFICER_EMAILS["DEO"].format(district=district_code)]

    return sent_to, cc_list


def _build_subject(anomaly: Anomaly, school: Optional[School], district: Optional[District]) -> str:
    school_name = school.name if school else anomaly.udise_code
    district_name = district.district_name if district else ""
    return (
        f"[SchoolTruth Notice] {anomaly.severity.value.upper()} — "
        f"{anomaly.anomaly_type.value.replace('_', ' ').title()} at "
        f"{school_name}, {district_name} | ₹{anomaly.funds_at_risk_inr/100_000:.1f}L at risk"
    )


def _build_email_html(
    anomaly: Anomaly,
    school: Optional[School],
    district: Optional[District],
    notice: Notice,
) -> str:
    school_name = school.name if school else anomaly.udise_code
    district_name = district.district_name if district else "Unknown"
    state_name = district.state_name if district else "Unknown"
    deadline = notice.response_deadline.strftime("%d %B %Y")

    return f"""
<html><body style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto;">
<div style="background:#c0392b; color:white; padding:20px; text-align:center;">
  <h1 style="margin:0;">SchoolTruth Official Notice</h1>
  <p style="margin:5px 0;">Severity: {anomaly.severity.value.upper()}</p>
</div>
<div style="padding:20px; border:1px solid #ddd;">
  <h2>{anomaly.anomaly_type.value.replace('_',' ').title()} Detected</h2>
  <table style="width:100%; border-collapse:collapse;">
    <tr><td style="font-weight:bold;padding:8px;background:#f5f5f5;">School</td>
        <td style="padding:8px;">{school_name}</td></tr>
    <tr><td style="font-weight:bold;padding:8px;background:#f5f5f5;">UDISE Code</td>
        <td style="padding:8px;">{anomaly.udise_code}</td></tr>
    <tr><td style="font-weight:bold;padding:8px;background:#f5f5f5;">District / State</td>
        <td style="padding:8px;">{district_name}, {state_name}</td></tr>
    <tr><td style="font-weight:bold;padding:8px;background:#f5f5f5;">Funds at Risk</td>
        <td style="padding:8px; color:#c0392b; font-weight:bold;">
          ₹{anomaly.funds_at_risk_inr/100_000:.1f} Lakh</td></tr>
    <tr><td style="font-weight:bold;padding:8px;background:#f5f5f5;">Response Deadline</td>
        <td style="padding:8px; font-weight:bold;">{deadline}</td></tr>
  </table>
  <div style="margin-top:20px; padding:15px; background:#fff3cd; border-left:4px solid #ffc107;">
    <strong>Summary:</strong> {anomaly.description or 'See attached PDF for full details.'}
  </div>
  {"<div style='margin-top:15px;'><img src='" + anomaly.satellite_before_url + "' style='max-width:100%;' alt='Satellite evidence'/></div>" if anomaly.satellite_before_url else ""}
  <div style="margin-top:20px; padding:15px; background:#f8d7da; border-left:4px solid #dc3545;">
    <strong>Action Required:</strong> Respond within 30 days to notices@schooltruth.in
    or via schooltruth.in. Failure to respond triggers automatic escalation.
  </div>
  <p style="margin-top:20px; font-size:12px; color:#666;">
    Full report: <a href="https://schooltruth.in/{anomaly.udise_code}">
    schooltruth.in/{anomaly.udise_code}</a>
  </p>
</div>
</body></html>
"""


def _send_email(
    to_email: str,
    cc_list: List[str],
    subject: str,
    body_html: str,
    attachment_bytes: bytes,
    attachment_name: str,
) -> None:
    """Send email via SendGrid API."""
    if not SENDGRID_API_KEY:
        logger.warning(f"SENDGRID_API_KEY not set — email to {to_email} skipped")
        return

    try:
        import base64
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail, Attachment, FileContent, FileName,
            FileType, Disposition, To
        )

        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=body_html,
        )

        for cc_email in cc_list:
            if cc_email and cc_email != to_email:
                message.add_cc(cc_email)

        attachment = Attachment(
            FileContent(base64.b64encode(attachment_bytes).decode()),
            FileName(attachment_name),
            FileType("application/pdf"),
            Disposition("attachment"),
        )
        message.attachment = attachment

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email} — status {response.status_code}")

    except Exception as exc:
        logger.error(f"SendGrid email failed: {exc}")
