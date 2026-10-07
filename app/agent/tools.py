from sqlalchemy import select 
from app.database.database import SessionLocal 
from app.database.models import Appointment
from app.database.models import Lead,HumanHandoff,ConversationLog
from langchain_core.tools import tool
from sqlalchemy.exc import IntegrityError

@tool
def check_availability(
    appointment_date: str,
    appointment_time: str,
) -> bool:
    """
    Check whether an appointment slot is available.

    Args:
        appointment_date: Date of the appointment.
        appointment_time: Time of the appointment.

    Returns:
        True if the slot is available, otherwise False.
    """

    db = SessionLocal()

    try:
        appointment = db.scalar(
            select(Appointment).where(
                Appointment.appointment_date == appointment_date,
                Appointment.appointment_time == appointment_time,
                Appointment.status == "confirmed",
            )
        )

        return appointment is None

    finally:
        db.close()

@tool
def book_appointment(
    session_id:str,
    customer_name:str,
    appointment_date:str,
    appointment_time:str,
    customer_phone:str |None=None,
    service:str | None=None
):
    """
    Create a new appointment in the database after
    the customer has confirmed the booking.

    Args:
        session_id: Unique conversation identifier.
        customer_name: Name of the customer.
        customer_phone: Customer's phone number.
        appointment_date: Date in YYYY-MM-DD format.
        appointment_time: Time in HH:MM format.
        service: Service requested by the customer.
    """
    db=SessionLocal()

    try:
        existing=db.scalar(
            select(Appointment).where(
                Appointment.appointment_date==appointment_date,
                Appointment.appointment_time==appointment_time,
                Appointment.status=="confirmed"
            )
        )
        if existing:
            return {
                "success":False,
                "message":"This appointment slot is no longer available"
            }
        appointment=Appointment(
            session_id=session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            service=service,
            status="confirmed"
        )
        # for race condition if two persons try to book at same time
        db.add(appointment)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

            return {
                "success":False,
                "message": (
                    "Sorry, this appointment slot was just booked "
                    "by someone else."
                ),
            }
        db.refresh(appointment)

        return {
            "success":True,
            "appointment_id":appointment.id
        }
    except Exception:
        db.rollback()

        return {
            "success": False,
            "message": (
                "Sorry, something went wrong while booking "
                "the appointment."
            ),
        }
    finally:
        db.close()


@tool
def find_appointment(
    customer_phone: str,
    appointment_date: str | None = None,
    appointment_time: str | None = None,
):
    """
    Find a confirmed appointment using the customer's phone number,
    and optionally the appointment date and time.

    Args:
        customer_phone: Phone number associated with the appointment.
        appointment_date: Appointment date, if known.
        appointment_time: Appointment time, if known.

    Returns:
        The matching appointment, or None if no appointment is found.
    """

    db = SessionLocal()

    try:
        query = select(Appointment).where(
            Appointment.customer_phone == customer_phone,
            Appointment.status == "confirmed",
        )

        if appointment_date:
            query = query.where(
                Appointment.appointment_date == appointment_date
            )

        if appointment_time:
            query = query.where(
                Appointment.appointment_time == appointment_time
            )

        return db.scalar(query)

    finally:
        db.close()

@tool
def cancel_appointment(appointment_id: int):
    """
    Cancel an existing appointment using its appointment ID.

    Args:
        appointment_id: ID of the appointment to cancel.

    Returns:
        A dictionary containing the cancellation result.
    """

    db = SessionLocal()

    try:
        appointment = db.get(Appointment, appointment_id)

        if not appointment:
            return {
                "success": False,
                "message": "Appointment not found."
            }

        appointment.status = "cancelled"
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

            return {
                "success": False,
                "message": "Unable to cancel the appointment.",
            }
 
        

        return {
            "success": True,
            "appointment_id": appointment.id
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "message": "Sorry, something went wrong while cancelling the appointment.",
        }

    finally:
        db.close()


@tool
def reschedule_appointment(
    appointment_id: int,
    new_date: str,
    new_time: str,
):
    """
    Reschedule an existing appointment to a new date and time.

    Args:
        appointment_id: ID of the appointment to reschedule.
        new_date: New appointment date.
        new_time: New appointment time.

    Returns:
        A dictionary containing the rescheduling result.
    """

    # Keep your existing database logic here
    db=SessionLocal()

    try:
        # fist finding the appointment
        appointment=db.get(Appointment,appointment_id)

        if not appointment:
            return {
                "success":False,
                "message":"Appointment not found"
            }
        # check another appointment is there or not

        conflicting_appointment=db.scalar(
            select(Appointment).where(
                Appointment.appointment_date==new_date,
                Appointment.appointment_time==new_time,
                Appointment.status=="confirmed",
                Appointment.id!=appointment_id
            )
        )
        if conflicting_appointment:
            return {
                "success":False,
                "message":(
                    f"The slot at {new_time} on {new_date} "
                    "is already booked."
                )
            }
        # Update appointment
        appointment.appointment_date = new_date
        appointment.appointment_time = new_time
        try:
            db.commit()
        except IntegrityError:
            db.rollback()

            return {
                "success": False,
                "message": (
                    "Sorry, that appointment slot was just "
                    "booked by someone else."
                ),
            }

        
        db.refresh(appointment)

        return {
            "success": True,
            "appointment_id": appointment.id,
            "new_date": appointment.appointment_date,
            "new_time": appointment.appointment_time,
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "message": (
                "Sorry, something went wrong while "
                "rescheduling the appointment."
            ),
        }

    finally:
        db.close()
    
        



@tool
def save_lead(
    session_id: str,
    customer_name: str,
    customer_phone: str,
    service: str,
    preferred_time: str,
    requirement: str | None = None,
):
    """
    Save a customer's lead information into the database.

    Args:
        session_id: Unique conversation/session ID.
        customer_name: Customer's name.
        customer_phone: Customer's phone number.
        service: Service the customer is interested in.
        preferred_time: Customer's preferred visit time.
        requirement: Additional customer requirement, if provided.

    Returns:
        A dictionary containing the lead creation result.
    """

    db = SessionLocal()

    try:
        lead = Lead(
            session_id=session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            service=service,
            preferred_time=preferred_time,
            requirement=requirement,
            status="new",
        )

        db.add(lead)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return {
                "success": False,
                "message": "Unable to save the lead information.",
            }

        
        db.refresh(lead)

        return {
            "success": True,
            "lead_id": lead.id,
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "message": (
                "Sorry, something went wrong while saving "
                "your information."
            ),
        }

    finally:
        db.close()



@tool
def create_human_handoff(
    session_id:str,
    customer_name:str | None=None,
    customer_phone:str | None=None,
    reason:str | None=None
):
    """
    Create a request for a human staff member to contact or assist the customer.

    Args:
        session_id: Unique conversation/session ID.
        customer_name: Customer's name, if known.
        customer_phone: Customer's phone number, if known.
        reason: Reason why the customer wants human assistance.

    Returns:
        A dictionary containing the handoff request result.
    """

    db = SessionLocal()

    try:
        handoff = HumanHandoff(
            session_id=session_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            reason=reason,
            status="pending",
        )

        db.add(handoff)
        db.commit()
        db.refresh(handoff)

        return {
            "success": True,
            "handoff_id": handoff.id,
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "message": str(e),
        }

    finally:
        db.close()
    
    

@tool
def log_conversation(
    session_id: str,
    customer_message: str,
    agent_response: str,
    intent: str | None = None,
):
    """
    Save a customer-agent interaction to the conversation log.

    Args:
        session_id: Unique conversation/session ID.
        customer_message: Message sent by the customer.
        agent_response: Response generated by the agent.
        intent: Detected customer intent.
    """

    db = SessionLocal()

    try:
        log = ConversationLog(
            session_id=session_id,
            customer_message=customer_message,
            agent_response=agent_response,
            intent=intent,
        )

        db.add(log)
        db.commit()
        db.refresh(log)

        return {
            "success": True,
            "log_id": log.id,
        }

    except Exception as e:
        db.rollback()

        return {
            "success": False,
            "message": str(e),
        }

    finally:
        db.close()