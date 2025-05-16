"""
Универсальный обработчик кнопок для телеграм-бота.
Этот модуль централизует логику обработки кнопок для улучшения надежности и упрощения поддержки.
"""

import logging
from typing import Dict, Any, Optional, Union, List

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config.config import load_config, is_admin
from bot.utils.keyboards import get_main_menu_keyboard, get_admin_keyboard
from bot.utils.helpers import check_admin, check_operator

logger = logging.getLogger(__name__)

def is_known_button(button_text: str) -> bool:
    """
    Проверяет, является ли текст известной кнопкой
    
    Args:
        button_text: Текст кнопки для проверки
        
    Returns:
        bool: True если кнопка найдена в словаре, False если нет
    """
    return button_text in BUTTON_MAP

# Словарь с описанием всех кнопок и их функциональности
BUTTON_MAP = {
    # Основные навигационные кнопки
    "🏠 Главное меню": {
        "action": "main_menu",
        "clear_states": True,
        "description": "Возврат в главное меню из любого места бота"
    },
    "🔐 Админ-панель": {
        "action": "admin_panel",
        "requires_admin": True,
        "description": "Открывает панель администратора"
    },
    "🔄 Назад в админ-панель": {
        "action": "admin_panel_back",
        "requires_admin": True,
        "description": "Возврат в панель администратора из подменю"
    },
    "🔙 Назад": {
        "action": "generic_back",
        "description": "Возврат на предыдущий экран в зависимости от контекста"
    },
    
    # Кнопки меню пользователя
    "📝 Купить крипту": {
        "action": "buy_crypto",
        "description": "Начать процесс покупки криптовалюты"
    },
    "📉 Продать крипту": {
        "action": "sell_crypto",
        "description": "Начать процесс продажи криптовалюты"
    },
    "👤 Профиль": {
        "action": "profile",
        "description": "Просмотр профиля пользователя"
    },
    "❓ Информация": {
        "action": "info",
        "description": "Показать информационное меню"
    },
    "📋 Мои заявки": {
        "action": "my_orders",
        "description": "Просмотр личных заявок пользователя"
    },
    "🔍 Курсы обмена": {
        "action": "exchange_rates",
        "description": "Просмотр текущих курсов обмена"
    },
    "📋 Активные заявки": {
        "action": "active_orders",
        "requires_operator": True,
        "description": "Просмотр всех активных заявок (для операторов и админов)"
    },
    
    # Кнопки админ-меню
    "⚙️ Установить курсы": {
        "action": "manage_rates",
        "requires_admin": True,
        "description": "Настройка курсов обмена"
    },
    "📝 Управление заявками": {
        "action": "manage_orders",
        "requires_admin": True,
        "description": "Управление всеми заявками"
    },
    "📊 Статистика": {
        "action": "statistics",
        "requires_admin": True,
        "description": "Просмотр статистики работы бота"
    },
    "👥 Управление пользователями": {
        "action": "manage_users",
        "requires_admin": True,
        "description": "Управление пользователями бота"
    },
    "📨 Создать рассылку": {
        "action": "create_broadcast",
        "requires_admin": True,
        "description": "Создание массовой рассылки"
    },
    "⚡ Настройки бота": {
        "action": "bot_settings",
        "requires_admin": True,
        "description": "Общие настройки бота"
    },
    "💬 Управление текстами": {
        "action": "manage_texts",
        "requires_admin": True, 
        "description": "Редактирование текстовых шаблонов"
    },
    "🔘 Управление кнопками": {
        "action": "manage_buttons",
        "requires_admin": True,
        "description": "Настройка кнопок бота"
    },
    "💱 Управление валютами": {
        "action": "manage_currencies",
        "requires_admin": True,
        "description": "Настройка поддерживаемых валют"
    },
    "🔔 Уведомления": {
        "action": "notifications",
        "requires_admin": True,
        "description": "Настройка уведомлений"
    }
}

async def process_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str) -> bool:
    """
    Универсальный обработчик кнопок.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст Telegram бота
        button_text: Текст нажатой кнопки
        
    Returns:
        bool: True если кнопка была обработана, False если нет
    """
    user_id = update.effective_user.id
    
    # Проверяем наличие кнопки в словаре
    button_info = BUTTON_MAP.get(button_text)
    if not button_info:
        # Если кнопка не найдена в словаре, пропускаем
        logger.info(f"Кнопка '{button_text}' не найдена в BUTTON_MAP")
        return False
        
    # Проверяем права администратора, если требуется
    if button_info.get("requires_admin", False) and not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для выполнения этой операции."
        )
        logger.warning(f"Пользователь {user_id} пытался использовать кнопку '{button_text}', требующую прав администратора")
        return True
        
    if button_info.get("requires_operator", False) and not await check_operator(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав оператора для выполнения этой операции."
        )
        return True
    
    # Очищаем состояния если нужно
    if button_info.get("clear_states", False):
        if "admin_state" in context.user_data:
            del context.user_data["admin_state"]
        if "current_operation" in context.user_data:
            del context.user_data["current_operation"]
        if "order_data" in context.user_data:
            del context.user_data["order_data"]
            
    # Обрабатываем кнопки в зависимости от их действия
    action = button_info.get("action", "")
    
    # Обработка основных навигационных кнопок
    if action == "main_menu":
        # Показываем главное меню
        is_admin_user = await check_admin(user_id)
        is_operator_user = await check_operator(user_id)
        keyboard = get_main_menu_keyboard(is_operator=is_operator_user, is_admin=is_admin_user)
        
        await update.message.reply_text(
            "🏠 *Главное меню*\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return True
        
    elif action == "admin_panel" or action == "admin_panel_back":
        # Показываем админ-панель
        # Очищаем все состояния при возврате в админ-панель
        if "admin_state" in context.user_data:
            del context.user_data["admin_state"]
            
        keyboard = get_admin_keyboard()
        
        await update.message.reply_text(
            "🔐 *Панель администратора*\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return True
    
    # Обработка действий пользователя
    elif action == "buy_crypto":
        # Показываем меню покупки криптовалюты
        # Получаем доступные криптовалюты из конфигурации
        config = load_config()
        currencies = config.get("currencies", {})
        crypto_currencies = [c for c in currencies.get("crypto", []) if c.get("enabled", True)]
        
        if not crypto_currencies:
            await update.message.reply_text(
                "❌ *В данный момент покупка криптовалюты недоступна.*\n\n"
                "Администратор не настроил ни одной криптовалюты для обмена.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu_keyboard(is_admin=await check_admin(user_id))
            )
            return True
            
        # Показываем информацию о покупке
        rates = get_current_rates()
        
        # Формируем текст с информацией о курсах
        rates_text = ""
        for crypto in crypto_currencies:
            code = crypto["code"]
            buy_rate_key = f"{code.lower()}_usd_buy"
            if buy_rate_key in rates:
                rates_text += f"• 1 {code} = ${rates[buy_rate_key]} (покупка)\n"
        
        # Показываем клавиатуру с вариантами сумм
        keyboard_rows = []
        # Добавляем кнопки с предустановленными суммами
        predefined_amounts = ["0.1", "0.25", "0.5", "1"]
        
        for i in range(0, len(predefined_amounts), 2):
            row = []
            for amount in predefined_amounts[i:i+2]:
                for crypto in crypto_currencies:
                    row.append(f"{amount} {crypto['code']}")
            keyboard_rows.append(row)
            
        # Добавляем кнопку для ввода произвольной суммы
        keyboard_rows.append(["💰 Другая сумма"])
        # Добавляем кнопку возврата в меню
        keyboard_rows.append(["🔙 Назад", "🏠 Главное меню"])
        
        await update.message.reply_text(
            "💰 *Покупка криптовалюты*\n\n"
            f"Текущие курсы:\n{rates_text}\n"
            "Выберите сумму для покупки или введите свою:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True)
        )
        
        # Устанавливаем состояние для ввода суммы
        context.user_data["current_operation"] = "buy_crypto"
        return True
        
    elif action == "sell_crypto":
        # Показываем меню продажи криптовалюты
        # Получаем доступные криптовалюты из конфигурации
        config = load_config()
        currencies = config.get("currencies", {})
        crypto_currencies = [c for c in currencies.get("crypto", []) if c.get("enabled", True)]
        
        if not crypto_currencies:
            await update.message.reply_text(
                "❌ *В данный момент продажа криптовалюты недоступна.*\n\n"
                "Администратор не настроил ни одной криптовалюты для обмена.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_main_menu_keyboard(is_admin=await check_admin(user_id))
            )
            return True
            
        # Показываем информацию о продаже
        rates = get_current_rates()
        
        # Формируем текст с информацией о курсах
        rates_text = ""
        for crypto in crypto_currencies:
            code = crypto["code"]
            sell_rate_key = f"{code.lower()}_usd_sell"
            if sell_rate_key in rates:
                rates_text += f"• 1 {code} = ${rates[sell_rate_key]} (продажа)\n"
        
        # Показываем клавиатуру с вариантами сумм
        keyboard_rows = []
        # Добавляем кнопки с предустановленными суммами
        predefined_amounts = ["0.1", "0.25", "0.5", "1"]
        
        for i in range(0, len(predefined_amounts), 2):
            row = []
            for amount in predefined_amounts[i:i+2]:
                for crypto in crypto_currencies:
                    row.append(f"{amount} {crypto['code']}")
            keyboard_rows.append(row)
            
        # Добавляем кнопку для ввода произвольной суммы
        keyboard_rows.append(["💰 Другая сумма"])
        # Добавляем кнопку возврата в меню
        keyboard_rows.append(["🔙 Назад", "🏠 Главное меню"])
        
        await update.message.reply_text(
            "💱 *Продажа криптовалюты*\n\n"
            f"Текущие курсы:\n{rates_text}\n"
            "Выберите сумму для продажи или введите свою:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup(keyboard_rows, resize_keyboard=True)
        )
        
        # Устанавливаем состояние для ввода суммы
        context.user_data["current_operation"] = "sell_crypto"
        return True
    
    # Если код дошел сюда, значит кнопка была найдена в словаре,
    # но обработчик для неё нужно вызвать извне
    return True

def is_known_button(button_text: str) -> bool:
    """
    Проверяет, является ли текст известной кнопкой.
    
    Args:
        button_text: Текст для проверки
        
    Returns:
        bool: True если кнопка известна, False если нет
    """
    return button_text in BUTTON_MAP