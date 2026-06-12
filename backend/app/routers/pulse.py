import asyncio
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db, SessionLocal
from app.models import PulseEvent
from app.schemas import PulseEventOut

router = APIRouter(prefix="/pulse", tags=["pulse"])


@router.get("/", response_model=List[PulseEventOut])
def get_pulse_events(
    state: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Latest pulse events with filters."""
    query = (
        db.query(PulseEvent)
        .filter(PulseEvent.is_published == True)
        .order_by(desc(PulseEvent.created_at))
    )

    if state:
        query = query.filter(PulseEvent.state_name.ilike(f"%{state}%"))

    if event_type:
        query = query.filter(PulseEvent.event_type == event_type)

    events = query.offset(offset).limit(limit).all()
    return [PulseEventOut.model_validate(e) for e in events]


@router.get("/stream")
async def pulse_stream(
    state: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
):
    """
    Server-Sent Events stream for real-time pulse feed.
    Polls every 10 seconds for new events.
    """
    async def event_generator():
        last_id = None
        retry_interval = 10  # seconds

        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'message': 'SkyAudit pulse stream connected'})}\n\n"

        while True:
            try:
                db = SessionLocal()
                try:
                    query = (
                        db.query(PulseEvent)
                        .filter(PulseEvent.is_published == True)
                        .order_by(desc(PulseEvent.created_at))
                    )

                    if last_id is not None:
                        query = query.filter(PulseEvent.id > last_id)

                    if state:
                        query = query.filter(PulseEvent.state_name.ilike(f"%{state}%"))

                    if event_type:
                        query = query.filter(PulseEvent.event_type == event_type)

                    new_events = query.limit(10).all()

                    for event in reversed(new_events):
                        last_id = max(last_id or 0, event.id)
                        event_data = {
                            "id": event.id,
                            "anomaly_id": event.anomaly_id,
                            "event_type": event.event_type,
                            "headline": event.headline,
                            "summary": event.summary,
                            "funds_mentioned_inr": event.funds_mentioned_inr,
                            "school_name": event.school_name,
                            "district_name": event.district_name,
                            "state_name": event.state_name,
                            "udise_code": event.udise_code,
                            "satellite_url": event.satellite_url,
                            "created_at": event.created_at.isoformat() if event.created_at else None,
                        }
                        yield f"id: {event.id}\ndata: {json.dumps(event_data)}\n\n"

                    # Keep-alive heartbeat
                    if not new_events:
                        yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"

                finally:
                    db.close()

            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

            await asyncio.sleep(retry_interval)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )
