from sqlalchemy import select 
from app.database.database import SessionLocal 
from app.database.models import Appointment




def check_availability(
     appointment_date:str,
     appointment_time:str   
)->bool:
    db=SessionLocal()

    try:
        appointment=db.scalar(
            select(Appointment).where(
                Appointment.appointment_date==appointment_date,
                Appointment.appointment_time==appointment_time,
                Appointment.status=="confirmed"
            )
        )
        return appointment is None
    finally:
        db.close()


def book_appointment(
    session_id:str,
    customer_name:str,
    appointment_date:str,
    appointment_time:str,
    customer_phone:str |None=None,
    service:str | None=None
):
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
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        return {
            "success":True,
            "appointment_id":appointment.id
        }
    finally:
        db.close()
