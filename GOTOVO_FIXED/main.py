import os
import sys
import logging
import asyncio

# Add the current directory to the path for imports
sys.path.insert(0, os.getcwd())

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Import bot modules
from telegram.ext import Application, ApplicationBuilder
from bot.database import init_db
from bot.config.constants import BOT_TOKEN, ADMIN_ID, MAIN_CHAT_ID
from bot.config.config import load_config, save_config, add_admin
from bot.handlers import register_handlers

def main():
    """Основная функция для запуска бота"""
    # Load configuration
    config = load_config()
    
    # Make sure the admin ID is in the config
    if ADMIN_ID not in config["admin_ids"]:
        config["admin_ids"].append(ADMIN_ID)
        save_config(config)
        add_admin(ADMIN_ID)
    
    # Initialize the database (в отдельном цикле для инициализации)
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_db())
    loop.close()
    
    # Print debug info
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Main Chat ID: {MAIN_CHAT_ID}")
    logger.info(f"Bot Config: {config}")
    
    # Создаем приложение
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Регистрируем обработчики
    register_handlers(application)
    
    # Функция для отправки уведомления о запуске
    async def post_init(application):
        """Отправляет уведомление после инициализации"""
        try:
            await application.bot.send_message(
                chat_id=ADMIN_ID,
                text="✅ Бот запущен и готов к работе!"
            )
        except Exception as e:
            logger.error(f"Failed to send startup notification: {e}")
    
    # Устанавливаем функцию post_init
    application.post_init = post_init
    
    logger.info("Starting bot polling")
    
    # Запускаем бот с polling (блокирует выполнение до остановки)
    application.run_polling(
        allowed_updates=["message", "callback_query", "edited_message", "channel_post", "edited_channel_post", "chat_member"],
        drop_pending_updates=False
    )

if __name__ == "__main__":
    # Запускаем бота
    main()

# Функции для тестовой отправки сообщений
def admin_send_message(message_text):
    """Отправить сообщение администратору"""
    # Создаем отдельное приложение для отправки сообщения
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Используем выделенный event loop для отправки сообщения
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Инициализируем бота и отправляем сообщение
        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.bot.send_message(
            chat_id=ADMIN_ID,
            text=message_text
        ))
        loop.run_until_complete(app.shutdown())
    except Exception as e:
        logger.error(f"Failed to send message to admin: {e}")
    finally:
        # Закрываем цикл событий
        loop.close()
    
def chat_send_message(message_text):
    """Отправить сообщение в групповой чат"""
    # Создаем отдельное приложение для отправки сообщения
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Используем выделенный event loop для отправки сообщения
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Инициализируем бота и отправляем сообщение
        loop.run_until_complete(app.initialize())
        loop.run_until_complete(app.bot.send_message(
            chat_id=MAIN_CHAT_ID,
            text=message_text
        ))
        loop.run_until_complete(app.shutdown())
    except Exception as e:
        logger.error(f"Failed to send message to chat: {e}")
    finally:
        # Закрываем цикл событий
        loop.close()