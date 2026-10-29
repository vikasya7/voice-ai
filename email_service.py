import base64
from email.message import EmailMessage

from googleapiclient.errors import HttpError

from google_auth import get_gmail_service


def send_email(
    to_email:str,
    subject:str,
    body:str,
)->dict:
    """Send a plain-text email using the authenticated Gmail account"""

    if not to_email or "@" not in to_email:
        raise ValueError("A valid recipient email address is required")

    message=EmailMessage()
    message["To"]=to_email
    message["subject"]=subject
    message.set_content(body)

    encoded_message=base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    service=get_gmail_service()

    try:
        result=service.users().messages().send(
            userId="me",
            body={"raw":encoded_message}
        ).execute()


        return {
            "success": True,
            "message_id": result.get("id"),
            "thread_id": result.get("threadId"),
        }
    except HttpError as exc:
        raise RuntimeError(
            f"Gmail message sending failed: {exc}"
        ) from exc


def send_booking_confirmation(
    customer_name:str,
    to_email:str,
    service_name:str,
    appointment_start:str,
    buisness_name:str="Our Team"
)->dict:
    subject=f"Appointment confirmation -{buisness_name}"
    body = (
        f"Hi {customer_name},\n\n"
        f"Your appointment has been booked successfully.\n\n"
        f"Service: {service_name}\n"
        f"Date and time: {appointment_start}\n\n"
        "If you need to reschedule or cancel, please contact us.\n\n"
        f"Regards,\n{buisness_name}"
    )

    return send_email(to_email, subject, body)