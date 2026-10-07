from datetime import datetime

from sqlalchemy import String, DateTime,Text,Index,text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import UniqueConstraint
from app.database.database import Base


class Appointment(Base):
    __tablename__ = "appointment"
    # it will prevent two appointments from using same date and time
    __table_args__ = (
        Index(
            "uq_confirmed_appointment_datetime",
            "appointment_date",
            "appointment_time",
            unique=True,
            postgresql_where=text("status = 'confirmed'"),
        ),
    )

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



class Lead(Base):
    __tablename__ = "lead"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    service: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    preferred_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    requirement: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="new"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )



class HumanHandoff(Base):
    __tablename__ = "human_handoff"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    customer_phone: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )



class ConversationLog(Base):
    __tablename__ = "conversation_log"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True
    )

    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    customer_message: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    agent_response: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    intent: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )