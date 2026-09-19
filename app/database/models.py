from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class Appointment(Base):
    __tablename__ = "appointment"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    appointment_date: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    appointment_time: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    service: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="confirmed"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )