import logging
from aiogram import Router, types, Bot
from aiogram.filters import ChatMemberUpdatedFilter
from aiogram.types import ChatJoinRequest
from database.crud import get_chat_settings, get_blacklisted_words
from sqlalchemy.ext.asyncio import AsyncSession
from services.heuristics import check_join_rate, is_suspicious_profile, extract_urls, is_malicious_link
from services.groq import analyze_text, analyze_image
import config

logger = logging.getLogger(__name__)
router = Router()

async def send_alert(bot: Bot, chat_id: int, settings, text: str):
    """Send alert to the configured alert channel and the global bot owner."""
    if settings.alert_channel_id:
        try:
            await bot.send_message(settings.alert_channel_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send alert to channel {settings.alert_channel_id}: {e}")
            
    if config.OWNER_ID:
        try:
            await bot.send_message(config.OWNER_ID, f"[Alert Chat {chat_id}]\n{text}", parse_mode="HTML")
        except Exception as e:
            logger.error(f"Failed to send alert to global owner: {e}")

@router.chat_join_request()
async def handle_join_request(event: ChatJoinRequest, db_session: AsyncSession, bot: Bot):
    """
    Handles join requests for channels (and chats if enabled).
    Performs rate-limit flood checks and profile heuristic verification.
    """
    chat_id = event.chat.id
    user = event.from_user
    settings = await get_chat_settings(db_session, chat_id)

    if not settings.anti_bot_flood:
        # Default behavior: approve if protection is off
        await event.approve()
        return

    # Check join rate (flood detection)
    is_flood = check_join_rate(chat_id)
    
    # Check if user has a profile picture
    has_photo = False
    try:
        photos = await bot.get_user_profile_photos(user.id, limit=1)
        has_photo = photos.total_count > 0
    except Exception as e:
        logger.error(f"Error fetching profile photos for user {user.id}: {e}")

    # Inspect profile using heuristics
    is_bot = is_suspicious_profile(
        first_name=user.first_name,
        last_name=user.last_name,
        username=user.username,
        bio=None, # Bio is not available in ChatJoinRequest object directly
        has_photo=has_photo
    )

    if is_flood or is_bot:
        try:
            # Decline request and block user to prevent further requests
            await event.decline()
            await bot.ban_chat_member(chat_id=chat_id, user_id=user.id)
            
            alert_msg = (
                f"🚨 **Заблокирован подозрительный бот на входе!**\n"
                f"• **Имя:** {user.full_name}\n"
                f"• **ID:** `{user.id}`\n"
                f"• **Юзернейм:** @{user.username if user.username else 'нет'}\n"
                f"• **Причина:** {'Всплеск накрутки (Anti-Flood)' if is_flood else 'Эвристика бота (Anti-Bot)'}"
            )
            await send_alert(bot, chat_id, settings, alert_msg)
        except Exception as e:
            logger.error(f"Error blocking bot {user.id}: {e}")
    else:
        try:
            await event.approve()
        except Exception as e:
            logger.error(f"Error approving user {user.id}: {e}")

async def inspect_channel_post(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Inspect channel posts for malicious links, keywords, or NSFW content."""
    chat_id = message.chat.id
    settings = await get_chat_settings(db_session, chat_id)

    if not settings.anti_admin_spam:
        return

    content_to_check = message.text or message.caption or ""
    urls = extract_urls(content_to_check)
    
    # 1. Local checks: malicious links (phishing/loggers)
    for url in urls:
        if is_malicious_link(url):
            await message.delete()
            alert_msg = (
                f"🚨 **Удален вредоносный пост в канале!**\n"
                f"• **Канал:** {message.chat.title}\n"
                f"• **Причина:** Обнаружена фишинговая ссылка / IP-логгер\n"
                f"• **Ссылка:** `{url}`"
            )
            await send_alert(bot, chat_id, settings, alert_msg)
            return

    # 2. Local checks: custom blacklisted words
    blacklisted_words = await get_blacklisted_words(db_session, chat_id)
    content_lower = content_to_check.lower()
    for word in blacklisted_words:
        if word in content_lower:
            await message.delete()
            alert_msg = (
                f"🚨 **Удален пост в канале!**\n"
                f"• **Канал:** {message.chat.title}\n"
                f"• **Причина:** Обнаружено запрещенное слово из черного списка (`{word}`)"
            )
            await send_alert(bot, chat_id, settings, alert_msg)
            return

    # 3. AI Scan: Text content via Groq
    if content_to_check:
        ai_res = await analyze_text(content_to_check, chat_id, db_session)
        if ai_res.get("is_violation"):
            await message.delete()
            alert_msg = (
                f"🚨 **Удален пост ИИ-фильтром (Groq)!**\n"
                f"• **Канал:** {message.chat.title}\n"
                f"• **Нарушение:** {ai_res.get('reason')}\n"
                f"• **Объяснение:** {ai_res.get('explanation')}"
            )
            await send_alert(bot, chat_id, settings, alert_msg)
            return

    # 4. AI Scan: Photo content via Groq Vision
    if message.photo:
        # Download the largest photo size
        photo = message.photo[-1]
        try:
            file_info = await bot.get_file(photo.file_id)
            file_bytes = await bot.download_file(file_info.file_path)
            # Read bytes
            photo_data = file_bytes.read()
            
            ai_res = await analyze_image(photo_data, chat_id, db_session)
            if ai_res.get("is_violation"):
                await message.delete()
                alert_msg = (
                    f"🚨 **Удален медиа-пост ИИ-фильтром (Groq Vision)!**\n"
                    f"• **Канал:** {message.chat.title}\n"
                    f"• **Нарушение:** {ai_res.get('reason')}\n"
                    f"• **Объяснение:** {ai_res.get('explanation')}"
                )
                await send_alert(bot, chat_id, settings, alert_msg)
                return
        except Exception as e:
            logger.error(f"Failed to download/analyze channel photo: {e}")

@router.channel_post()
async def on_channel_post(message: types.Message, db_session: AsyncSession, bot: Bot):
    await inspect_channel_post(message, db_session, bot)

@router.edited_channel_post()
async def on_edited_channel_post(message: types.Message, db_session: AsyncSession, bot: Bot):
    await inspect_channel_post(message, db_session, bot)
