from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from datetime import datetime
from .db import metadata

Base = declarative_base(metadata=metadata)


class UserProvider(Base):
    __tablename__ = "user_providers"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    provider = Column(String, primary_key=True)
    user = relationship("User", back_populates="providers")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    providers = relationship(
        "UserProvider", back_populates="user", cascade="all, delete-orphan", lazy="joined"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    to = Column(String, index=True)
    text = Column(String)
    provider = Column(String, index=True)
    status = Column(String, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
