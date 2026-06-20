from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION, LEAVE_TRANSITION
from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatType
from database.crud import get_chat_settings
from database.models import ChatSettings
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Start command handler. Differentiates between DM and group chats."""
    if message.chat.type == ChatType.PRIVATE:
        await message.answer(
            "🛡 **Привет! Я защитный Telegram-бот от сообщества Endware Cyber Security.**\n\n"
            "Я помогаю защитить ваши каналы и чаты от спама, бот-набегов, скрытой рекламы, фишинга и взломов.\n\n"
            "⚙️ Чтобы настроить свои чаты и каналы, используйте команду `/settings` здесь, в личных сообщениях. "
            "Я найду ресурсы, в которых вы являетесь владельцем и где я добавлен администратором.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "🛡 **Бот Endware Security запущен в этом чате.**\n\n"
            "Все модули защиты активируются владельцем группы через панель управления в моих личных сообщениях (/settings)."
        )

@router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command handler."""
    help_text = (
        "🛡 **Инструкция по использованию Endware Security Bot**\n\n"
        "**Для владельцев чатов/каналов:**\n"
        "1. Добавьте бота в ваш чат или канал как администратора с правами на удаление сообщений, блокировку пользователей и управление администраторами (для полной защиты).\n"
        "2. Напишите мне в личные сообщения команду `/settings` для настройки параметров защиты, добавления стоп-слов или ввода кастомных ключей Groq.\n\n"
        "**Команды модераторов в чате (с ответом на сообщение нарушителя):**\n"
        "• `/mute [время] [причина]` — замутить (например, `/mute 30m спам`)\n"
        "• `/unmute` — размутить\n"
        "• `/kick` — кикнуть из группы\n"
        "• `/ban` — забанить\n"
        "• `/unban` — разбанить\n"
        "• `/warn [причина]` — выдать варн (3 варна = автомут на 24 часа)\n"
        "• `/unwarn` — снять варн\n"
    )
    await message.answer(help_text, parse_mode="Markdown")

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_bot_added(event: ChatMemberUpdated, db_session: AsyncSession):
    chat_id = event.chat.id
    # Get settings which automatically creates default entry in DB
    await get_chat_settings(db_session, chat_id)
    logger.info(f"Bot was added to chat/channel {chat_id}. ChatSettings initialized.")

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=LEAVE_TRANSITION))
async def on_bot_removed(event: ChatMemberUpdated, db_session: AsyncSession):
    chat_id = event.chat.id
    # Clean up settings from DB when bot is kicked
    await db_session.execute(delete(ChatSettings).where(ChatSettings.chat_id == chat_id))
    await db_session.commit()
    logger.info(f"Bot was removed from chat/channel {chat_id}. ChatSettings cleaned.")

