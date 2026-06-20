import logging
from aiogram import Router, types, Bot, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ChatType, ChatMemberStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import ChatSettings, BlacklistedWords
from database.crud import get_chat_settings, update_chat_settings, add_blacklisted_word, remove_blacklisted_word, get_blacklisted_words
import config

logger = logging.getLogger(__name__)
router = Router()

class SettingsStates(StatesGroup):
    waiting_for_text_key = State()
    waiting_for_vision_key = State()
    waiting_for_log_channel = State()
    waiting_for_blacklist_word = State()

async def get_user_managed_chats(session: AsyncSession, bot: Bot, user_id: int):
    """Retrieve all chats from DB where user is Creator/Global Owner and bot is present."""
    result = await session.execute(select(ChatSettings))
    all_chat_settings = result.scalars().all()
    
    managed = []
    for setting in all_chat_settings:
        if user_id == config.OWNER_ID:
            try:
                chat = await bot.get_chat(setting.chat_id)
                managed.append(chat)
            except Exception:
                pass
            continue
            
        try:
            member = await bot.get_chat_member(setting.chat_id, user_id)
            if member.status in [ChatMemberStatus.CREATOR]:
                chat = await bot.get_chat(setting.chat_id)
                managed.append(chat)
        except Exception:
            # Bot might have been kicked or user is not in the chat
            pass
    return managed

def make_main_keyboard(chats, bot_username: str) -> InlineKeyboardMarkup:
    """Generate list of chats/groups/channels for owner to configure along with bot invite links."""
    keyboard = []
    for chat in chats:
        title = chat.title or f"Chat {chat.id}"
        keyboard.append([InlineKeyboardButton(text=f"⚙️ {title}", callback_data=f"set:chat:{chat.id}")])
    
    # Add help buttons to invite the bot
    keyboard.append([
        InlineKeyboardButton(text="➕ Добавить в группу", url=f"https://t.me/{bot_username}?startgroup=true"),
        InlineKeyboardButton(text="➕ Добавить в канал", url=f"https://t.me/{bot_username}?startchannel=true")
    ])
    keyboard.append([InlineKeyboardButton(text="🔄 Обновить список", callback_data="set:list")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def make_chat_settings_keyboard(session: AsyncSession, chat_id: int) -> InlineKeyboardMarkup:
    """Generate configuration options for a specific chat/channel."""
    settings = await get_chat_settings(session, chat_id)
    
    t_anti_bot = "✅ Анти-накрутка" if settings.anti_bot_flood else "❌ Анти-накрутка"
    t_anti_admin = "✅ Rogue Admin" if settings.anti_admin_spam else "❌ Rogue Admin"
    t_stealth_ad = "✅ Скрытая реклама" if settings.anti_stealth_ad else "❌ Скрытая реклама"
    t_captcha = "✅ Капча при входе" if settings.captcha_gate else "❌ Капча при входе"
    t_link_guard = "✅ Безопасные ссылки" if settings.link_guard else "❌ Безопасные ссылки"
    
    keyboard = [
        [InlineKeyboardButton(text=t_anti_bot, callback_data=f"set:toggle:{chat_id}:anti_bot_flood")],
        [InlineKeyboardButton(text=t_anti_admin, callback_data=f"set:toggle:{chat_id}:anti_admin_spam")],
        [InlineKeyboardButton(text=t_stealth_ad, callback_data=f"set:toggle:{chat_id}:anti_stealth_ad")],
        [InlineKeyboardButton(text=t_captcha, callback_data=f"set:toggle:{chat_id}:captcha_gate")],
        [InlineKeyboardButton(text=t_link_guard, callback_data=f"set:toggle:{chat_id}:link_guard")],
        [
            InlineKeyboardButton(text="➖ 10м", callback_data=f"set:mute:{chat_id}:minus"),
            InlineKeyboardButton(text=f"Мут: {settings.mute_duration_minutes} мин", callback_data="set:ignore"),
            InlineKeyboardButton(text="➕ 10м", callback_data=f"set:mute:{chat_id}:plus")
        ],
        [
            InlineKeyboardButton(text="🔑 Текстовый Ключ", callback_data=f"set:key_text:{chat_id}"),
            InlineKeyboardButton(text="📷 Визуальный Ключ", callback_data=f"set:key_vis:{chat_id}")
        ],
        [
            InlineKeyboardButton(text="📝 Стоп-слова", callback_data=f"set:words:{chat_id}"),
            InlineKeyboardButton(text="📢 Канал Логов", callback_data=f"set:log:{chat_id}")
        ],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="set:list")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.message(Command("settings"), F.chat.type == ChatType.PRIVATE)
async def cmd_settings(message: types.Message, db_session: AsyncSession, bot: Bot):
    """Entrypoint command for interactive settings panel (DM only)."""
    chats = await get_user_managed_chats(db_session, bot, message.from_user.id)
    bot_info = await bot.get_me()
    
    if not chats:
        text = (
            "⚠️ **У вас нет доступных чатов для настройки.**\n\n"
            "Чтобы настроить чат или канал:\n"
            "1. Нажмите одну из кнопок ниже, чтобы добавить бота в вашу группу или канал.\n"
            "2. Обязательно выдайте боту права администратора (удаление постов и блокировка пользователей).\n"
            "3. Вернитесь сюда и нажмите кнопку **Обновить список**."
        )
    else:
        text = "🛠 **Панель настройки Endware Security**\n\nВыберите чат или канал для управления:"
        
    await message.answer(
        text,
        reply_markup=make_main_keyboard(chats, bot_info.username),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "set:list")
async def callback_show_list(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chats = await get_user_managed_chats(db_session, bot, callback.from_user.id)
    bot_info = await bot.get_me()
    
    if not chats:
        text = (
            "⚠️ **У вас нет доступных чатов для настройки.**\n\n"
            "Чтобы настроить чат или канал:\n"
            "1. Нажмите одну из кнопок ниже, чтобы добавить бота в вашу группу или канал.\n"
            "2. Обязательно выдайте боту права администратора (удаление постов и блокировка пользователей).\n"
            "3. Нажмите кнопку **Обновить список**."
        )
    else:
        text = "🛠 **Панель настройки Endware Security**\n\nВыберите чат или канал для управления:"
        
    await callback.message.edit_text(
        text,
        reply_markup=make_main_keyboard(chats, bot_info.username),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set:chat:"))
async def callback_chat_details(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chat_id = int(callback.data.split(":")[2])
    chat = await bot.get_chat(chat_id)
    title = chat.title or f"Chat {chat_id}"
    
    settings = await get_chat_settings(db_session, chat_id)
    status_text = (
        f"⚙️ **Управление чатом/каналом:** {title}\n"
        f"• **ID:** `{chat_id}`\n\n"
        f"• **Текстовый ключ Groq:** {'Установлен (персональный)' if settings.custom_groq_key_text else 'Глобальный (дефолт)'}\n"
        f"• **Визуальный ключ Groq:** {'Установлен (персональный)' if settings.custom_groq_key_vision else 'Глобальный (дефолт)'}\n"
        f"• **Канал логов:** {settings.alert_channel_id if settings.alert_channel_id else 'не настроен'}"
    )
    
    await callback.message.edit_text(
        status_text,
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set:toggle:"))
async def callback_toggle_setting(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    _, _, chat_id_str, field = callback.data.split(":")
    chat_id = int(chat_id_str)
    
    settings = await get_chat_settings(db_session, chat_id)
    current_val = getattr(settings, field)
    # Update field toggle
    kwargs = {field: not current_val}
    await update_chat_settings(db_session, chat_id, **kwargs)
    
    # Refresh keyboard
    await callback.message.edit_reply_markup(
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id)
    )
    await callback.answer("Настройка изменена!")

@router.callback_query(F.data.startswith("set:mute:"))
async def callback_mute_duration(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    _, _, chat_id_str, action = callback.data.split(":")
    chat_id = int(chat_id_str)
    
    settings = await get_chat_settings(db_session, chat_id)
    current_mute = settings.mute_duration_minutes
    
    if action == "plus":
        new_mute = current_mute + 10
    else:
        new_mute = max(10, current_mute - 10)
        
    await update_chat_settings(db_session, chat_id, mute_duration_minutes=new_mute)
    
    # Refresh keyboard
    await callback.message.edit_reply_markup(
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id)
    )
    await callback.answer(f"Длительность мута: {new_mute} мин")

# --- Interactive Text Input States (FSM) ---

@router.callback_query(F.data.startswith("set:key_text:"))
async def on_set_key_text(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[2])
    await state.set_state(SettingsStates.waiting_for_text_key)
    await state.update_data(chat_id=chat_id, message_id=callback.message.message_id)
    await callback.message.edit_text(
        "🔑 **Отправьте Groq API Key для текстовых проверок.**\n"
        "Отправьте `/cancel` чтобы отменить.",
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set:key_vis:"))
async def on_set_key_vision(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[2])
    await state.set_state(SettingsStates.waiting_for_vision_key)
    await state.update_data(chat_id=chat_id, message_id=callback.message.message_id)
    await callback.message.edit_text(
        "📷 **Отправьте Groq API Key для анализа изображений.**\n"
        "Отправьте `/cancel` чтобы отменить.",
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("set:log:"))
async def on_set_log_channel(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[2])
    await state.set_state(SettingsStates.waiting_for_log_channel)
    await state.update_data(chat_id=chat_id, message_id=callback.message.message_id)
    await callback.message.edit_text(
        "📢 **Отправьте ID канала логирования (начинается с -100).**\n"
        "Убедитесь, что бот добавлен администратором в этот лог-канал.\n"
        "Отправьте `/cancel` чтобы отменить.",
        parse_mode="Markdown"
    )

# --- FSM Handlers ---

@router.message(Command("cancel"), F.chat.type == ChatType.PRIVATE)
async def cmd_cancel_fsm(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    """Cancel FSM input and return to chat settings."""
    data = await state.get_data()
    chat_id = data.get("chat_id")
    await state.clear()
    
    if chat_id:
        chat = await bot.get_chat(chat_id)
        title = chat.title or f"Chat {chat_id}"
        await message.answer(
            f"❌ Ввод отменен.\n⚙️ **Управление чатом/каналом:** {title}",
            reply_markup=await make_chat_settings_keyboard(db_session, chat_id),
            parse_mode="Markdown"
        )
    else:
        await message.answer("❌ Ввод отменен.")

@router.message(SettingsStates.waiting_for_text_key, F.chat.type == ChatType.PRIVATE)
async def process_text_key(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    chat_id = data["chat_id"]
    key = message.text.strip()
    
    # Verify input key format slightly (gsk_...) or allow cleanup
    if key.startswith("gsk_") or len(key) > 20:
        await update_chat_settings(db_session, chat_id, custom_groq_key_text=key)
        await message.answer(f"✅ Персональный Groq Text Key успешно сохранен для чата `{chat_id}`.")
    else:
        # Reset custom key if they send something else or 'reset'
        await update_chat_settings(db_session, chat_id, custom_groq_key_text=None)
        await message.answer("🔄 Персональный Groq Text Key сброшен на дефолтный.")
        
    await state.clear()
    chat = await bot.get_chat(chat_id)
    await message.answer(
        f"⚙️ **Управление чатом:** {chat.title}",
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id),
        parse_mode="Markdown"
    )

@router.message(SettingsStates.waiting_for_vision_key, F.chat.type == ChatType.PRIVATE)
async def process_vision_key(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    chat_id = data["chat_id"]
    key = message.text.strip()
    
    if key.startswith("gsk_") or len(key) > 20:
        await update_chat_settings(db_session, chat_id, custom_groq_key_vision=key)
        await message.answer(f"✅ Персональный Groq Vision Key успешно сохранен для чата `{chat_id}`.")
    else:
        await update_chat_settings(db_session, chat_id, custom_groq_key_vision=None)
        await message.answer("🔄 Персональный Groq Vision Key сброшен на дефолтный.")
        
    await state.clear()
    chat = await bot.get_chat(chat_id)
    await message.answer(
        f"⚙️ **Управление чатом:** {chat.title}",
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id),
        parse_mode="Markdown"
    )

@router.message(SettingsStates.waiting_for_log_channel, F.chat.type == ChatType.PRIVATE)
async def process_log_channel(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    chat_id = data["chat_id"]
    log_input = message.text.strip()
    
    try:
        log_id = int(log_input)
        await update_chat_settings(db_session, chat_id, alert_channel_id=log_id)
        await message.answer(f"✅ Канал логов для чата `{chat_id}` успешно изменен на `{log_id}`.")
    except ValueError:
        # Reset if not numeric
        await update_chat_settings(db_session, chat_id, alert_channel_id=None)
        await message.answer("🔄 Канал логирования сброшен.")
        
    await state.clear()
    chat = await bot.get_chat(chat_id)
    await message.answer(
        f"⚙️ **Управление чатом:** {chat.title}",
        reply_markup=await make_chat_settings_keyboard(db_session, chat_id),
        parse_mode="Markdown"
    )

# --- Blacklist Stopwords UI ---

@router.callback_query(F.data.startswith("set:words:"))
async def callback_blacklist_words(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chat_id = int(callback.data.split(":")[2])
    words = await get_blacklisted_words(db_session, chat_id)
    
    chat = await bot.get_chat(chat_id)
    title = chat.title or f"Chat {chat_id}"
    
    text = f"📝 **Черный список стоп-слов для {title}:**\n\n"
    if words:
        text += ", ".join([f"`{w}`" for w in words])
    else:
        text += "Список пуст."
        
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить стоп-слово", callback_data=f"set:add_word:{chat_id}")],
        [InlineKeyboardButton(text="🗑 Очистить весь список", callback_data=f"set:clear_words:{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"set:chat:{chat_id}")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@router.callback_query(F.data.startswith("set:add_word:"))
async def on_add_word(callback: CallbackQuery, state: FSMContext):
    chat_id = int(callback.data.split(":")[3])
    await state.set_state(SettingsStates.waiting_for_blacklist_word)
    await state.update_data(chat_id=chat_id)
    await callback.message.edit_text(
        "📝 **Отправьте стоп-слово или фразу для добавления в фильтр.**\n"
        "Отправьте `/cancel` чтобы отменить.",
        parse_mode="Markdown"
    )

@router.message(SettingsStates.waiting_for_blacklist_word, F.chat.type == ChatType.PRIVATE)
async def process_new_word(message: types.Message, state: FSMContext, db_session: AsyncSession, bot: Bot):
    data = await state.get_data()
    chat_id = data["chat_id"]
    word = message.text.strip().lower()
    
    if word and not word.startswith("/"):
        added = await add_blacklisted_word(db_session, chat_id, word)
        if added:
            await message.answer(f"✅ Слово `{word}` добавлено в черный список.")
        else:
            await message.answer(f"⚠️ Слово `{word}` уже есть в списке.")
    else:
        await message.answer("❌ Недопустимое слово.")
        
    await state.clear()
    
    # Return to blacklist view
    words = await get_blacklisted_words(db_session, chat_id)
    chat = await bot.get_chat(chat_id)
    text = f"📝 **Черный список стоп-слов для {chat.title}:**\n\n" + ", ".join([f"`{w}`" for w in words])
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить стоп-слово", callback_data=f"set:add_word:{chat_id}")],
        [InlineKeyboardButton(text="🗑 Очистить весь список", callback_data=f"set:clear_words:{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"set:chat:{chat_id}")]
    ]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")

@router.callback_query(F.data.startswith("set:clear_words:"))
async def on_clear_words(callback: CallbackQuery, db_session: AsyncSession, bot: Bot):
    chat_id = int(callback.data.split(":")[3])
    
    # Delete all stopwords
    from database.models import BlacklistedWords
    from sqlalchemy import delete
    await db_session.execute(delete(BlacklistedWords).where(BlacklistedWords.chat_id == chat_id))
    await db_session.commit()
    
    await callback.answer("Черный список очищен!")
    
    # Refresh blacklist view
    chat = await bot.get_chat(chat_id)
    text = f"📝 **Черный список стоп-слов для {chat.title}:**\n\nСписок пуст."
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить стоп-слово", callback_data=f"set:add_word:{chat_id}")],
        [InlineKeyboardButton(text="🗑 Очистить весь список", callback_data=f"set:clear_words:{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к чату", callback_data=f"set:chat:{chat_id}")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard), parse_mode="Markdown")
