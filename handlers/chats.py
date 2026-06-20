import asyncio
import logging
import random
import time
from typing import Dict, Any
from datetime import datetime, timedelta
from aiogram import Router, types, Bot, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions, CallbackQuery
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import ChatMemberUpdated
from aiogram.enums import ChatMemberStatus, ChatType
from database.crud import get_chat_settings, get_blacklisted_words, add_active_mute, add_warn, reset_warns
from sqlalchemy.ext.asyncio import AsyncSession
from services.heuristics import contains_stealth_ad_keywords, is_malicious_link, extract_urls
from services.groq import analyze_text, analyze_image
import config

logger = logging.getLogger(__name__)
router = Router()

# In-memory storage for active captchas
# Format: {(chat_id, user_id): {"correct": str, "msg_id": int, "expires_at": float}}
_active_captchas: Dict[tuple, Dict[str, Any]] = {}

CAPTCHA_ANIMALS = [
    {"name": "Лев", "emoji": "🦁"},
    {"name": "Тигр", "emoji": "🐯"},
    {"name": "Лиса", "emoji": "🦊"},
    {"name": "Медведь", "emoji": "🐻"},
    {"name": "Панда", "emoji": "🐼"},
    {"name": "Обезьяна", "emoji": "🐵"},
    {"name": "Заяц", "emoji": "🐰"},
    {"name": "Кот", "emoji": "🐱"}
]

async def send_group_alert(bot: Bot, chat_id: int, settings, text: str):
    """Utility to log security alerts to log channel and global owner."""
    if settings.alert_channel_id:
        try:
            await bot.send_message(settings.alert_channel_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Alert log failed for chat {chat_id}: {e}")
    if config.OWNER_ID:
        try:
            await bot.send_message(config.OWNER_ID, f"[Alert Group {chat_id}]\n{text}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Owner alert failed: {e}")

async def demote_admin_if_possible(bot: Bot, chat_id: int, user_id: int) -> bool:
    """Attempts to remove all admin rights from a group administrator (Rogue Admin)."""
    try:
        # Check if the bot is admin and has rights to manage administrators
        bot_member = await bot.get_chat_member(chat_id, bot.id)
        if bot_member.status == ChatMemberStatus.ADMINISTRATOR and bot_member.can_promote_members:
            await bot.promote_chat_member(
                chat_id=chat_id,
                user_id=user_id,
                is_anonymous=False,
                can_manage_chat=False,
                can_post_messages=False,
                can_edit_messages=False,
                can_delete_messages=False,
                can_manage_video_chats=False,
                can_restrict_members=False,
                can_promote_members=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False
            )
            return True
    except Exception as e:
        logger.error(f"Failed to demote admin {user_id} in {chat_id}: {e}")
    return False

# --- Captcha Gate ---

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated, db_session: AsyncSession, bot: Bot):
    """Triggers when a new user joins the chat. Restricts permissions and sends captcha."""
    chat_id = event.chat.id
    user = event.new_chat_member.user
    
    # Ignore bots
    if user.is_bot:
        return
        
    settings = await get_chat_settings(db_session, chat_id)
    if not settings.captcha_gate:
        return

    # Restrict permissions immediately
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False)
        )
    except Exception as e:
        logger.error(f"Failed to restrict joining member {user.id}: {e}")
        return

    # Select random animal captcha
    correct_animal = random.choice(CAPTCHA_ANIMALS)
    distractors = [a for a in CAPTCHA_ANIMALS if a["emoji"] != correct_animal["emoji"]]
    choices = random.sample(distractors, 3) + [correct_animal]
    random.shuffle(choices)

    # Make keyboard
    buttons = [
        InlineKeyboardButton(
            text=choice["emoji"], 
            callback_data=f"cap:{correct_animal['emoji']}:{choice['emoji']}:{user.id}"
        )
        for choice in choices
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[buttons])

    msg = await bot.send_message(
        chat_id=chat_id,
        text=(
            f"🤖 Добро пожаловать, {user.mention_html()}!\n\n"
            f"Для защиты от спам-ботов пройдите мини-капчу. "
            f"Выберите правильное животное: **{correct_animal['name']} {correct_animal['emoji']}**.\n"
            f"⏱ У вас есть {settings.captcha_timeout_seconds} сек."
        ),
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

    # Store state
    key = (chat_id, user.id)
    _active_captchas[key] = {
        "correct": correct_animal["emoji"],
        "msg_id": msg.message_id,
        "expires_at": time.time() + settings.captcha_timeout_seconds
    }

    # Start background timeout check
    asyncio.create_task(captcha_timeout_monitor(bot, chat_id, user.id, settings.captcha_timeout_seconds))

async def captcha_timeout_monitor(bot: Bot, chat_id: int, user_id: int, timeout: int):
    """Monitors if user responds to captcha in time. If not, kicks the user."""
    await asyncio.sleep(timeout)
    key = (chat_id, user_id)
    if key in _active_captchas:
        captcha = _active_captchas.pop(key)
        try:
            # Delete message and kick user
            await bot.delete_message(chat_id, captcha["msg_id"])
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
        except Exception as e:
            logger.error(f"Timeout handler error for user {user_id}: {e}")

@router.callback_query(F.data.startswith("cap:"))
async def handle_captcha_callback(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    """Handles captcha inline button clicks."""
    _, correct, chosen, target_id_str = callback.data.split(":")
    target_id = int(target_id_str)
    chat_id = callback.message.chat.id
    clicker_id = callback.from_user.id

    if clicker_id != target_id:
        return await callback.answer("Это не ваша капча!", show_alert=True)

    key = (chat_id, target_id)
    if key not in _active_captchas:
        return await callback.answer("Время вышло или капча неактивна.", show_alert=True)

    captcha = _active_captchas.pop(key)

    if chosen == correct:
        # Correct answer
        try:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=target_id,
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
            await callback.answer("Капча успешно пройдена! Добро пожаловать.", show_alert=False)
            await bot.delete_message(chat_id, captcha["msg_id"])
        except Exception as e:
            logger.error(f"Failed to restore permissions for user {target_id}: {e}")
    else:
        # Wrong answer - Kick user
        try:
            await callback.answer("Неверный ответ! Вы исключены из группы.", show_alert=True)
            await bot.delete_message(chat_id, captcha["msg_id"])
            await bot.ban_chat_member(chat_id, target_id)
            await bot.unban_chat_member(chat_id, target_id)
        except Exception as e:
            logger.error(f"Failed to kick user {target_id} on wrong captcha: {e}")

# --- Message Watchdog ---

async def handle_user_violation(
    bot: Bot, message: types.Message, db_session: AsyncSession, settings, reason: str, explanation: str
):
    """Mutes the user, deletes the message, and sends security alert logs."""
    chat_id = message.chat.id
    user = message.from_user
    
    # Check if user is admin
    member = await message.chat.get_member(user.id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]

    # Demote if admin (Rogue Admin Protection)
    demoted = False
    if is_admin and settings.anti_admin_spam:
        demoted = await demote_admin_if_possible(bot, chat_id, user.id)

    # Mute/Restrict user
    duration = timedelta(minutes=settings.mute_duration_minutes)
    until_date = datetime.utcnow() + duration
    
    try:
        await message.delete()
        if not is_admin or demoted:
            await bot.restrict_chat_member(
                chat_id=chat_id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await add_active_mute(db_session, chat_id, user.id, until_date)
            
        alert_msg = (
            f"🚨 **Нарушение правил в группе!**\n"
            f"• **Чат:** {message.chat.title}\n"
            f"• **Нарушитель:** {user.mention_html()} (`{user.id}`)\n"
            f"• **Тип:** {reason}\n"
            f"• **Вердикт:** Удаление сообщения + мут на {settings.mute_duration_minutes} мин"
            f"{' (Админ разжалован)' if demoted else ''}\n"
            f"• **Детали ИИ:** {explanation}"
        )
        await send_group_alert(bot, chat_id, settings, alert_msg)
    except Exception as e:
        logger.error(f"Error handling violation for user {user.id}: {e}")

@router.message(F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def monitor_chat_message(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Scans chat messages for URL security, stop words, stealth ads and NSFW media."""
    # Ignore messages without text/caption and photos
    if not message.text and not message.caption and not message.photo:
        return

    chat_id = message.chat.id
    user = message.from_user
    if user.is_bot:
        return

    settings = await get_chat_settings(db_session, chat_id)
    
    content = message.text or message.caption or ""
    
    # 1. Check custom blacklisted words
    if content:
        blacklisted = await get_blacklisted_words(db_session, chat_id)
        content_lower = content.lower()
        for word in blacklisted:
            if word in content_lower:
                return await handle_user_violation(
                    bot, message, db_session, settings, 
                    reason="Черный список слов", explanation=f"Содержит заблокированное слово: {word}"
                )

    # 2. Check Link Guard (Phishing and IP loggers)
    if settings.link_guard and content:
        urls = extract_urls(content)
        for url in urls:
            if is_malicious_link(url):
                return await handle_user_violation(
                    bot, message, db_session, settings,
                    reason="Вредоносная ссылка", explanation=f"Обнаружен IP-логгер или фишинг домен: {url}"
                )

    # 3. Check Stealth Ads (Heuristics + Groq API check)
    if settings.anti_stealth_ad and content:
        # Check nickname/username for promo links
        name_str = f"{user.first_name or ''} {user.last_name or ''} @{user.username or ''}"
        has_stealth_ad_profile = "@" in name_str or "t.me" in name_str or "http" in name_str
        
        has_suspicious_keywords = contains_stealth_ad_keywords(content)
        
        if has_stealth_ad_profile or has_suspicious_keywords:
            # Fallback to Groq for deep validation
            ai_res = await analyze_text(content, chat_id, db_session)
            if ai_res.get("is_violation"):
                return await handle_user_violation(
                    bot, message, db_session, settings,
                    reason=f"Скрытая реклама ({ai_res.get('reason')})",
                    explanation=ai_res.get("explanation", "")
                )

    # 4. Check NSFW Media (Groq Vision)
    if message.photo:
        # Ensure we check the photo settings. We can check either NSFW or generally illegal contents.
        # Since NSFW image classification is required, we use the vision key
        photo = message.photo[-1]
        try:
            file_info = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            photo_data = file_bytes.read()
            
            ai_res = await analyze_image(photo_data, chat_id, db_session)
            if ai_res.get("is_violation"):
                return await handle_user_violation(
                    bot, message, db_session, settings,
                    reason=f"Запрещенное изображение ({ai_res.get('reason')})",
                    explanation=ai_res.get("explanation", "")
                )
        except Exception as e:
            logger.error(f"Error checking group photo: {e}")
