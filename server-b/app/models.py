import enum
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column

Base = declarative_base()


class MessageStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"


class EventType(str, enum.Enum):
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    DELIVERED = "DELIVERED"
    PROVIDER_SWITCHED = "PROVIDER_SWITCHED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String, unique=True, default=lambda: str(uuid.uuid4()))
    client_key: Mapped[str] = mapped_column(String)
    to: Mapped[str] = mapped_column(String)
    text: Mapped[str] = mapped_column(String)
    ttl_seconds: Mapped[int] = mapped_column(Integer)
    provider_final: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus), default=MessageStatus.QUEUED)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events: Mapped[list["MessageEvent"]] = relationship(
        "MessageEvent", back_populates="message", cascade="all, delete-orphan"
    )


class MessageEvent(Base):
    __tablename__ = "message_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tracking_id: Mapped[str] = mapped_column(String, ForeignKey("messages.tracking_id"))
    event_type: Mapped[EventType] = mapped_column(Enum(EventType))
    provider: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    message: Mapped[Message] = relationship("Message", back_populates="events")
