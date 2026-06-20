import asyncio
import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import TelegramObject, ChatPermissions
from database.db import init_db, async_session
from database.crud import get_expired_mutes, remove_active_mute
from handlers import common, moderation, channels, chats, settings
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("endware_bot")

class DbSessionMiddleware(BaseMiddleware):
    """Outer middleware to provide an active SQLAlchemy session to every handler."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with async_session() as session:
            data["db_session"] = session
            return await handler(event, data)

async def unmute_scheduler(bot: Bot):
    """Background loop checking SQLite for expired mutes every 15 seconds."""
    logger.info("Unmute scheduler service started.")
    while True:
        try:
            await asyncio.sleep(15)
            async with async_session() as session:
                expired = await get_expired_mutes(session)
                for mute in expired:
                    try:
                        await bot.restrict_chat_member(
                            chat_id=mute.chat_id,
                            user_id=mute.user_id,
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
                        logger.info(f"User {mute.user_id} in chat {mute.chat_id} was successfully unmuted (timer expired).")
                    except Exception as e:
                        # Log error (e.g. if bot was kicked or user left the chat)
                        logger.error(f"Could not restore chat permissions for user {mute.user_id} in chat {mute.chat_id}: {e}")
                    
                    # Always remove active mute entry from DB to avoid infinite retries
                    await remove_active_mute(session, mute.chat_id, mute.user_id)
        except Exception as e:
            logger.error(f"Unmute scheduler execution error: {e}")

async def main():
    # Initialize DB tables
    logger.info("Initializing SQLite database tables...")
    await init_db()

    # Initialize Bot and Dispatcher
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Setup database middlewares
    dp.message.outer_middleware(DbSessionMiddleware())
    dp.callback_query.outer_middleware(DbSessionMiddleware())
    dp.chat_join_request.outer_middleware(DbSessionMiddleware())
    dp.chat_member.outer_middleware(DbSessionMiddleware())
    dp.my_chat_member.outer_middleware(DbSessionMiddleware())

    # Register routers
    dp.include_router(common.router)
    dp.include_router(moderation.router)
    dp.include_router(settings.router)
    dp.include_router(channels.router)
    dp.include_router(chats.router)

    # Start background scheduler task
    asyncio.create_task(unmute_scheduler(bot))

    # Start polling loop
    logger.info("Starting Telegram Bot long polling...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
