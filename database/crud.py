from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import ChatSettings, Warns, ActiveMutes, BlacklistedWords

# --- ChatSettings CRUD ---

async def get_chat_settings(session: AsyncSession, chat_id: int) -> ChatSettings:
    """Retrieve chat settings, create default settings if they do not exist."""
    result = await session.execute(
        select(ChatSettings).where(ChatSettings.chat_id == chat_id)
    )
    settings = result.scalar_one_or_none()
    if not settings:
        settings = ChatSettings(chat_id=chat_id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings

async def update_chat_settings(session: AsyncSession, chat_id: int, **kwargs) -> ChatSettings:
    """Update settings fields dynamically."""
    settings = await get_chat_settings(session, chat_id)
    for key, value in kwargs.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await session.commit()
    await session.refresh(settings)
    return settings

# --- Warns CRUD ---

async def get_warns(session: AsyncSession, chat_id: int, user_id: int) -> int:
    """Get the current warning count for a user in a chat."""
    result = await session.execute(
        select(Warns).where(Warns.chat_id == chat_id, Warns.user_id == user_id)
    )
    warn = result.scalar_one_or_none()
    return warn.warn_count if warn else 0

async def add_warn(session: AsyncSession, chat_id: int, user_id: int) -> int:
    """Increment the warning count for a user. Return the new count."""
    result = await session.execute(
        select(Warns).where(Warns.chat_id == chat_id, Warns.user_id == user_id)
    )
    warn = result.scalar_one_or_none()
    if not warn:
        warn = Warns(chat_id=chat_id, user_id=user_id, warn_count=1)
        session.add(warn)
    else:
        warn.warn_count += 1
        warn.last_warn_date = datetime.utcnow()
    await session.commit()
    return warn.warn_count

async def reset_warns(session: AsyncSession, chat_id: int, user_id: int):
    """Reset the warnings count for a user to 0."""
    await session.execute(
        delete(Warns).where(Warns.chat_id == chat_id, Warns.user_id == user_id)
    )
    await session.commit()

# --- ActiveMutes CRUD ---

async def add_active_mute(session: AsyncSession, chat_id: int, user_id: int, unmute_at: datetime):
    """Record an active mute for a user in a chat."""
    # Check if mute already exists, if so update it
    result = await session.execute(
        select(ActiveMutes).where(ActiveMutes.chat_id == chat_id, ActiveMutes.user_id == user_id)
    )
    mute = result.scalar_one_or_none()
    if not mute:
        mute = ActiveMutes(chat_id=chat_id, user_id=user_id, unmute_at=unmute_at)
        session.add(mute)
    else:
        mute.unmute_at = unmute_at
    await session.commit()

async def remove_active_mute(session: AsyncSession, chat_id: int, user_id: int):
    """Remove active mute entry when user is unmuted."""
    await session.execute(
        delete(ActiveMutes).where(ActiveMutes.chat_id == chat_id, ActiveMutes.user_id == user_id)
    )
    await session.commit()

async def get_expired_mutes(session: AsyncSession) -> List[ActiveMutes]:
    """Retrieve all mutes that have expired relative to the current UTC time."""
    result = await session.execute(
        select(ActiveMutes).where(ActiveMutes.unmute_at <= datetime.utcnow())
    )
    return list(result.scalars().all())

# --- BlacklistedWords CRUD ---

async def get_blacklisted_words(session: AsyncSession, chat_id: int) -> List[str]:
    """Get list of blacklisted words for a chat."""
    result = await session.execute(
        select(BlacklistedWords).where(BlacklistedWords.chat_id == chat_id)
    )
    return [row.word for row in result.scalars().all()]

async def add_blacklisted_word(session: AsyncSession, chat_id: int, word: str) -> bool:
    """Add a word to the blacklist if it is not already present. Returns True if added."""
    word_clean = word.strip().lower()
    result = await session.execute(
        select(BlacklistedWords).where(BlacklistedWords.chat_id == chat_id, BlacklistedWords.word == word_clean)
    )
    if not result.scalar_one_or_none():
        new_word = BlacklistedWords(chat_id=chat_id, word=word_clean)
        session.add(new_word)
        await session.commit()
        return True
    return False

async def remove_blacklisted_word(session: AsyncSession, chat_id: int, word: str) -> bool:
    """Remove a word from the blacklist. Returns True if removed."""
    word_clean = word.strip().lower()
    result = await session.execute(
        delete(BlacklistedWords).where(BlacklistedWords.chat_id == chat_id, BlacklistedWords.word == word_clean)
    )
    await session.commit()
    return result.rowcount > 0
