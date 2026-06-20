from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from database.db import Base

class ChatSettings(Base):
    __tablename__ = "chat_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_title: Mapped[str] = mapped_column(String, nullable=True)
    chat_type: Mapped[str] = mapped_column(String, nullable=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    anti_bot_flood: Mapped[bool] = mapped_column(Boolean, default=False)
    anti_admin_spam: Mapped[bool] = mapped_column(Boolean, default=False)
    anti_stealth_ad: Mapped[bool] = mapped_column(Boolean, default=False)
    captcha_gate: Mapped[bool] = mapped_column(Boolean, default=False)
    link_guard: Mapped[bool] = mapped_column(Boolean, default=False)
    mute_duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    captcha_timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    custom_groq_key_text: Mapped[str] = mapped_column(String, nullable=True)
    custom_groq_key_vision: Mapped[str] = mapped_column(String, nullable=True)
    alert_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

class Warns(Base):
    __tablename__ = "warns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    warn_count: Mapped[int] = mapped_column(Integer, default=0)
    last_warn_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ActiveMutes(Base):
    __tablename__ = "active_mutes"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    unmute_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

class BlacklistedWords(Base):
    __tablename__ = "blacklisted_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    word: Mapped[str] = mapped_column(String, nullable=False)
