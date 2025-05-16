import os
import logging
import asyncio
from telegram.ext import ApplicationBuilder, Application

from bot.config.constants import BOT_TOKEN, ADMIN_ID, MAIN_CHAT_ID
from bot.database import init_db
from bot.handlers import register_handlers
from bot.config import load_config, save_config, add_admin

logger = logging.getLogger(__name__)

async def create_bot() -> Application:
    """Create and configure the bot application"""
    # Import here to avoid circular imports
    from bot.config import load_config, save_config, add_admin
    
    # Load configuration
    config = load_config()
    
    # Make sure the admin ID is in the config
    if ADMIN_ID not in config["admin_ids"]:
        config["admin_ids"].append(ADMIN_ID)
        save_config(config)
        add_admin(ADMIN_ID)
    
    # Create the Application
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Initialize the database
    await init_db()
    
    # Register all handlers
    register_handlers(application)
    
    logger.info("Bot initialized successfully")
    return application

async def start_bot(application: Application):
    """Start the bot and keep it running until interrupted"""
    logger.info("Starting the bot")
    
    # Notify admin that bot has started
    try:
        await application.bot.send_message(
            chat_id=ADMIN_ID,
            text="✅ Бот запущен и готов к работе!"
        )
    except Exception as e:
        logger.error(f"Failed to send startup notification: {e}")
    
    # Set up polling without awaiting
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
        close_loop=False
    )
