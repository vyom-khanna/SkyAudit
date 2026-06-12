"""
APScheduler service for all periodic jobs.
Uses PostgreSQL job store for persistence across restarts.
"""
import os
import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://skyaudit:skyaudit@localhost:5432/skyaudit"
)

_scheduler: BackgroundScheduler = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        jobstores = {
            "default": SQLAlchemyJobStore(url=DATABASE_URL, tablename="apscheduler_jobs")
        }
        executors = {"default": ThreadPoolExecutor(max_workers=4)}
        _scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            timezone="Asia/Kolkata",
        )
    return _scheduler


def start_scheduler():
    """Initialise and start all scheduled jobs."""
    scheduler = get_scheduler()

    if scheduler.running:
        return

    # ── Job 1: Satellite-paced re-verification (every 5 days) ─────────────
    scheduler.add_job(
        func=_job_satellite_update,
        trigger="interval",
        days=5,
        id="satellite_update",
        name="Sentinel-2 satellite update scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    # ── Job 2: Weekly state reports (every Monday 6am IST) ────────────────
    scheduler.add_job(
        func=_job_weekly_reports,
        trigger="cron",
        day_of_week="mon",
        hour=6,
        minute=0,
        id="weekly_state_reports",
        name="Weekly state accountability reports",
        replace_existing=True,
    )

    # ── Job 2: Weekly state reports (every Monday 6am IST) ────────────────
    scheduler.add_job(
        func=_job_weekly_reports,
        trigger="cron",
        day_of_week="mon",
        hour=6,
        minute=0,
        id="weekly_state_reports",
        name="Weekly state accountability reports",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("SkyAudit scheduler started with 2 jobs")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


# ── Job implementations ──────────────────────────────────────────────────────

def _job_satellite_update():
    """Re-run verification for stale schools using new Sentinel-2 imagery."""
    from app.database import SessionLocal
    from app.services.anomaly_engine import run_scheduled

    db = SessionLocal()
    try:
        result = run_scheduled(db)
        logger.info(
            f"[satellite_update] Processed {result['processed']} schools, "
            f"{result['new_anomalies']} new anomalies at {result['run_at']}"
        )
        _log_job("satellite_update", "success", result)
    except Exception as exc:
        logger.error(f"[satellite_update] Failed: {exc}")
        _log_job("satellite_update", "error", {"error": str(exc)})
    finally:
        db.close()





def _job_weekly_reports():
    """Generate and email weekly state accountability reports."""
    from app.database import SessionLocal
    from app.models import District

    db = SessionLocal()
    try:
        states = db.query(District.state_code, District.state_name).distinct().all()
        reports_sent = 0
        for state_code, state_name in states:
            try:
                _generate_state_report(state_code, state_name, db)
                reports_sent += 1
            except Exception as exc:
                logger.error(f"State report failed for {state_code}: {exc}")

        logger.info(f"[weekly_reports] Sent {reports_sent} state reports")
        _log_job("weekly_state_reports", "success", {"reports_sent": reports_sent})
    except Exception as exc:
        logger.error(f"[weekly_reports] Failed: {exc}")
        _log_job("weekly_state_reports", "error", {"error": str(exc)})
    finally:
        db.close()








def _generate_state_report(state_code: str, state_name: str, db) -> None:
    """Generate and email weekly state report."""
    from datetime import timedelta
    from app.models import Anomaly, District, School, AnomalyStatus

    week_ago = datetime.utcnow() - timedelta(days=7)

    # New anomalies this week
    new_anomalies = (
        db.query(Anomaly)
        .join(School, Anomaly.udise_code == School.udise_code)
        .join(District, School.district_code == District.district_code)
        .filter(
            District.state_code == state_code,
            Anomaly.detected_at >= week_ago,
        )
        .all()
    )

    # Resolved this week
    resolved = (
        db.query(Anomaly)
        .join(School, Anomaly.udise_code == School.udise_code)
        .join(District, School.district_code == District.district_code)
        .filter(
            District.state_code == state_code,
            Anomaly.resolved_at >= week_ago,
            Anomaly.status == AnomalyStatus.resolved,
        )
        .all()
    )

    total_funds_new = sum(a.funds_at_risk_inr for a in new_anomalies)

    subject = (
        f"SkyAudit Weekly — {state_name} | "
        f"{datetime.utcnow().strftime('%d %b %Y')} | "
        f"{len(new_anomalies)} new anomalies | "
        f"₹{total_funds_new/10_000_000:.1f}Cr flagged"
    )

    recipients = _get_state_recipients(state_code)
    if not recipients:
        return

    html = _build_weekly_report_html(
        state_name, new_anomalies, resolved, total_funds_new
    )

    _send_email(
        to_email=recipients[0],
        cc_list=recipients[1:],
        subject=subject,
        body_html=html,
    )


def _build_weekly_report_html(state_name, new_anomalies, resolved, total_funds) -> str:
    anomaly_rows = ""
    for a in new_anomalies[:10]:
        anomaly_rows += (
            f"<tr>"
            f"<td style='padding:6px;'>{a.udise_code}</td>"
            f"<td style='padding:6px;'>{a.anomaly_type.value.replace('_',' ').title()}</td>"
            f"<td style='padding:6px;'>{a.severity.value.upper()}</td>"
            f"<td style='padding:6px;color:#c0392b;font-weight:bold;'>₹{a.funds_at_risk_inr/100_000:.1f}L</td>"
            f"</tr>"
        )

    return f"""
<html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;">
<div style="background:#2c3e50;color:white;padding:20px;">
  <h1 style="margin:0;">SkyAudit Weekly Report</h1>
  <p style="margin:5px 0;">{state_name} | {datetime.utcnow().strftime('%d %B %Y')}</p>
</div>
<div style="padding:20px;">
  <div style="display:flex;gap:20px;margin-bottom:20px;">
    <div style="background:#e74c3c;color:white;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:28px;font-weight:bold;">{len(new_anomalies)}</div>
      <div>New Anomalies</div>
    </div>
    <div style="background:#e67e22;color:white;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:28px;font-weight:bold;">₹{total_funds/10_000_000:.1f}Cr</div>
      <div>Newly Flagged</div>
    </div>
    <div style="background:#27ae60;color:white;padding:15px;border-radius:6px;flex:1;text-align:center;">
      <div style="font-size:28px;font-weight:bold;">{len(resolved)}</div>
      <div>Resolved</div>
    </div>
  </div>
  <h2>Top New Cases</h2>
  <table style="width:100%;border-collapse:collapse;border:1px solid #ddd;">
    <thead>
      <tr style="background:#f5f5f5;">
        <th style="padding:8px;text-align:left;">UDISE Code</th>
        <th style="padding:8px;text-align:left;">Type</th>
        <th style="padding:8px;text-align:left;">Severity</th>
        <th style="padding:8px;text-align:left;">Funds at Risk</th>
      </tr>
    </thead>
    <tbody>{anomaly_rows}</tbody>
  </table>
  <p style="margin-top:20px;font-size:12px;color:#666;">
    Full report: <a href="https://skyaudit.in">skyaudit.in</a>
  </p>
</div>
</body></html>
"""


def _get_state_recipients(state_code: str):
    """Return pre-configured recipient list for a state."""
    config = {
        "UP": [
            os.getenv("UP_EDUCATION_SEC_EMAIL", "education-sec@up.gov.in"),
            os.getenv("UP_JOURNALIST_1", "education@hindustantimes.com"),
        ],
        "Bihar": [os.getenv("BR_EDUCATION_SEC_EMAIL", "education-sec@bihar.gov.in")],
    }
    return config.get(state_code, [])


def _log_job(job_id: str, status: str, result: dict) -> None:
    logger.info(f"JOB [{job_id}] status={status} result={result}")


def _send_email(
    to_email: str,
    cc_list: list,
    subject: str,
    body_html: str,
) -> None:
    """Send email via SendGrid API."""
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "notices@skyaudit.in")
    
    if not SENDGRID_API_KEY:
        logger.warning(f"SENDGRID_API_KEY not set — email to {to_email} skipped")
        return

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=body_html,
        )

        for cc_email in cc_list:
            if cc_email and cc_email != to_email:
                message.add_cc(cc_email)

        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info(f"Email sent to {to_email} — status {response.status_code}")

    except Exception as exc:
        logger.error(f"SendGrid email failed: {exc}")
