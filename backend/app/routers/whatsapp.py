from fastapi import APIRouter, Depends, Form, Response, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.whatsapp_bot import handle_message, send_whatsapp_reply

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    MessageSid: str = Form(default=""),
    db: Session = Depends(get_db),
):
    """
    Receive incoming WhatsApp messages via Twilio webhook.
    Parse command, fetch data, reply in Hindi or English.
    """
    from_number = From.replace("whatsapp:", "")
    message_body = Body.strip()

    response_text = handle_message(from_number, message_body, db)

    # Send reply via Twilio
    send_whatsapp_reply(From, response_text)

    # Return TwiML response (empty — reply sent via API, not TwiML)
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


@router.get("/webhook")
async def whatsapp_webhook_verify(request: Request):
    """Twilio webhook verification endpoint."""
    return {"status": "SchoolTruth WhatsApp webhook active"}
