import re
from datetime import datetime, timedelta
from typing import Optional
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.types import ChatPermissions
from aiogram.enums import ChatMemberStatus
from database.crud import add_warn, reset_warns, add_active_mute, remove_active_mute, get_warns
from sqlalchemy.ext.asyncio import AsyncSession
import config

router = Router()

def parse_time(time_str: str) -> Optional[timedelta]:
    """Parse time string like 30m, 1h, 2d, 1w into timedelta."""
    match = re.match(r"^(\d+)([mhdw])$", time_str.lower())
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "w":
        return timedelta(weeks=value)
    return None

async def is_admin(message: types.Message) -> bool:
    """Helper to check if sender is admin or bot owner."""
    if message.from_user.id == config.OWNER_ID:
        return True
    member = await message.chat.get_member(message.from_user.id)
    return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]

@router.message(Command("mute"))
async def cmd_mute(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Mute a user in a chat. Command format: /mute [duration] [reason] as reply."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user
    args = message.text.split(maxsplit=2)
    
    duration = timedelta(minutes=30)  # Default mute duration is 30 mins
    reason = "нарушение правил"
    
    if len(args) > 1:
        parsed = parse_time(args[1])
        if parsed:
            duration = parsed
            if len(args) > 2:
                reason = args[2]
        else:
            reason = " ".join(args[1:])

    until_date = datetime.utcnow() + duration

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        # Register in database for tracking
        await add_active_mute(db_session, message.chat.id, target_user.id, until_date)
        
        await message.reply(
            f"🤐 Пользователь {target_user.mention_html()} временно лишен права писать сообщения.\n"
            f"⏱ **Срок:** {args[1] if len(args) > 1 and parsed else '30m'}\n"
            f"📝 **Причина:** {reason}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"Не удалось выдать мут: {e}")

@router.message(Command("unmute"))
async def cmd_unmute(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Unmute a user in a chat."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True
            )
        )
        await remove_active_mute(db_session, message.chat.id, target_user.id)
        await message.reply(f"🔊 Пользователь {target_user.mention_html()} размучен.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Не удалось снять мут: {e}")

@router.message(Command("kick"))
async def cmd_kick(message: types.Message, bot: Bot):
    """Kick user from the group (banned and immediately unbanned so they can rejoin)."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(f"👢 Пользователь {target_user.mention_html()} исключен из чата.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Не удалось кикнуть: {e}")

@router.message(Command("ban"))
async def cmd_ban(message: types.Message, bot: Bot):
    """Ban a user from the chat permanently."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "нарушение правил"

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(
            f"🚫 Пользователь {target_user.mention_html()} заблокирован в чате.\n"
            f"📝 **Причина:** {reason}",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.reply(f"Не удалось забанить: {e}")

@router.message(Command("unban"))
async def cmd_unban(message: types.Message, bot: Bot):
    """Unban a user."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user

    try:
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        await message.reply(f"✅ Пользователь {target_user.mention_html()} разблокирован.", parse_mode="HTML")
    except Exception as e:
        await message.reply(f"Не удалось разбанить: {e}")

@router.message(Command("warn"))
async def cmd_warn(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Issue a warning to a user. At 3 warnings, they are muted for 24 hours."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user
    args = message.text.split(maxsplit=1)
    reason = args[1] if len(args) > 1 else "нарушение правил"

    new_count = await add_warn(db_session, message.chat.id, target_user.id)

    if new_count >= 3:
        # Reset warnings and mute for 24h
        await reset_warns(db_session, message.chat.id, target_user.id)
        until_date = datetime.utcnow() + timedelta(days=1)
        
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target_user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await add_active_mute(db_session, message.chat.id, target_user.id, until_date)
            await message.reply(
                f"🚨 Пользователь {target_user.mention_html()} набрал **3/3 предупреждений** и автоматически замучен на **24 часа**.",
                parse_mode="HTML"
            )
        except Exception as e:
            await message.reply(f"Предупреждение выдано, но не удалось выдать автоматический мут: {e}")
    else:
        await message.reply(
            f"⚠️ Пользователь {target_user.mention_html()} получил предупреждение (**{new_count}/3**).\n"
            f"📝 **Причина:** {reason}",
            parse_mode="HTML"
        )

@router.message(Command("unwarn"))
async def cmd_unwarn(message: types.Message, db_session: AsyncSession):
    """Remove a warning from a user."""
    if not message.reply_to_message:
        return await message.reply("Эту команду нужно вызывать в ответ на сообщение пользователя.")
    
    if not await is_admin(message):
        return await message.reply("Вы не являетесь администратором.")

    target_user = message.reply_to_message.from_user
    
    current_count = await get_warns(db_session, message.chat.id, target_user.id)
    if current_count > 0:
        # Subtract one warn by deleting and re-creating or resetting. Let's just use database update directly or reset warns.
        # To decrement warn count, let's write a small database transaction or reset it
        # Since reset_warns deletes the entry, we can also decrease the count manually:
        from database.models import Warns
        from sqlalchemy import select
        result = await db_session.execute(
            select(Warns).where(Warns.chat_id == message.chat.id, Warns.user_id == target_user.id)
        )
        warn = result.scalar_one_or_none()
        if warn:
            warn.warn_count = max(0, warn.warn_count - 1)
            await db_session.commit()
            new_count = warn.warn_count
        else:
            new_count = 0
        await message.reply(f"✅ Одно предупреждение снято. Текущее количество: **{new_count}/3**.", parse_mode="HTML")
    else:
        await message.reply("У этого пользователя нет активных предупреждений.")
