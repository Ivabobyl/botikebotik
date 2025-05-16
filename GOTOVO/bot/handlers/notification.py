"""
Модуль для управления уведомлениями бота.
"""

import logging
from typing import Dict, Any, Optional, List

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config.config import load_config, save_config
from bot.utils.helpers import check_admin

logger = logging.getLogger(__name__)

async def handle_notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик настроек уведомлений."""
    user_id = update.effective_user.id
    
    # Проверяем права администратора
    if not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для настройки уведомлений."
        )
        return
    
    # Получаем текущие настройки уведомлений
    config = load_config()
    notifications = config.get("notifications", {
        "new_order": True,
        "completed_order": True,
        "new_user": True,
        "user_message": True,
        "system": True
    })
    
    # Если нет настроек уведомлений, добавляем их с дефолтными значениями
    if "notifications" not in config:
        config["notifications"] = notifications
        save_config(config)
    
    # Формируем сообщение с текущими настройками
    status_symbols = {True: "✅", False: "❌"}
    
    message_text = (
        "🔔 *Настройки уведомлений*\n\n"
        f"{status_symbols[notifications.get('new_order', True)]} Новые заявки\n"
        f"{status_symbols[notifications.get('completed_order', True)]} Завершенные заявки\n"
        f"{status_symbols[notifications.get('new_user', True)]} Новые пользователи\n"
        f"{status_symbols[notifications.get('user_message', True)]} Сообщения от пользователей\n"
        f"{status_symbols[notifications.get('system', True)]} Системные уведомления\n\n"
        "Выберите тип уведомлений для включения/отключения:"
    )
    
    # Клавиатура с типами уведомлений
    keyboard = ReplyKeyboardMarkup([
        ["🔄 Новые заявки", "🔄 Завершенные заявки"],
        ["🔄 Новые пользователи", "🔄 Сообщения от пользователей"],
        ["🔄 Системные уведомления"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    # Сохраняем состояние для обработки выбора
    context.user_data["admin_state"] = "notification_settings"
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_notification_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик переключения настроек уведомлений."""
    user_id = update.effective_user.id
    
    # Проверяем права администратора
    if not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для настройки уведомлений."
        )
        return
    
    message_text = update.message.text
    
    # Определяем тип уведомления на основе текста кнопки
    notification_type_map = {
        "🔄 Новые заявки": "new_order",
        "🔄 Завершенные заявки": "completed_order",
        "🔄 Новые пользователи": "new_user",
        "🔄 Сообщения от пользователей": "user_message",
        "🔄 Системные уведомления": "system"
    }
    
    notification_type = notification_type_map.get(message_text)
    
    if not notification_type:
        # Если не нашли соответствующий тип, значит это не переключение настройки
        return
    
    # Получаем текущие настройки
    config = load_config()
    notifications = config.get("notifications", {
        "new_order": True,
        "completed_order": True,
        "new_user": True,
        "user_message": True,
        "system": True
    })
    
    # Переключаем настройку
    notifications[notification_type] = not notifications.get(notification_type, True)
    
    # Сохраняем настройки
    config["notifications"] = notifications
    save_config(config)
    
    # Отображаем обновленные настройки
    status_symbols = {True: "✅", False: "❌"}
    
    updated_message = (
        "🔔 *Настройки уведомлений*\n\n"
        f"{status_symbols[notifications.get('new_order', True)]} Новые заявки\n"
        f"{status_symbols[notifications.get('completed_order', True)]} Завершенные заявки\n"
        f"{status_symbols[notifications.get('new_user', True)]} Новые пользователи\n"
        f"{status_symbols[notifications.get('user_message', True)]} Сообщения от пользователей\n"
        f"{status_symbols[notifications.get('system', True)]} Системные уведомления\n\n"
        f"✅ Настройка '{message_text.replace('🔄 ', '')}' {('включена' if notifications[notification_type] else 'отключена')}."
    )
    
    await update.message.reply_text(
        updated_message,
        reply_markup=update.message.reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def send_notification(message: str, notification_type: str, bot = None) -> bool:
    """
    Отправляет уведомление администраторам.
    
    Args:
        message: Текст уведомления
        notification_type: Тип уведомления (new_order, completed_order, new_user, user_message, system)
        bot: Экземпляр бота для отправки сообщений
        
    Returns:
        bool: True если уведомление отправлено, False в случае ошибки
    """
    from bot.config.constants import ADMIN_ID
    
    # Получаем настройки уведомлений
    config = load_config()
    notifications = config.get("notifications", {
        "new_order": True,
        "completed_order": True,
        "new_user": True,
        "user_message": True,
        "system": True
    })
    
    # Проверяем, включены ли уведомления данного типа
    if not notifications.get(notification_type, True):
        logger.info(f"Notification of type {notification_type} is disabled")
        return False
    
    try:
        # Отправляем уведомление администратору
        if bot:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        else:
            logger.error("Bot instance not provided for sending notification")
            return False
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False