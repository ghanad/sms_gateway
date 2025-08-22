from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from .models import User, Message, UserProvider
from .auth import get_password_hash


# User operations
async def get_user_by_username(session: AsyncSession, username: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.username == username))
    return result.unique().scalars().first()


async def create_user(session: AsyncSession, username: str, password: str, role: str = "user") -> User:
    user = User(username=username, password_hash=get_password_hash(password), role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def list_users(session: AsyncSession) -> List[User]:
    result = await session.execute(select(User).distinct())
    return list(result.scalars().unique())


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.unique().scalars().first()


async def delete_user(session: AsyncSession, user_id: int) -> None:
    user = await get_user(session, user_id)
    if user:
        await session.delete(user)
        await session.commit()


async def add_user_provider(session: AsyncSession, user: User, provider_name: str) -> User:
    assoc = UserProvider(user_id=user.id, provider=provider_name)
    user.providers.append(assoc)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# Message operations
async def list_messages(
    session: AsyncSession,
    *,
    to: Optional[str] = None,
    provider: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> tuple[List[Message], int]:
    query = select(Message)
    count_query = select(func.count(Message.id))
    if to:
        query = query.where(Message.to == to)
        count_query = count_query.where(Message.to == to)
    if provider:
        query = query.where(Message.provider == provider)
        count_query = count_query.where(Message.provider == provider)
    if status:
        query = query.where(Message.status == status)
        count_query = count_query.where(Message.status == status)
    total = (await session.execute(count_query)).scalar() or 0
    result = await session.execute(query.order_by(Message.id).limit(limit).offset(offset))
    return list(result.scalars()), total


async def get_message(session: AsyncSession, message_id: int) -> Optional[Message]:
    result = await session.execute(select(Message).where(Message.id == message_id))
    return result.scalar_one_or_none()


async def providers_summary(session: AsyncSession):
    result = await session.execute(
        select(Message.provider, func.count(Message.id)).group_by(Message.provider)
    )
    return [(row[0], row[1]) for row in result.all()]


async def summary(session: AsyncSession):
    msg_count = (await session.execute(select(func.count(Message.id)))).scalar() or 0
    user_count = (await session.execute(select(func.count(User.id)))).scalar() or 0
    return msg_count, user_count
