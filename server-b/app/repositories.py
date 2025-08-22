from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from . import models


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_message(self, data: models.Message) -> None:
        self.session.add(data)
        await self.session.commit()

    async def update_message_status(self, tracking_id: str, status: models.MessageStatus, provider_final: str | None = None) -> None:
        await self.session.execute(
            update(models.Message)
            .where(models.Message.tracking_id == tracking_id)
            .values(status=status, provider_final=provider_final)
        )
        await self.session.commit()

    async def add_event(
        self, tracking_id: str, event_type: models.EventType, provider: str | None = None, details: dict | None = None
    ) -> None:
        evt = models.MessageEvent(
            tracking_id=tracking_id, event_type=event_type, provider=provider, details=details or {}
        )
        self.session.add(evt)
        await self.session.commit()

    async def get_message_with_events(self, tracking_id: str) -> models.Message | None:
        result = await self.session.execute(
            select(models.Message).where(models.Message.tracking_id == tracking_id).options(
                selectinload(models.Message.events)
            )
        )
        return result.scalars().first()


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_users(self) -> list[models.User]:
        result = await self.session.execute(select(models.User))
        return result.scalars().all()

    async def create_user(self, **data) -> models.User:
        user = models.User(**data)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get(self, user_id: int) -> models.User | None:
        return await self.session.get(models.User, user_id)

    async def get_by_username(self, username: str) -> models.User | None:
        result = await self.session.execute(select(models.User).where(models.User.username == username))
        return result.scalars().first()

    async def update_user(self, user_id: int, data: dict) -> models.User | None:
        user = await self.get(user_id)
        if not user:
            return None
        for key, value in data.items():
            setattr(user, key, value)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> bool:
        user = await self.get(user_id)
        if not user:
            return False
        await self.session.delete(user)
        await self.session.commit()
        return True

    async def change_password(self, username: str, password: str) -> models.User | None:
        user = await self.get_by_username(username)
        if not user:
            return None
        user.password = password
        await self.session.commit()
        return user
