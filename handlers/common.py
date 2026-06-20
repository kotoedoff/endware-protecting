from aiogram import Router, types
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatType

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
