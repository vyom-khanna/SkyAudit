from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from app.database import get_db
from app.models import Anomaly, School, District, Notice, AnomalyStatus
from app.schemas import AnomalyOut, AnomalyStatusUpdate, NoticeOut
from app.routers.auth import get_current_officer

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("/", response_model=List[AnomalyOut])
def list_anomalies(
    state: Optional[str] = Query(None),
    anomaly_type: Optional[str] = Query(None),
    anomaly_status: Optional[str] = Query(None),
    min_funds: Optional[float] = Query(None),
    district_code: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List anomalies with flexible filtering.
    ?state=UP&type=ghost_school&status=new&min_funds=100000
    """
    query = db.query(Anomaly).join(School, Anomaly.udise_code == School.udise_code)

    if state or district_code:
        query = query.join(District, School.district_code == District.district_code)
        if state:
            query = query.filter(District.state_code == state)
        if district_code:
            query = query.filter(District.district_code == district_code)

    if anomaly_type:
        query = query.filter(Anomaly.anomaly_type == anomaly_type)

    if anomaly_status:
        query = query.filter(Anomaly.status == anomaly_status)

    if min_funds is not None:
        query = query.filter(Anomaly.funds_at_risk_inr >= min_funds)

    if severity:
        query = query.filter(Anomaly.severity == severity)

    anomalies = (
        query.order_by(desc(Anomaly.detected_at)).offset(offset).limit(limit).all()
    )
    return [AnomalyOut.model_validate(a) for a in anomalies]


@router.get("/{anomaly_id}", response_model=dict)
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)):
    """Full anomaly details with evidence, notice history, and escalation timeline."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail=f"Anomaly {anomaly_id} not found")

    school = db.query(School).filter(School.udise_code == anomaly.udise_code).first()
    district = (
        db.query(District).filter(District.district_code == school.district_code).first()
        if school
        else None
    )

    notices = (
        db.query(Notice)
        .filter(Notice.anomaly_id == anomaly_id)
        .order_by(Notice.sent_at)
        .all()
    )

    # Days until escalation
    days_until_escalation = None
    if anomaly.response_due_at and anomaly.status == AnomalyStatus.noticed:
        days_remaining = (anomaly.response_due_at - datetime.utcnow()).days
        days_until_escalation = max(0, days_remaining)

    # Build escalation timeline
    timeline = _build_timeline(anomaly, notices)

    return {
        "anomaly": AnomalyOut.model_validate(anomaly),
        "school": {
            "name": school.name if school else None,
            "block": school.block if school else None,
            "udise_code": anomaly.udise_code,
        },
        "district": {
            "name": district.district_name if district else None,
            "state": district.state_name if district else None,
        },
        "notices": [NoticeOut.model_validate(n) for n in notices],
        "days_until_escalation": days_until_escalation,
        "escalation_timeline": timeline,
    }


@router.patch("/{anomaly_id}/status", response_model=AnomalyOut)
def update_anomaly_status(
    anomaly_id: int,
    update: AnomalyStatusUpdate,
    db: Session = Depends(get_db),
    officer=Depends(get_current_officer),
):
    """Update anomaly status — requires officer authentication."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    # Officers can only update anomalies in their district
    if officer.district_code:
        school = db.query(School).filter(School.udise_code == anomaly.udise_code).first()
        if school and school.district_code != officer.district_code:
            raise HTTPException(
                status_code=403,
                detail="You can only update anomalies in your district",
            )

    old_status = anomaly.status
    anomaly.status = update.status

    if update.status == AnomalyStatus.resolved:
        anomaly.resolved_at = datetime.utcnow()

    # Log status change in evidence_json
    history = anomaly.evidence_json or {}
    changes = history.get("status_changes", [])
    changes.append(
        {
            "from": old_status.value if old_status else None,
            "to": update.status.value,
            "by": officer.email,
            "at": datetime.utcnow().isoformat(),
            "response": update.response_text,
            "evidence_url": update.evidence_url,
        }
    )
    history["status_changes"] = changes
    anomaly.evidence_json = history

    # Update notice if response provided
    if update.response_text:
        notice = (
            db.query(Notice)
            .filter(Notice.anomaly_id == anomaly_id)
            .order_by(Notice.sent_at.desc())
            .first()
        )
        if notice:
            notice.response_received = True
            notice.response_text = update.response_text

    db.commit()
    db.refresh(anomaly)
    return AnomalyOut.model_validate(anomaly)


def _build_timeline(anomaly: Anomaly, notices: list) -> list:
    """Build escalation timeline for ResponseTracker component."""
    timeline = [
        {
            "day": 0,
            "event": "Anomaly detected",
            "timestamp": anomaly.detected_at.isoformat() if anomaly.detected_at else None,
            "status": "completed",
        }
    ]

    if anomaly.notice_sent_at:
        timeline.append(
            {
                "day": 0,
                "event": f"Notice sent to {notices[0].sent_to if notices else 'DEO'}",
                "timestamp": anomaly.notice_sent_at.isoformat(),
                "status": "completed",
            }
        )

    if anomaly.response_due_at:
        now = datetime.utcnow()
        is_overdue = now > anomaly.response_due_at
        response_received = any(n.response_received for n in notices)

        timeline.append(
            {
                "day": 30,
                "event": "DEO response due",
                "timestamp": anomaly.response_due_at.isoformat(),
                "status": "completed" if response_received else ("overdue" if is_overdue else "pending"),
                "days_remaining": max(0, (anomaly.response_due_at - now).days) if not is_overdue else None,
            }
        )

        escalated = any(n.escalation_level >= 2 for n in notices)
        if is_overdue and not response_received:
            timeline.append(
                {
                    "day": 30,
                    "event": "Escalated to State Education Secretary",
                    "timestamp": None,
                    "status": "completed" if escalated else "pending",
                }
            )

        day60_deadline = anomaly.response_due_at + timedelta(days=30)
        rti_due = now > day60_deadline
        timeline.append(
            {
                "day": 60,
                "event": "RTI auto-filed",
                "timestamp": day60_deadline.isoformat(),
                "status": "completed" if rti_due and not response_received else "pending",
            }
        )

        day90_deadline = anomaly.response_due_at + timedelta(days=60)
        timeline.append(
            {
                "day": 90,
                "event": "Added to Hall of Shame",
                "timestamp": day90_deadline.isoformat(),
                "status": "completed" if now > day90_deadline and not response_received else "pending",
            }
        )

    return timeline
