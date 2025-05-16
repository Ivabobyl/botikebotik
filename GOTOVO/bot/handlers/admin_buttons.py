"""
Модуль обработки кнопок админ-панели.
Централизует логику обработки админских функций и упрощает навигацию.
"""

import logging
from typing import Dict, Any, Optional, Union, List

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config.config import load_config, is_admin
from bot.utils.keyboards import get_main_menu_keyboard, get_admin_keyboard
from bot.utils.helpers import check_admin, check_operator

# Импорт необходимых обработчиков
from bot.handlers.admin_currency import handle_currency_management
from bot.handlers.notification import handle_notification_settings

logger = logging.getLogger(__name__)

async def handle_admin_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str) -> bool:
    """
    Обработчик кнопок админ-панели.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст Telegram бота
        button_text: Текст нажатой кнопки
        
    Returns:
        bool: True если кнопка была обработана, False если нет
    """
    user_id = update.effective_user.id
    
    # Проверка на админские права
    if not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для выполнения этой операции."
        )
        return True
        
    # Логика для каждой кнопки админ-панели
    if button_text == "⚙️ Установить курсы":
        # Обработка нажатия на кнопку управления курсами
        await handle_rates_setup(update, context)
        return True
        
    elif button_text == "📝 Управление заявками":
        # Обработка нажатия на кнопку управления заявками
        await handle_orders_management(update, context)
        return True
        
    elif button_text == "📊 Статистика":
        # Обработка нажатия на кнопку статистики
        await handle_statistics(update, context)
        return True
        
    elif button_text == "👥 Управление пользователями":
        # Обработка нажатия на кнопку управления пользователями
        await handle_users_management(update, context)
        return True
        
    elif button_text == "📨 Создать рассылку":
        # Обработка нажатия на кнопку создания рассылки
        await handle_broadcast_creation(update, context)
        return True
        
    elif button_text == "⚡ Настройки бота":
        # Обработка нажатия на кнопку настроек бота
        await handle_bot_settings(update, context)
        return True
        
    elif button_text == "💬 Управление текстами":
        # Обработка нажатия на кнопку управления текстами
        await handle_texts_management(update, context)
        return True
        
    elif button_text == "🔘 Управление кнопками":
        # Обработка нажатия на кнопку управления кнопками
        await handle_buttons_management(update, context)
        return True
        
    elif button_text == "💱 Управление валютами":
        # Обработка нажатия на кнопку управления валютами
        await handle_currency_management(update, context)
        return True
        
    elif button_text == "🔔 Уведомления":
        # Обработка нажатия на кнопку настройки уведомлений
        await handle_notification_settings(update, context)
        return True
        
    return False

async def handle_rates_setup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик настройки курсов обмена."""
    config = load_config()
    rates = config.get("rates", {})
    
    # Получаем текущие курсы
    ltc_usd_buy = rates.get("ltc_usd_buy", 0)
    ltc_usd_sell = rates.get("ltc_usd_sell", 0)
    usd_rub_buy = rates.get("usd_rub_buy", 0)
    usd_rub_sell = rates.get("usd_rub_sell", 0)
    
    # Форматируем сообщение с текущими курсами
    message_text = (
        "⚙️ *Установка курсов обмена*\n\n"
        "Текущие курсы обмена:\n"
        f"LTC ➝ USD (покупка): `{ltc_usd_buy}`\n"
        f"LTC ➝ USD (продажа): `{ltc_usd_sell}`\n"
        f"USD ➝ RUB (покупка): `{usd_rub_buy}`\n"
        f"USD ➝ RUB (продажа): `{usd_rub_sell}`\n\n"
        "Для изменения курса, отправьте сообщение в формате:\n"
        "```\n"
        "rate_type значение\n"
        "```\n"
        "Например: `ltc_usd_buy 100`\n\n"
        "Доступные типы курсов:\n"
        "- `ltc_usd_buy` - Покупка LTC за USD\n"
        "- `ltc_usd_sell` - Продажа LTC за USD\n"
        "- `usd_rub_buy` - Покупка USD за RUB\n"
        "- `usd_rub_sell` - Продажа USD за RUB\n"
    )
    
    # Устанавливаем состояние для обработки
    context.user_data["admin_state"] = "setting_rates"
    
    # Отправляем сообщение с клавиатурой
    keyboard = ReplyKeyboardMarkup([
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_orders_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик управления заявками."""
    # Получение активных заявок
    active_orders_count = 0
    in_progress_orders_count = 0
    completed_orders_count = 0
    
    # Формирование сообщения
    message_text = (
        "📝 *Управление заявками*\n\n"
        f"Активные заявки: {active_orders_count}\n"
        f"В обработке: {in_progress_orders_count}\n"
        f"Завершенные: {completed_orders_count}\n\n"
        "Выберите действие из меню ниже:"
    )
    
    # Клавиатура с вариантами действий
    keyboard = ReplyKeyboardMarkup([
        ["📋 Активные заявки", "📋 Заявки в обработке"],
        ["📋 Завершенные заявки", "🔍 Поиск заявки"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик статистики."""
    # Заглушка для статистики (в реальном боте здесь будет получение данных из БД)
    total_users = 0
    total_orders = 0
    completed_orders = 0
    total_volume_usd = 0
    
    # Формирование сообщения со статистикой
    message_text = (
        "📊 *Статистика бота*\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Всего заявок: {total_orders}\n"
        f"Завершенных заявок: {completed_orders}\n"
        f"Общий объем (USD): ${total_volume_usd}\n\n"
        "Выберите период для просмотра детальной статистики:"
    )
    
    # Клавиатура с выбором периода
    keyboard = ReplyKeyboardMarkup([
        ["📅 За сегодня", "📅 За неделю"],
        ["📅 За месяц", "📅 За все время"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_users_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик управления пользователями."""
    # Заглушка для получения данных о пользователях
    total_users = 0
    total_admins = 0
    total_operators = 0
    
    # Формирование сообщения
    message_text = (
        "👥 *Управление пользователями*\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Администраторов: {total_admins}\n"
        f"Операторов: {total_operators}\n\n"
        "Выберите действие из меню ниже:"
    )
    
    # Клавиатура с действиями
    keyboard = ReplyKeyboardMarkup([
        ["👤 Список админов", "👤 Список операторов"],
        ["➕ Добавить админа", "➕ Добавить оператора"],
        ["➖ Удалить админа", "➖ Удалить оператора"],
        ["🔍 Поиск пользователя"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_broadcast_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик создания рассылки."""
    # Формирование сообщения
    message_text = (
        "📨 *Создание рассылки*\n\n"
        "Выберите тип рассылки из меню ниже:"
    )
    
    # Клавиатура с типами рассылки
    keyboard = ReplyKeyboardMarkup([
        ["📨 Всем пользователям"],
        ["📨 Только админам", "📨 Только операторам"],
        ["📨 Активным пользователям"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик настроек бота."""
    # Получение текущих настроек
    config = load_config()
    min_amount = config.get("min_amount", 0)
    
    # Формирование сообщения
    message_text = (
        "⚡ *Настройки бота*\n\n"
        f"Минимальная сумма: {min_amount}\n\n"
        "Выберите параметр для изменения:"
    )
    
    # Клавиатура с параметрами
    keyboard = ReplyKeyboardMarkup([
        ["💰 Минимальная сумма", "💱 Комиссии"],
        ["🔄 Реферальная система", "🔔 Уведомления"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_texts_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик управления текстами."""
    # Формирование сообщения
    message_text = (
        "💬 *Управление текстами*\n\n"
        "Выберите текст для редактирования:"
    )
    
    # Клавиатура с текстами
    keyboard = ReplyKeyboardMarkup([
        ["💬 Приветствие", "💬 О нас"],
        ["💬 Правила", "💬 Контакты"],
        ["💬 Помощь", "💬 FAQ"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_buttons_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик управления кнопками."""
    # Формирование сообщения
    message_text = (
        "🔘 *Управление кнопками*\n\n"
        "Выберите действие из меню ниже:"
    )
    
    # Клавиатура с действиями
    keyboard = ReplyKeyboardMarkup([
        ["➕ Добавить кнопку", "➖ Удалить кнопку"],
        ["📋 Список кнопок", "✏️ Редактировать кнопку"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )