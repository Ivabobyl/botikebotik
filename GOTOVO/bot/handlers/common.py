import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.config.config import (
    load_config, save_config, get_current_rates, update_rates,
    is_admin, add_admin, remove_admin, get_referral_percentage,
    is_operator, add_operator, remove_operator, get_min_amount, set_min_amount,
    get_currencies, get_enabled_crypto_currencies, get_enabled_fiat_currencies,
    add_crypto_currency, add_fiat_currency, enable_disable_currency
)
from bot.database import get_custom_command, get_user, create_order, get_users
from bot.utils.keyboards import get_main_menu_keyboard, get_admin_keyboard
from bot.utils.helpers import check_admin
from bot.handlers.admin_currency import handle_admin_currency_message

logger = logging.getLogger(__name__)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with available commands"""
    help_text = (
        "🤖 *Доступные команды:*\n\n"
        "/start - Начать работу с ботом\n"
        "/profile - Просмотр вашего профиля\n"
        "/help - Показать эту справку\n\n"
        "Используйте кнопки меню для навигации."
    )
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def handle_custom_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle custom commands created by admins"""
    # Extract command name (without / prefix)
    command_text = update.message.text[1:]  # Remove leading '/'
    
    # If command has parameters, only use the command part
    if ' ' in command_text:
        command_text = command_text.split(' ')[0]
    
    # Lookup command in database
    command = await get_custom_command(command_text)
    
    if not command:
        return  # Not a custom command, let other handlers process it
    
    # Create keyboard with buttons if defined
    keyboard = []
    buttons = command.get("buttons", [])
    
    if buttons:
        # Create rows with 1-2 buttons each
        row = []
        for i, button_text in enumerate(buttons):
            row.append(InlineKeyboardButton(button_text, callback_data=f"custom_button_{command_text}_{i}"))
            
            # Add 2 buttons per row
            if len(row) == 2 or i == len(buttons) - 1:
                keyboard.append(row)
                row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    # Send response
    await update.message.reply_text(
        command["response"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_custom_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle custom command button clicks"""
    await update.callback_query.answer()
    
    # Get button data
    query_data = update.callback_query.data
    parts = query_data.split('_')
    
    if len(parts) < 4:
        await update.callback_query.edit_message_text("❌ Ошибка: неверный формат кнопки.")
        return
    
    command_name = parts[2]
    button_index = int(parts[3])
    
    # Get command data
    command = await get_custom_command(command_name)
    
    if not command:
        await update.callback_query.edit_message_text("❌ Команда не найдена.")
        return
    
    # Get button text
    buttons = command.get("buttons", [])
    
    if button_index >= len(buttons):
        await update.callback_query.edit_message_text("❌ Кнопка не найдена.")
        return
    
    button_text = buttons[button_index]
    
    # For now, just show the button text with a back button
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data=f"custom_back_{command_name}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"*{button_text}*\n\n"
        f"Вы выбрали: {button_text}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_custom_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back button for custom commands"""
    await update.callback_query.answer()
    
    # Get command name
    query_data = update.callback_query.data
    command_name = query_data.split('_')[2]
    
    # Get command data
    command = await get_custom_command(command_name)
    
    if not command:
        await update.callback_query.edit_message_text("❌ Команда не найдена.")
        return
    
    # Create keyboard with buttons if defined
    keyboard = []
    buttons = command.get("buttons", [])
    
    if buttons:
        # Create rows with 1-2 buttons each
        row = []
        for i, button_text in enumerate(buttons):
            row.append(InlineKeyboardButton(button_text, callback_data=f"custom_button_{command_name}_{i}"))
            
            # Add 2 buttons per row
            if len(row) == 2 or i == len(buttons) - 1:
                keyboard.append(row)
                row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    # Send response
    await update.callback_query.edit_message_text(
        command["response"],
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu callback to return user to the main menu from anywhere"""
    await update.callback_query.answer()
    
    user_id = update.effective_user.id
    user_data = await get_user(user_id)
    if not user_data:
        user_data = {"role": "user"}
    
    is_operator_role = user_data.get("role") == "operator"
    is_admin_role = user_data.get("role") == "admin" or is_admin(user_id)
    
    keyboard = get_main_menu_keyboard(is_operator_role, is_admin_role)
    
    await update.callback_query.edit_message_text(
        "🏠 *Главное меню*\n\nВыберите действие из меню ниже:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_commission_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки настройки комиссий"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет доступа к этой функции. Только администраторы могут настраивать комиссии.",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Купить LTC", "💱 Продать LTC"],
                ["👤 Профиль", "📊 Мои сделки"],
                ["ℹ️ Информация", "📞 Поддержка"]
            ], resize_keyboard=True)
        )
        return
    
    # Получаем текущие настройки комиссий
    rates = get_current_rates()
    
    await update.message.reply_text(
        "📋 *Настройки комиссий*\n\n"
        "Здесь вы можете настроить курсы обмена и комиссии для всех валют.\n\n"
        "*Текущие курсы:*\n"
        f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
        f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
        f"*Курсы USD/RUB:*\n"
        f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
        f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
        "Для изменения курсов, выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup([
            ["🔄 Изменить все курсы"],
            ["📈 Изменить курс покупки LTC", "📉 Изменить курс продажи LTC"],
            ["💵 Изменить курс USD/RUB"],
            ["🔄 Назад в админ-панель"]
        ], resize_keyboard=True)
    )

async def handle_notification_settings_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки настройки уведомлений"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет доступа к этой функции. Только администраторы могут настраивать уведомления.",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Купить LTC", "💱 Продать LTC"],
                ["👤 Профиль", "📊 Мои сделки"],
                ["ℹ️ Информация", "📞 Поддержка"]
            ], resize_keyboard=True)
        )
        return
    
    # Получаем текущие настройки уведомлений
    config = load_config()
    notification_settings = config.get("notifications", {
        "new_order_to_chat": True,
        "new_order_to_admin": True,
        "completed_order_to_chat": True,
        "system_messages_to_admin": True
    })
    
    # Формируем статусы
    status_new_order_chat = "✅" if notification_settings.get("new_order_to_chat", True) else "❌"
    status_new_order_admin = "✅" if notification_settings.get("new_order_to_admin", True) else "❌"
    status_completed_order = "✅" if notification_settings.get("completed_order_to_chat", True) else "❌"
    status_system_messages = "✅" if notification_settings.get("system_messages_to_admin", True) else "❌"
    
    await update.message.reply_text(
        "📱 *Настройка уведомлений*\n\n"
        "Здесь вы можете настроить параметры уведомлений системы.\n\n"
        "*Текущие настройки:*\n"
        f"• Новые заказы в чат: {status_new_order_chat}\n"
        f"• Новые заказы админу: {status_new_order_admin}\n"
        f"• Выполненные заказы в чат: {status_completed_order}\n"
        f"• Системные сообщения админу: {status_system_messages}\n\n"
        "Выберите, какое уведомление вы хотите изменить:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup([
            [f"{status_new_order_chat} Новые заказы в чат"],
            [f"{status_new_order_admin} Новые заказы админу"],
            [f"{status_completed_order} Выполненные заказы в чат"],
            [f"{status_system_messages} Системные сообщения админу"],
            ["🔄 Назад в админ-панель"]
        ], resize_keyboard=True)
    )
    
    # Устанавливаем состояние для ожидания ввода
    context.user_data["admin_state"] = "waiting_for_notification_toggle"

async def handle_notification_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик переключения настроек уведомлений"""
    message_text = update.message.text
    
    if message_text == "🔄 Назад в админ-панель":
        # Возвращаемся в админ-панель
        if "admin_state" in context.user_data:
            del context.user_data["admin_state"]
        await handle_admin_panel(update, context)
        return
        
    # Определяем, какая настройка была выбрана
    try:
        config = load_config()
        if "notifications" not in config:
            config["notifications"] = {
                "new_order_to_chat": True,
                "new_order_to_admin": True,
                "completed_order_to_chat": True,
                "system_messages_to_admin": True
            }
            
        notification_settings = config["notifications"]
        
        setting_key = None
        new_status = None
        
        # Очищаем текст сообщения от эмодзи статуса (✅ или ❌)
        clean_message = message_text
        if message_text.startswith("✅ ") or message_text.startswith("❌ "):
            clean_message = message_text[2:]
        
        # Проверяем настройки по очищенному сообщению
        if clean_message == "Новые заказы в чат":
            setting_key = "new_order_to_chat"
            current_status = notification_settings.get(setting_key, True)
            new_status = not current_status
        elif clean_message == "Новые заказы админу":
            setting_key = "new_order_to_admin"
            current_status = notification_settings.get(setting_key, True)
            new_status = not current_status
        elif clean_message == "Выполненные заказы в чат":
            setting_key = "completed_order_to_chat"
            current_status = notification_settings.get(setting_key, True)
            new_status = not current_status
        elif clean_message == "Системные сообщения админу":
            setting_key = "system_messages_to_admin"
            current_status = notification_settings.get(setting_key, True)
            new_status = not current_status
    except Exception as e:
        logger.error(f"Ошибка при обработке настроек уведомлений: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке настроек уведомлений. Попробуйте еще раз."
        )
        return
    
    if setting_key and new_status is not None:
        # Обновляем настройку
        notification_settings[setting_key] = new_status
        config["notifications"] = notification_settings
        save_config(config)
        
        # Обновляем отображение
        status_text = "включены ✅" if new_status else "отключены ❌"
        
        # Формируем статусы для кнопок
        status_new_order_chat = "✅" if notification_settings.get("new_order_to_chat", True) else "❌"
        status_new_order_admin = "✅" if notification_settings.get("new_order_to_admin", True) else "❌"
        status_completed_order = "✅" if notification_settings.get("completed_order_to_chat", True) else "❌"
        status_system_messages = "✅" if notification_settings.get("system_messages_to_admin", True) else "❌"
        
        # Определяем название настройки
        setting_name = ""
        if setting_key == "new_order_to_chat":
            setting_name = "Уведомления о новых заказах в чат"
        elif setting_key == "new_order_to_admin":
            setting_name = "Уведомления о новых заказах админу"
        elif setting_key == "completed_order_to_chat":
            setting_name = "Уведомления о выполненных заказах в чат"
        elif setting_key == "system_messages_to_admin":
            setting_name = "Системные сообщения админу"
        
        # Создаем клавиатуру для ответа
        keyboard = ReplyKeyboardMarkup([
            [f"{status_new_order_chat} Новые заказы в чат"],
            [f"{status_new_order_admin} Новые заказы админу"],
            [f"{status_completed_order} Выполненные заказы в чат"],
            [f"{status_system_messages} Системные сообщения админу"],
            ["🔄 Назад в админ-панель"]
        ], resize_keyboard=True)
        
        # Подготавливаем сообщение
        message_text = (
            f"✅ *Настройка обновлена!*\n\n"
            f"*{setting_name}* теперь {status_text}\n\n"
            f"Выберите другие настройки или вернитесь в меню:"
        )
        
        try:
            # Пытаемся отправить сообщение с Markdown-разметкой
            await update.message.reply_text(
                message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            # В случае ошибки парсинга Markdown отправляем без разметки
            logger.error(f"Ошибка отправки сообщения с Markdown: {e}")
            await update.message.reply_text(
                message_text.replace('*', ''),
                reply_markup=keyboard
            )
    else:
        # Неизвестная опция
        await update.message.reply_text(
            "❌ Неизвестная опция. Пожалуйста, выберите один из предложенных вариантов.",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True)
        )

async def handle_referral_system_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик кнопки настройки реферальной системы"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет доступа к этой функции. Только администраторы могут настраивать реферальную систему.",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Купить LTC", "💱 Продать LTC"],
                ["👤 Профиль", "📊 Мои сделки"],
                ["ℹ️ Информация", "📞 Поддержка"]
            ], resize_keyboard=True)
        )
        return
    
    # Получаем текущие настройки реферальной системы
    config = load_config()
    levels = config["referral"]["levels"]
    
    levels_text = "\n".join([
        f"• {level['min']}-{level['max'] if level['max'] != float('inf') else '∞'} рефералов: {level['percentage']}%"
        for level in levels
    ])
    
    await update.message.reply_text(
        "🔗 *Настройка реферальной системы*\n\n"
        "Здесь вы можете настроить проценты вознаграждения для разных уровней рефералов.\n\n"
        "*Текущие уровни:*\n"
        f"{levels_text}\n\n"
        "Для редактирования, введите новые настройки в формате:\n"
        "`мин1-макс1:процент1, мин2-макс2:процент2, ...`\n\n"
        "Например: `1-10:10, 11-25:12.5, 26-50:15, 51-100:17.5, 101-inf:20`\n\n"
        "Где `inf` означает бесконечность.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup([
            ["🔄 Назад в админ-панель"]
        ], resize_keyboard=True)
    )
    
    # Устанавливаем состояние для ожидания ввода
    context.user_data["admin_state"] = "waiting_for_referral_settings"

async def handle_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает админ-панель"""
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет доступа к этой функции.",
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Купить LTC", "💱 Продать LTC"],
                ["👤 Профиль", "📊 Мои сделки"],
                ["ℹ️ Информация", "📞 Поддержка"]
            ], resize_keyboard=True)
        )
        return
    
    await update.message.reply_text(
        "👨‍💼 *Панель администратора*\n\n"
        "Выберите действие:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=ReplyKeyboardMarkup([
            ["👥 Управление пользователями", "💼 Управление заказами"],
            ["👨‍💼 Управление админами", "📋 Настройка комиссий"],
            ["💰 Мин. сумма транзакции", "🔗 Реферальная система"],
            ["📱 Настройка уведомлений"],
            ["🔄 Назад в главное меню"]
        ], resize_keyboard=True)
    )

async def update_referral_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обновляет настройки реферальной системы"""
    try:
        message_text = update.message.text.strip()
        
        # Отмена операции
        if message_text == "🔄 Назад в админ-панель":
            del context.user_data["admin_state"]
            await handle_admin_panel(update, context)
            return
        
        # Парсим введенную строку
        levels = []
        for level_str in message_text.split(','):
            level_str = level_str.strip()
            if not level_str:
                continue
                
            range_part, percentage_part = level_str.split(':')
            range_part = range_part.strip()
            percentage_part = percentage_part.strip()
            
            min_max = range_part.split('-')
            min_val = int(min_max[0].strip())
            max_val = float('inf') if min_max[1].strip().lower() == 'inf' else int(min_max[1].strip())
            percentage = float(percentage_part)
            
            levels.append({
                "min": min_val,
                "max": max_val,
                "percentage": percentage
            })
        
        # Проверяем корректность данных
        if not levels:
            raise ValueError("Не указаны уровни реферальной системы")
            
        # Проверяем, что уровни не перекрываются
        sorted_levels = sorted(levels, key=lambda x: x["min"])
        for i in range(1, len(sorted_levels)):
            if sorted_levels[i]["min"] <= sorted_levels[i-1]["max"]:
                raise ValueError(f"Уровни перекрываются: {sorted_levels[i-1]} и {sorted_levels[i]}")
        
        # Обновляем конфигурацию
        config = load_config()
        config["referral"]["levels"] = sorted_levels
        save_config(config)
        
        # Формируем новый текст с уровнями
        levels_text = "\n".join([
            f"• {level['min']}-{level['max'] if level['max'] != float('inf') else '∞'} рефералов: {level['percentage']}%"
            for level in sorted_levels
        ])
        
        # Отправляем подтверждение
        await update.message.reply_text(
            "✅ *Настройки реферальной системы успешно обновлены!*\n\n"
            "*Новые уровни:*\n"
            f"{levels_text}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["👨‍💼 Управление админами", "📋 Настройка комиссий"],
                ["💰 Мин. сумма транзакции", "🔗 Реферальная система"],
                ["📱 Настройка уведомлений"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True)
        )
        
        # Сбрасываем состояние
        del context.user_data["admin_state"]
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении настроек реферальной системы: {e}")
        await update.message.reply_text(
            f"❌ *Ошибка!*\n\n"
            f"Произошла ошибка при обновлении настроек: {str(e)}\n\n"
            f"Пожалуйста, проверьте формат ввода и попробуйте снова.\n"
            f"Формат: `мин1-макс1:процент1, мин2-макс2:процент2, ...`\n\n"
            f"Например: `1-10:10, 11-25:12.5, 26-50:15, 51-100:17.5, 101-inf:20`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True)
        )

async def check_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором"""
    from bot.config import is_admin
    return is_admin(user_id)
    
async def check_operator(user_id: int) -> bool:
    """Проверяет, является ли пользователь оператором"""
    from bot.database import get_user
    user = await get_user(user_id)
    return user is not None and user.get("role") == "operator"

async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых кнопок из ReplyKeyboardMarkup"""
    message_text = update.message.text
    user_id = update.effective_user.id
    
    # Обработка основных кнопок пользователя
    if message_text == "🏠 Главное меню":
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
        
        # Очистка состояний
        keys_to_clear = ["admin_state", "current_operation", "order_data"]
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]
        return
        
    elif message_text == "📝 Купить крипту":
        # Получаем доступные криптовалюты
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
            return
        
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
        return
        
    elif message_text == "📉 Продать крипту":
        # Такой же код как для покупки, но с другими текстами и состояниями
        # Получаем доступные криптовалюты
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
            return
        
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
        return
    
    # Проверка прав администратора
    user_is_admin = await check_admin(user_id)
    
    # Обработка админских кнопок
    if message_text == "🔐 Админ-панель" and user_is_admin:
        await update.message.reply_text(
            "🔐 *Панель администратора*\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=get_admin_keyboard(),
            parse_mode=ParseMode.MARKDOWN
        )
        return
            
    # Импортируем обработчик админских кнопок
    from bot.handlers.admin_buttons import handle_admin_button
    
    # Проверяем, является ли это кнопкой админ-панели
    if user_is_admin and message_text:
        # Пытаемся обработать кнопку через обработчик админ-панели
        handled = await handle_admin_button(update, context, message_text)
        if handled:
            return
    
    # Получаем текущее состояние
    admin_state = context.user_data.get("admin_state", None)
    
    # Проверяем, не находимся ли мы в состоянии управления валютами
    if admin_state in ["add_crypto", "add_fiat", "toggle_currency_status", "currency_management"] and user_is_admin:
        # Вызываем специализированный обработчик для управления валютами
        await handle_admin_currency_message(update, context)
        return
    
    # Обработка кнопки "Уведомления"
    elif message_text == "🔔 Уведомления" and user_is_admin:
        await handle_notification_settings_button(update, context)
        return
        
    # Обработка кнопки "Управление валютами"
    elif message_text == "💱 Управление валютами" and user_is_admin:
        # Получаем список валют
        currencies = get_currencies()
        crypto_currencies = currencies.get("crypto", [])
        fiat_currencies = currencies.get("fiat", [])
        
        # Формируем сообщение со списком валют
        crypto_text = "\n".join([
            f"• {'✅' if c.get('enabled', True) else '❌'} {c['code']} - {c['name']}" 
            for c in crypto_currencies
        ])
        
        fiat_text = "\n".join([
            f"• {'✅' if c.get('enabled', True) else '❌'} {c['code']} - {c['name']} ({c.get('symbol', '')})" 
            for c in fiat_currencies
        ])
        
        await update.message.reply_text(
            f"💱 *Управление валютами*\n\n"
            f"*Криптовалюты:*\n{crypto_text}\n\n"
            f"*Фиатные валюты:*\n{fiat_text}\n\n"
            f"Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Добавить криптовалюту", "➕ Добавить фиатную валюту"],
                ["✏️ Изменить статус валюты"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "currency_management"
        return
    
    # Обработка кнопок в меню "Управление валютами"
    elif message_text == "➕ Добавить криптовалюту" and is_admin:
        await update.message.reply_text(
            "➕ *Добавление новой криптовалюты*\n\n"
            "Введите код и название криптовалюты в формате:\n"
            "`КОД Название`\n\n"
            "Например: `BTC Bitcoin`",
            reply_markup=ReplyKeyboardMarkup([
                ["🔙 Назад к валютам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "add_crypto"
        return
    
    elif message_text == "➕ Добавить фиатную валюту" and is_admin:
        await update.message.reply_text(
            "➕ *Добавление новой фиатной валюты*\n\n"
            "Введите код, название и символ валюты в формате:\n"
            "`КОД Название Символ`\n\n"
            "Например: `UAH Гривна ₴`",
            reply_markup=ReplyKeyboardMarkup([
                ["🔙 Назад к валютам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "add_fiat"
        return
    
    elif message_text == "✏️ Изменить статус валюты" and is_admin:
        # Получаем список валют
        currencies = get_currencies()
        crypto_currencies = currencies.get("crypto", [])
        fiat_currencies = currencies.get("fiat", [])
        
        # Создаем клавиатуру с кнопками для всех валют
        keyboard = []
        for c in crypto_currencies:
            status = "✅" if c.get('enabled', True) else "❌"
            keyboard.append([KeyboardButton(f"{status} CRYPTO:{c['code']} ({c['name']})")])
        
        for c in fiat_currencies:
            status = "✅" if c.get('enabled', True) else "❌"
            keyboard.append([KeyboardButton(f"{status} FIAT:{c['code']} ({c['name']})")])
        
        keyboard.append([KeyboardButton("🔙 Назад к валютам")])
        
        await update.message.reply_text(
            "✏️ *Изменение статуса валюты*\n\n"
            "Выберите валюту, статус которой хотите изменить:\n"
            "✅ - валюта активна\n"
            "❌ - валюта отключена",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "toggle_currency_status"
        return
    
    elif message_text == "🔙 Назад к валютам" and is_admin:
        # Возврат в меню управления валютами
        # Получаем список валют
        currencies = get_currencies()
        crypto_currencies = currencies.get("crypto", [])
        fiat_currencies = currencies.get("fiat", [])
        
        # Формируем сообщение со списком валют
        crypto_text = "\n".join([
            f"• {'✅' if c.get('enabled', True) else '❌'} {c['code']} - {c['name']}" 
            for c in crypto_currencies
        ])
        
        fiat_text = "\n".join([
            f"• {'✅' if c.get('enabled', True) else '❌'} {c['code']} - {c['name']} ({c.get('symbol', '')})" 
            for c in fiat_currencies
        ])
        
        await update.message.reply_text(
            f"💱 *Управление валютами*\n\n"
            f"*Криптовалюты:*\n{crypto_text}\n\n"
            f"*Фиатные валюты:*\n{fiat_text}\n\n"
            f"Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Добавить криптовалюту", "➕ Добавить фиатную валюту"],
                ["✏️ Изменить статус валюты"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "currency_management"
        return
    
    # Обработка кнопок админ-панели
    elif message_text == "⚙️ Установить курсы" and is_admin:
        rates = get_current_rates()
        await update.message.reply_text(
            f"💱 *Текущие курсы обмена:*\n\n"
            f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
            f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
            f"*Курсы USD/RUB:*\n"
            f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
            f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
            f"Выберите, какой курс вы хотите изменить:",
            reply_markup=ReplyKeyboardMarkup([
                ["🪙 Покупка LTC (USD)", "🪙 Продажа LTC (USD)"],
                ["💱 Покупка USD (RUB)", "💱 Продажа USD (RUB)"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "select_rate_to_change"
        return
    
    elif message_text == "📝 Управление заявками" and is_admin:
        await update.message.reply_text(
            "📝 *Управление заявками*\n\n"
            "Выберите категорию заявок для просмотра:",
            reply_markup=ReplyKeyboardMarkup([
                ["📋 Активные заявки", "🔄 В процессе"],
                ["✅ Завершенные", "❌ Отмененные"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif message_text == "📊 Статистика" and is_admin:
        await update.message.reply_text(
            "📊 *Статистика*\n\n"
            "Выберите тип статистики для просмотра:",
            reply_markup=ReplyKeyboardMarkup([
                ["📈 Статистика заявок", "👥 Статистика пользователей"],
                ["💰 Финансовая статистика", "📆 Статистика по периодам"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif message_text == "👥 Управление пользователями" and is_admin:
        await update.message.reply_text(
            "👥 *Управление пользователями*\n\n"
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["👤 Найти пользователя", "🧩 Изменить роль"],
                ["💰 Изменить баланс", "❌ Заблокировать"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif message_text == "📨 Создать рассылку" and is_admin:
        await update.message.reply_text(
            "📨 *Создание рассылки*\n\n"
            "Выберите тип рассылки:",
            reply_markup=ReplyKeyboardMarkup([
                ["📢 Все пользователи", "👥 Выбранные пользователи"],
                ["💸 Пользователи с балансом", "🛒 С активными заявками"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif message_text == "⚡ Настройки бота" and is_admin:
        await update.message.reply_text(
            "⚡ *Настройки бота*\n\n"
            "Выберите раздел настроек:",
            reply_markup=ReplyKeyboardMarkup([
                ["👨‍💼 Управление админами", "📋 Настройка комиссий"],
                ["💰 Мин. сумма транзакции", "🔗 Реферальная система"],
                ["📱 Настройка уведомлений"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Настройка минимальной суммы транзакции
    elif message_text == "💰 Мин. сумма транзакции" and is_admin:
        min_amount = get_min_amount()
        await update.message.reply_text(
            f"💰 *Настройка минимальной суммы транзакции*\n\n"
            f"Текущее значение: *{min_amount:.2f} PMR рублей*\n\n"
            f"Введите новое значение минимальной суммы в PMR рублях:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Отмена"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_min_amount"
        return
    
    # Кнопка возврата из подменю админки в админ-панель
    elif message_text == "🔄 Назад в админ-панель" and is_admin:
        keyboard = get_admin_keyboard()
        await update.message.reply_text(
            "🔐 *Панель администратора*\n\n"
            "Выберите действие из меню ниже:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Обработка кнопок раздела "Управление пользователями"
    elif message_text == "👥 Управление пользователями" and is_admin:
        await update.message.reply_text(
            "👥 *Управление пользователями*\n\n"
            "Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["👤 Найти пользователя", "🧩 Изменить роль"],
                ["💰 Изменить баланс", "❌ Заблокировать"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Обработка кнопки "Найти пользователя"
    elif message_text == "👤 Найти пользователя" and is_admin:
        await update.message.reply_text(
            "👤 *Поиск пользователя*\n\n"
            "Введите ID или @username пользователя:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_user_id_search"
        return
    
    # Обработка кнопки "Изменить роль"
    elif message_text == "🧩 Изменить роль" and is_admin:
        await update.message.reply_text(
            "🧩 *Изменение роли пользователя*\n\n"
            "Введите ID пользователя, которому хотите изменить роль:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_user_id_role"
        return
    
    # Обработка кнопки "Изменить баланс"
    elif message_text == "💰 Изменить баланс" and is_admin:
        await update.message.reply_text(
            "💰 *Изменение баланса пользователя*\n\n"
            "Введите ID пользователя, которому хотите изменить баланс:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_user_id_balance"
        return
    
    # Обработка кнопки "Заблокировать"
    elif message_text == "❌ Заблокировать" and is_admin:
        await update.message.reply_text(
            "❌ *Блокировка пользователя*\n\n"
            "Введите ID пользователя, которого хотите заблокировать:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_user_id_block"
        return
        
    # Обработка кнопки "Статистика"
    elif message_text == "📊 Статистика" and is_admin:
        await update.message.reply_text(
            "📊 *Статистика*\n\n"
            "Выберите тип статистики для просмотра:",
            reply_markup=ReplyKeyboardMarkup([
                ["📈 Статистика заявок", "👥 Статистика пользователей"],
                ["💰 Финансовая статистика", "📆 Статистика по периодам"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопок в подменю "Статистика"
    elif message_text == "📈 Статистика заявок" and is_admin:
        # Получаем статистику по заявкам
        active_orders = await get_active_orders()
        in_progress_orders = await get_in_progress_orders()
        completed_orders = await get_completed_orders()
        
        # Считаем общую прибыль (спред)
        total_spread = 0
        for order in completed_orders:
            if order.get("spread"):
                total_spread += order.get("spread")
        
        await update.message.reply_text(
            "📈 *Статистика заявок*\n\n"
            f"• Активных заявок: {len(active_orders)}\n"
            f"• Заявок в работе: {len(in_progress_orders)}\n"
            f"• Завершённых заявок: {len(completed_orders)}\n"
            f"• Общая прибыль (спред): {total_spread:.2f} руб.\n\n",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад к статистике"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Кнопка возврата из подменю статистики в меню статистики
    elif message_text == "🔄 Назад к статистике" and is_admin:
        await update.message.reply_text(
            "📊 *Статистика*\n\n"
            "Выберите тип статистики для просмотра:",
            reply_markup=ReplyKeyboardMarkup([
                ["📈 Статистика заявок", "👥 Статистика пользователей"],
                ["💰 Финансовая статистика", "📆 Статистика по периодам"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки "Курсы обмена" (Валюты)
    elif message_text == "💱 Курсы обмена" and is_admin:
        # Получаем текущие курсы
        rates = get_current_rates()
        
        # Форматируем курсы для отображения
        await update.message.reply_text(
            "💱 *Курсы обмена*\n\n"
            f"*Покупка LTC:*\n"
            f"1 LTC = ${rates['ltc_usd_buy']:.2f}\n"
            f"1 LTC = ₽{rates['ltc_usd_buy'] * rates['usd_rub_buy']:.2f}\n\n"
            f"*Продажа LTC:*\n"
            f"1 LTC = ${rates['ltc_usd_sell']:.2f}\n"
            f"1 LTC = ₽{rates['ltc_usd_sell'] * rates['usd_rub_sell']:.2f}\n\n"
            f"*Курс USD/RUB:*\n"
            f"Покупка: 1 USD = ₽{rates['usd_rub_buy']:.2f}\n"
            f"Продажа: 1 USD = ₽{rates['usd_rub_sell']:.2f}",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Изменить курс покупки LTC", "📝 Изменить курс продажи LTC"],
                ["📝 Изменить курс USD/RUB"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки "Изменить курс покупки LTC"
    elif message_text == "📝 Изменить курс покупки LTC" and is_admin:
        rates = get_current_rates()
        await update.message.reply_text(
            "📝 *Изменение курса покупки LTC*\n\n"
            f"Текущий курс: 1 LTC = ${rates['ltc_usd_buy']:.2f}\n\n"
            "Выберите действие или введите новый курс:",
            reply_markup=ReplyKeyboardMarkup([
                ["+1%", "+5%", "-1%", "-5%"],
                ["🔄 Назад к курсам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "edit_ltc_buy_rate"
        return
        
    # Обработка кнопки "Изменить курс продажи LTC"
    elif message_text == "📝 Изменить курс продажи LTC" and is_admin:
        rates = get_current_rates()
        await update.message.reply_text(
            "📝 *Изменение курса продажи LTC*\n\n"
            f"Текущий курс: 1 LTC = ${rates['ltc_usd_sell']:.2f}\n\n"
            "Выберите действие или введите новый курс:",
            reply_markup=ReplyKeyboardMarkup([
                ["+1%", "+5%", "-1%", "-5%"],
                ["🔄 Назад к курсам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "edit_ltc_sell_rate"
        return
        
    # Обработка кнопки "Изменить курс USD/RUB"
    elif message_text == "📝 Изменить курс USD/RUB" and is_admin:
        rates = get_current_rates()
        await update.message.reply_text(
            "📝 *Изменение курса USD/RUB*\n\n"
            f"Текущий курс покупки: 1 USD = ₽{rates['usd_rub_buy']:.2f}\n"
            f"Текущий курс продажи: 1 USD = ₽{rates['usd_rub_sell']:.2f}\n\n"
            "Введите новый курс покупки USD/RUB:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад к курсам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "edit_usd_rub_buy_rate"
        return
        
    # Обработка кнопки "Назад к курсам"
    elif message_text == "🔄 Назад к курсам" and is_admin:
        # Получаем текущие курсы
        rates = get_current_rates()
        
        # Форматируем курсы для отображения
        await update.message.reply_text(
            "💱 *Курсы обмена*\n\n"
            f"*Покупка LTC:*\n"
            f"1 LTC = ${rates['ltc_usd_buy']:.2f}\n"
            f"1 LTC = ₽{rates['ltc_usd_buy'] * rates['usd_rub_buy']:.2f}\n\n"
            f"*Продажа LTC:*\n"
            f"1 LTC = ${rates['ltc_usd_sell']:.2f}\n"
            f"1 LTC = ₽{rates['ltc_usd_sell'] * rates['usd_rub_sell']:.2f}\n\n"
            f"*Курс USD/RUB:*\n"
            f"Покупка: 1 USD = ₽{rates['usd_rub_buy']:.2f}\n"
            f"Продажа: 1 USD = ₽{rates['usd_rub_sell']:.2f}",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Изменить курс покупки LTC", "📝 Изменить курс продажи LTC"],
                ["📝 Изменить курс USD/RUB"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки изменения процентов для курсов
    elif (message_text in ["+1%", "+5%", "-1%", "-5%"] and is_admin and 
          context.user_data.get("admin_state") in ["edit_ltc_buy_rate", "edit_ltc_sell_rate"]):
        
        state = context.user_data.get("admin_state")
        rates = get_current_rates()
        
        # Определяем какой курс изменяем
        if state == "edit_ltc_buy_rate":
            current_rate = rates["ltc_usd_buy"]
            rate_key = "ltc_usd_buy"
            rate_name = "покупки LTC"
        else:  # edit_ltc_sell_rate
            current_rate = rates["ltc_usd_sell"]
            rate_key = "ltc_usd_sell"
            rate_name = "продажи LTC"
        
        # Рассчитываем изменение в зависимости от кнопки
        if message_text == "+1%":
            new_rate = current_rate * 1.01
        elif message_text == "+5%":
            new_rate = current_rate * 1.05
        elif message_text == "-1%":
            new_rate = current_rate * 0.99
        else:  # "-5%"
            new_rate = current_rate * 0.95
            
        # Обновляем курс
        if rate_key == "ltc_usd_buy":
            update_rates(new_rate, rates["ltc_usd_sell"], rates["usd_rub_buy"], rates["usd_rub_sell"])
        else:
            update_rates(rates["ltc_usd_buy"], new_rate, rates["usd_rub_buy"], rates["usd_rub_sell"])
            
        # Отображаем обновленный курс
        await update.message.reply_text(
            f"✅ Курс {rate_name} успешно обновлен!\n\n"
            f"Было: ${current_rate:.2f}\n"
            f"Стало: ${new_rate:.2f}\n\n"
            "Выберите действие или введите новый курс:",
            reply_markup=ReplyKeyboardMarkup([
                ["+1%", "+5%", "-1%", "-5%"],
                ["🔄 Назад к курсам"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки "Управление операторами"
    elif message_text == "👨‍💼 Управление операторами" and is_admin:
        # Получаем список операторов
        operators = await get_users_by_role("operator")
        
        operator_list = "Список операторов:\n\n"
        if operators:
            for i, operator in enumerate(operators, 1):
                username = operator.get("username", "Нет имени")
                operator_list += f"{i}. {username} (ID: `{operator.get('user_id')}`)\n"
        else:
            operator_list += "Операторов пока нет"
        
        await update.message.reply_text(
            f"👨‍💼 *Управление операторами*\n\n"
            f"{operator_list}\n\n"
            f"Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Добавить оператора", "➖ Удалить оператора"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки "Добавить оператора"
    elif message_text == "➕ Добавить оператора" and is_admin:
        await update.message.reply_text(
            "➕ *Добавление оператора*\n\n"
            "Введите ID пользователя, которого хотите назначить оператором:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад к управлению операторами"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_operator_id"
        return
        
    # Обработка кнопки "Удалить оператора"
    elif message_text == "➖ Удалить оператора" and is_admin:
        await update.message.reply_text(
            "➖ *Удаление оператора*\n\n"
            "Введите ID оператора, которого хотите удалить:",
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Назад к управлению операторами"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "waiting_for_operator_id_to_remove"
        return
        
    # Обработка кнопки "Назад к управлению операторами"
    elif message_text == "🔄 Назад к управлению операторами" and is_admin:
        # Получаем список операторов
        operators = await get_users_by_role("operator")
        
        operator_list = "Список операторов:\n\n"
        if operators:
            for i, operator in enumerate(operators, 1):
                username = operator.get("username", "Нет имени")
                operator_list += f"{i}. {username} (ID: `{operator.get('user_id')}`)\n"
        else:
            operator_list += "Операторов пока нет"
        
        await update.message.reply_text(
            f"👨‍💼 *Управление операторами*\n\n"
            f"{operator_list}\n\n"
            f"Выберите действие:",
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Добавить оператора", "➖ Удалить оператора"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Возврат в главное меню из любого раздела
    elif message_text == "🔄 Главное меню":
        # Возвращаемся в главное меню
        user_data = await get_user(user_id)
        if not user_data:
            user_data = {"role": "user"}
        
        is_operator = user_data.get("role") == "operator"
        is_admin = is_admin or user_data.get("role") == "admin"
        
        keyboard = get_main_menu_keyboard(is_operator, is_admin)
        await update.message.reply_text(
            "🔄 *Главное меню*\n\nВыберите действие:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return
    elif message_text == "💵 Купить LTC" or message_text == "💰 Продать LTC":
        # Обработка покупки/продажи LTC
        order_type = "buy" if message_text == "💵 Купить LTC" else "sell"
        action_text = "покупки" if order_type == "buy" else "продажи"
        
        rates = get_current_rates()
        if order_type == "buy":
            rate_usd = rates["ltc_usd_buy"]
            rate_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
        else:
            rate_usd = rates["ltc_usd_sell"]
            rate_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
        
        await update.message.reply_text(
            f"💰 *Создание заявки на {action_text} LTC*\n\n"
            f"Текущий курс: 1 LTC = ${rate_usd:.2f} (₽{rate_rub:.2f})\n\n"
            f"Введите сумму в LTC, которую вы хотите {'купить' if order_type == 'buy' else 'продать'}:\n"
            f"Например: `0.5` или `1.25`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Сохраняем информацию о типе ордера
        context.user_data["create_order_type"] = order_type
        context.user_data["user_action"] = "waiting_for_order_amount"
        return
    
    elif message_text == "📊 Курсы":
        # Показываем текущие курсы
        rates = get_current_rates()
        ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
        ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
        
        await update.message.reply_text(
            f"💱 *Текущие курсы обмена*\n\n"
            f"*Litecoin (LTC):*\n"
            f"• Покупка: ${rates['ltc_usd_buy']:.2f} (₽{ltc_buy_rub:.2f})\n"
            f"• Продажа: ${rates['ltc_usd_sell']:.2f} (₽{ltc_sell_rub:.2f})\n\n"
            f"*Доллар США (USD):*\n"
            f"• Покупка: ₽{rates['usd_rub_buy']:.2f}\n"
            f"• Продажа: ₽{rates['usd_rub_sell']:.2f}",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    elif message_text == "👤 Профиль":
        # Запускаем обработчик профиля
        user_data = await get_user(user_id)
        if not user_data:
            # Если пользователя нет, предлагаем использовать /start
            await update.message.reply_text(
                "❌ Ваш профиль не найден. Используйте /start для регистрации.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Получаем необходимые данные
        username = user_data.get("username", f"user_{user_id}")
        balance = user_data.get("balance", 0)
        referrals_count = len(user_data.get("referrals", []))
        referral_link = f"https://t.me/your_crypto_exchange_bot?start={user_id}"
        
        # Статистика по сделкам
        buy_orders = user_data.get("buy_orders", 0)
        sell_orders = user_data.get("sell_orders", 0)
        total_orders = buy_orders + sell_orders
        total_volume = user_data.get("total_volume", 0)
        
        # Статистика за месяц
        monthly_buy_orders = user_data.get("monthly_buy_orders", 0)
        monthly_sell_orders = user_data.get("monthly_sell_orders", 0)
        monthly_total_orders = monthly_buy_orders + monthly_sell_orders
        monthly_volume = user_data.get("monthly_volume", 0)
        
        # Скидка пользователя
        discount = user_data.get("discount", 0)
        
        # Формируем текст профиля в формате как на скриншоте
        profile_text = (
            f"👤 *Профиль* @{username} | {user_id}\n\n"
            f"📊 *Статистика:*\n"
            f"🟢 Всего успешных сделок: {total_orders} шт.\n"
            f"📈 Сделок на покупку: {buy_orders} шт.\n"
            f"📉 Сделок на продажу: {sell_orders} шт.\n"
            f"💰 Общая сумма сделок: {total_volume:.2f} $\n\n"
            f"📅 *Статистика за месяц:*\n"
            f"🟢 Всего успешных сделок: {monthly_total_orders} шт.\n"
            f"📈 Сделок на покупку: {monthly_buy_orders} шт.\n"
            f"📉 Сделок на продажу: {monthly_sell_orders} шт.\n"
            f"💰 Общая сумма сделок: {monthly_volume:.2f} $\n\n"
            f"💲 *Ваша скидка:* {discount} %"
        )
        
        # Добавляем кнопки для просмотра информации о скидке и реферальной программе
        buttons = [
            [KeyboardButton("ℹ️ Информация о скидке")],
            [KeyboardButton("👥 Реферальная система")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(profile_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return
        
    elif message_text == "ℹ️ Информация о скидке":
        # Информация о скидках
        discount_text = (
            f"💰 *Скидки в нашем сервисе в зависимости от месячного оборота сделок в $:*\n\n"
            f"• 0 - 100 $: 0% скидка! 🎁\n"
            f"• 100 - 500 $: 5% скидка! 🎁\n"
            f"• 500 - 1000 $: 10% скидка! 🎁\n"
            f"• 1000 - 3000 $: 15% скидка! 🎁\n"
            f"• От 3000 $ и выше: 20% скидка! 🔥\n\n"
            f"⏳ Поторопитесь воспользоваться нашими выгодными предложениями! Ваша скидка обновляется каждый месяц"
        )
        
        # Кнопка назад
        buttons = [[KeyboardButton("↩️ Назад")]]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(discount_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return
        
    elif message_text == "👥 Реферальная система":
        # Реферальная система
        user_data = await get_user(user_id)
        if not user_data:
            user_data = {"username": f"user_{user_id}", "balance": 0, "referrals": []}
            
        referrals_count = len(user_data.get("referrals", []))
        earnings = user_data.get("referral_earnings", 0)
        referral_link = f"https://t.me/your_crypto_exchange_bot?start={user_id}"
        
        referral_text = (
            f"👋 *Привет! Вот твоя статистика:*\n\n"
            f"📊 *Приглашено людей:* {referrals_count}\n\n"
            f"💰 *Общий заработок:* {earnings:.2f} USD\n\n"
            f"💲 *Текущий баланс:* {user_data.get('balance', 0):.2f} USD\n\n"
            f"🔗 *Твоя ссылка для приглашений:*\n"
            f"{referral_link}\n\n"
            f"Приглашай друзей и зарабатывай больше! 🚀"
        )
        
        # Добавляем кнопки
        buttons = [
            [KeyboardButton("💵 Запросить вывод")],
            [KeyboardButton("❓ Как это работает?")],
            [KeyboardButton("↩️ Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        # Избегаем ошибок с форматированием markdown
        try:
            await update.message.reply_text(
                referral_text, 
                reply_markup=reply_markup, 
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке реферального текста: {e}")
            # Отправляем без разметки при ошибке
            await update.message.reply_text(
                referral_text.replace('*', '').replace('_', ''), 
                reply_markup=reply_markup
            )
        return
        
    elif message_text == "❓ Как это работает?":
        # Объяснение работы реферальной системы
        explanation_text = (
            "*Реферальная система*\n\n"
            "Наша реферальная система предоставляет пользователям уникальную возможность зарабатывать на каждом обмене, "
            "осуществляемом их рефералами. Станьте частью нашего сообщества и начните получать 20% комиссионных "
            "от комиссии обменника за все сделки.\n\n"
            "*Основные элементы:*\n"
            "1. Получите уникальную реферальную ссылку в профиле\n"
            "2. Делитесь ссылкой с друзьями и в социальных сетях\n"
            "3. Получайте вознаграждение за каждую сделку реферала\n"
            "4. Запрашивайте вывод средств через бота\n\n"
            "*Преимущества:*\n"
            "• Без ограничений на количество рефералов\n"
            "• Постоянный пассивный доход\n"
            "• Прозрачная система начислений\n"
            "• Быстрые выплаты\n\n"
            "Присоединяйтесь к нашей реферальной программе и начните зарабатывать уже сегодня!"
        )
        
        # Кнопка назад
        buttons = [[KeyboardButton("↩️ Назад")]]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(explanation_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        return
        
    elif message_text == "↩️ Назад":
        # Возвращаемся назад - проверим текущий контекст, если есть
        if "current_context" in context.user_data and context.user_data["current_context"] == "referral":
            # Если мы в контексте реферальной системы, возвращаемся к ней
            return await handle_text_buttons(update, context)
        else:
            # По умолчанию возвращаемся в главное меню
            keyboard = get_main_menu_keyboard(is_admin=is_admin)
            await update.message.reply_text(
                "Выберите действие:",
                reply_markup=keyboard
            )
            return
    
    elif message_text == "📝 Установить курсы" and is_admin:
        # Обрабатываем установку курсов
        rates = get_current_rates()
        await update.message.reply_text(
            f"💱 *Текущие курсы обмена*\n\n"
            f"*Litecoin (LTC):*\n"
            f"• Покупка: ${rates['ltc_usd_buy']:.2f}\n"
            f"• Продажа: ${rates['ltc_usd_sell']:.2f}\n\n"
            f"*Доллар США (USD):*\n"
            f"• Покупка: ₽{rates['usd_rub_buy']:.2f}\n"
            f"• Продажа: ₽{rates['usd_rub_sell']:.2f}\n\n"
            f"Для изменения курсов отправьте 4 числа в следующем формате:\n"
            f"`ltc_usd_buy ltc_usd_sell usd_rub_buy usd_rub_sell`\n\n"
            f"Например: `80 78 90 88`",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Установим состояние ожидания ввода курсов
        context.user_data["admin_action"] = "waiting_for_rates"
        return
        
    elif message_text == "👥 Управление пользователями" and is_admin:
        # Обрабатываем управление пользователями
        await update.message.reply_text(
            "👥 *Управление пользователями*\n\n"
            "Для назначения роли пользователю введите команду в формате:\n"
            "`ID роль`\n\n"
            "Например: `12345678 operator`\n\n"
            "Доступные роли:\n"
            "• `user` - обычный пользователь\n"
            "• `operator` - оператор\n"
            "• `admin` - администратор",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Установим состояние ожидания ввода ид пользователя и роли
        context.user_data["admin_action"] = "waiting_for_user_role"
        return
        
    elif message_text == "📊 Статистика" and is_admin:
        # Показываем статистику
        # Здесь можно было бы добавить реальные данные статистики, если они доступны
        await update.message.reply_text(
            "📊 *Статистика*\n\n"
            "Общая статистика работы бота:\n"
            "• Количество пользователей: ...\n"
            "• Активных заявок: ...\n"
            "• Завершенных заявок: ...\n"
            "• Оборот: ... LTC\n\n"
            "Детальную статистику смотрите в панели администратора.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "📨 Создать рассылку" and is_admin:
        # Обрабатываем создание рассылки
        await update.message.reply_text(
            "📨 *Создание рассылки*\n\n"
            "Введите текст сообщения, которое будет отправлено всем пользователям.\n"
            "Поддерживается Markdown-форматирование.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Установим состояние ожидания ввода текста рассылки
        context.user_data["admin_action"] = "waiting_for_broadcast_text"
        return
        
    # Обработка кнопки "Найти пользователя" в админ-панели
    elif message_text == "👤 Найти пользователя" and is_admin:
        # Логируем информацию для отладки
        logging.info(f"Поиск пользователя: {message_text}")
        logging.info(f"Тип запроса: {type(message_text)}")
        
        await update.message.reply_text(
            "👤 *Поиск пользователя*\n\n"
            "Введите ID или @username пользователя:\n"
            "_Например: 123456789 или @username_",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 Управление пользователями"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        # Устанавливаем состояние ожидания ввода ID или username пользователя
        context.user_data["admin_state"] = "waiting_for_user_id_search"
        return
        
    # Обработка кнопки "Изменить роль" в админ-панели
    elif message_text == "🧩 Изменить роль" and is_admin:
        await update.message.reply_text(
            "🧩 *Изменение роли пользователя*\n\n"
            "Введите ID пользователя и новую роль в формате:\n"
            "`ID роль`\n\n"
            "Например: `123456789 operator`\n\n"
            "Доступные роли:\n"
            "• `user` - обычный пользователь\n"
            "• `operator` - оператор\n"
            "• `admin` - администратор",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 Управление пользователями"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        # Устанавливаем состояние ожидания ввода ID и роли пользователя
        context.user_data["admin_state"] = "waiting_for_user_role_change"
        return
        
    # Обработка кнопки "Изменить баланс" в админ-панели
    elif message_text == "💰 Изменить баланс" and is_admin:
        await update.message.reply_text(
            "💰 *Изменение баланса пользователя*\n\n"
            "Введите ID пользователя и сумму изменения в формате:\n"
            "`ID сумма`\n\n"
            "Примеры:\n"
            "• `123456789 +500` - пополнить баланс на 500\n"
            "• `123456789 -200` - списать с баланса 200",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 Управление пользователями"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        # Устанавливаем состояние ожидания ввода ID и суммы
        context.user_data["admin_state"] = "waiting_for_balance_change"
        return
        
    # Обработка кнопки "Заблокировать" в админ-панели
    elif message_text == "❌ Заблокировать" and is_admin:
        await update.message.reply_text(
            "❌ *Блокировка пользователя*\n\n"
            "Введите ID пользователя для блокировки:",
            reply_markup=ReplyKeyboardMarkup([
                ["👥 Управление пользователями"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        # Устанавливаем состояние ожидания ввода ID пользователя
        context.user_data["admin_state"] = "waiting_for_user_block"
        return
        
    # Обработчики для покупки/продажи крипты
    elif message_text == "📝 Купить крипту":
        # Получаем текущие курсы
        rates = get_current_rates()
        
        # Рассчитываем курс LTC в рублях
        ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
        
        # Создаем клавиатуру
        buttons = [
            [KeyboardButton("0.1 LTC"), KeyboardButton("0.25 LTC"), KeyboardButton("0.5 LTC")],
            [KeyboardButton("1 LTC"), KeyboardButton("2 LTC"), KeyboardButton("5 LTC")],
            [KeyboardButton("Другая сумма")],
            [KeyboardButton("↩️ Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        buy_message = (
            f"📈 *Покупка Litecoin (LTC)*\n\n"
            f"Текущий курс: ${rates['ltc_usd_buy']:.2f} (≈ {ltc_buy_rub:.2f} ₽)\n\n"
            f"Выберите количество LTC для покупки или введите свою сумму.\n"
            f"Минимальная сумма покупки: 0.1 LTC"
        )
        
        # Устанавливаем состояние для ожидания ввода суммы
        context.user_data["current_operation"] = "buy_ltc"
        
        await update.message.reply_text(
            buy_message,
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "📉 Продать крипту":
        # Получаем текущие курсы
        rates = get_current_rates()
        
        # Рассчитываем курс LTC в рублях
        ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
        
        # Создаем клавиатуру
        buttons = [
            [KeyboardButton("0.1 LTC"), KeyboardButton("0.25 LTC"), KeyboardButton("0.5 LTC")],
            [KeyboardButton("1 LTC"), KeyboardButton("2 LTC"), KeyboardButton("5 LTC")],
            [KeyboardButton("Другая сумма")],
            [KeyboardButton("↩️ Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        sell_message = (
            f"📉 *Продажа Litecoin (LTC)*\n\n"
            f"Текущий курс: ${rates['ltc_usd_sell']:.2f} (≈ {ltc_sell_rub:.2f} ₽)\n\n"
            f"Выберите количество LTC для продажи или введите свою сумму.\n"
            f"Минимальная сумма продажи: 0.1 LTC"
        )
        
        # Устанавливаем состояние для ожидания ввода суммы
        context.user_data["current_operation"] = "sell_ltc"
        
        await update.message.reply_text(
            sell_message,
            reply_markup=reply_markup, 
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Обработка пункта "Другая сумма"
    elif message_text == "Другая сумма":
        # Проверяем какая операция выполняется
        operation = context.user_data.get("current_operation", "")
        
        # Получаем текущие курсы для отображения
        rates = get_current_rates()
        
        # Создаем клавиатуру с кнопкой отмены
        buttons = [
            [KeyboardButton("❌ Отменить")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        if operation == "buy_ltc":
            # Рассчитываем курс LTC в рублях
            ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
            
            # Устанавливаем новое состояние
            context.user_data["current_operation"] = "custom_buy_ltc"
            
            await update.message.reply_text(
                f"📈 *Покупка Litecoin (LTC) - Произвольная сумма*\n\n"
                f"Текущий курс: ${rates['ltc_usd_buy']:.2f} (≈ {ltc_buy_rub:.2f} ₽)\n\n"
                f"Введите желаемое количество LTC (например, 0.75).\n"
                f"Минимальная сумма: 0.1 LTC\n\n"
                f"*Примеры сумм:*\n"
                f"• 0.1 LTC ≈ {0.1 * ltc_buy_rub:.2f} ₽\n"
                f"• 0.5 LTC ≈ {0.5 * ltc_buy_rub:.2f} ₽\n"
                f"• 1 LTC ≈ {1 * ltc_buy_rub:.2f} ₽",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
        elif operation == "sell_ltc":
            # Рассчитываем курс LTC в рублях
            ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
            
            # Устанавливаем новое состояние
            context.user_data["current_operation"] = "custom_sell_ltc"
            
            await update.message.reply_text(
                f"📉 *Продажа Litecoin (LTC) - Произвольная сумма*\n\n"
                f"Текущий курс: ${rates['ltc_usd_sell']:.2f} (≈ {ltc_sell_rub:.2f} ₽)\n\n"
                f"Введите желаемое количество LTC (например, 0.75).\n"
                f"Минимальная сумма: 0.1 LTC\n\n"
                f"*Примеры сумм:*\n"
                f"• 0.1 LTC ≈ {0.1 * ltc_sell_rub:.2f} ₽\n"
                f"• 0.5 LTC ≈ {0.5 * ltc_sell_rub:.2f} ₽\n"
                f"• 1 LTC ≈ {1 * ltc_sell_rub:.2f} ₽",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
        
        return
    
    # Обработка ввода произвольной суммы
    elif (context.user_data.get("current_operation") == "custom_buy_ltc" or 
          context.user_data.get("current_operation") == "custom_sell_ltc"):
        try:
            # Преобразуем введенный текст в число
            ltc_amount = float(message_text.strip())
            
            # Проверяем минимальную сумму
            if ltc_amount < 0.1:
                await update.message.reply_text(
                    "❌ Минимальная сумма для операции: 0.1 LTC.\n"
                    "Пожалуйста, введите сумму не менее 0.1 LTC.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Получаем текущие курсы
            rates = get_current_rates()
            
            # Определяем, какая операция выполняется
            operation = context.user_data.get("current_operation", "")
            real_operation = "buy_ltc" if operation == "custom_buy_ltc" else "sell_ltc"
            context.user_data["current_operation"] = real_operation
            
            # Дальнейшая обработка аналогична стандартным суммам
            if real_operation == "buy_ltc":
                # Рассчитываем курс LTC в рублях и общую сумму
                ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
                total_rub = ltc_amount * ltc_buy_rub
                total_usd = ltc_amount * rates["ltc_usd_buy"]
                
                # Создаем клавиатуру для подтверждения
                buttons = [
                    [KeyboardButton("✅ Подтвердить покупку")],
                    [KeyboardButton("❌ Отменить")]
                ]
                reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
                
                # Сохраняем данные о заказе
                context.user_data["order_data"] = {
                    "type": "buy",
                    "ltc_amount": ltc_amount,
                    "total_rub": total_rub,
                    "total_usd": total_usd,
                    "rate_used": rates["ltc_usd_buy"]
                }
                
                confirm_message = (
                    f"🔍 *Подтверждение покупки*\n\n"
                    f"Вы собираетесь купить *{ltc_amount} LTC*\n"
                    f"По курсу: ${rates['ltc_usd_buy']:.2f} (≈ {ltc_buy_rub:.2f} ₽)\n\n"
                    f"Общая стоимость:\n"
                    f"• ${total_usd:.2f}\n"
                    f"• {total_rub:.2f} ₽\n\n"
                    f"Пожалуйста, подтвердите вашу покупку."
                )
                
                await update.message.reply_text(
                    confirm_message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
                
            elif real_operation == "sell_ltc":
                # Рассчитываем курс LTC в рублях и общую сумму
                ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
                total_rub = ltc_amount * ltc_sell_rub
                total_usd = ltc_amount * rates["ltc_usd_sell"]
                
                # Создаем клавиатуру для подтверждения
                buttons = [
                    [KeyboardButton("✅ Подтвердить продажу")],
                    [KeyboardButton("❌ Отменить")]
                ]
                reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
                
                # Сохраняем данные о заказе
                context.user_data["order_data"] = {
                    "type": "sell",
                    "ltc_amount": ltc_amount,
                    "total_rub": total_rub,
                    "total_usd": total_usd,
                    "rate_used": rates["ltc_usd_sell"]
                }
                
                confirm_message = (
                    f"🔍 *Подтверждение продажи*\n\n"
                    f"Вы собираетесь продать *{ltc_amount} LTC*\n"
                    f"По курсу: ${rates['ltc_usd_sell']:.2f} (≈ {ltc_sell_rub:.2f} ₽)\n\n"
                    f"Вы получите:\n"
                    f"• ${total_usd:.2f}\n"
                    f"• {total_rub:.2f} ₽\n\n"
                    f"Пожалуйста, подтвердите вашу продажу."
                )
                
                await update.message.reply_text(
                    confirm_message,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
                
        except ValueError:
            # Обработка ошибки ввода (введено не число)
            await update.message.reply_text(
                "❌ Пожалуйста, введите корректное число.\n"
                "Например: 0.75",
                parse_mode=ParseMode.MARKDOWN
            )
            return
    
    # Обработка стандартных сумм LTC
    elif message_text in ["0.1 LTC", "0.25 LTC", "0.5 LTC", "1 LTC", "2 LTC", "5 LTC"]:
        # Преобразуем текст в число, убирая " LTC" в конце
        ltc_amount = float(message_text.replace(" LTC", ""))
        
        # Проверяем какая операция выполняется
        operation = context.user_data.get("current_operation", "")
        
        if operation == "buy_ltc":
            # Получаем текущие курсы
            rates = get_current_rates()
            
            # Рассчитываем курс LTC в рублях и общую сумму
            ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
            total_rub = ltc_amount * ltc_buy_rub
            total_usd = ltc_amount * rates["ltc_usd_buy"]
            
            # Создаем клавиатуру для подтверждения
            buttons = [
                [KeyboardButton("✅ Подтвердить покупку")],
                [KeyboardButton("❌ Отменить")]
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            
            # Сохраняем данные о заказе
            context.user_data["order_data"] = {
                "type": "buy",
                "ltc_amount": ltc_amount,
                "total_rub": total_rub,
                "total_usd": total_usd,
                "rate_used": rates["ltc_usd_buy"]
            }
            
            confirm_message = (
                f"🔍 *Подтверждение покупки*\n\n"
                f"Вы собираетесь купить *{ltc_amount} LTC*\n"
                f"По курсу: ${rates['ltc_usd_buy']:.2f} (≈ {ltc_buy_rub:.2f} ₽)\n\n"
                f"Общая стоимость:\n"
                f"• ${total_usd:.2f}\n"
                f"• {total_rub:.2f} ₽\n\n"
                f"Пожалуйста, подтвердите вашу покупку."
            )
            
            await update.message.reply_text(
                confirm_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return
            
        elif operation == "sell_ltc":
            # Получаем текущие курсы
            rates = get_current_rates()
            
            # Рассчитываем курс LTC в рублях и общую сумму
            ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
            total_rub = ltc_amount * ltc_sell_rub
            total_usd = ltc_amount * rates["ltc_usd_sell"]
            
            # Создаем клавиатуру для подтверждения
            buttons = [
                [KeyboardButton("✅ Подтвердить продажу")],
                [KeyboardButton("❌ Отменить")]
            ]
            reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            
            # Сохраняем данные о заказе
            context.user_data["order_data"] = {
                "type": "sell",
                "ltc_amount": ltc_amount,
                "total_rub": total_rub,
                "total_usd": total_usd,
                "rate_used": rates["ltc_usd_sell"]
            }
            
            confirm_message = (
                f"🔍 *Подтверждение продажи*\n\n"
                f"Вы собираетесь продать *{ltc_amount} LTC*\n"
                f"По курсу: ${rates['ltc_usd_sell']:.2f} (≈ {ltc_sell_rub:.2f} ₽)\n\n"
                f"Вы получите:\n"
                f"• ${total_usd:.2f}\n"
                f"• {total_rub:.2f} ₽\n\n"
                f"Пожалуйста, подтвердите вашу продажу."
            )
            
            await update.message.reply_text(
                confirm_message,
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return
    
    # Обработка подтверждения покупки/продажи
    elif message_text == "✅ Подтвердить покупку":
        # Создаем новый заказ на покупку
        user_id = update.effective_user.id
        user = await get_user(user_id)
        username = user.get("username") if user else update.effective_user.username or f"user_{user_id}"
        
        # Получаем данные заказа
        order_data = context.user_data.get("order_data", {})
        
        if not order_data:
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке заказа. Пожалуйста, начните заново.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Создаем заказ в базе данных
        order = await create_order(user_id, username, "buy", order_data.get("total_rub", 0))
        
        # Возвращаем пользователя в главное меню
        keyboard = get_main_menu_keyboard(is_admin=is_admin)
        
        await update.message.reply_text(
            f"✅ *Заявка на покупку успешно создана!*\n\n"
            f"• Номер заявки: {order['order_number']}\n"
            f"• Количество: {order_data.get('ltc_amount', 0)} LTC\n"
            f"• Сумма: {order_data.get('total_rub', 0):.2f} ₽\n\n"
            f"Оператор свяжется с вами в ближайшее время для уточнения деталей.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Очищаем данные операции
        if "current_operation" in context.user_data:
            del context.user_data["current_operation"]
        if "order_data" in context.user_data:
            del context.user_data["order_data"]
        
        return
        
    elif message_text == "✅ Подтвердить продажу":
        # Создаем новый заказ на продажу
        user_id = update.effective_user.id
        user = await get_user(user_id)
        username = user.get("username") if user else update.effective_user.username or f"user_{user_id}"
        
        # Получаем данные заказа
        order_data = context.user_data.get("order_data", {})
        
        if not order_data:
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке заказа. Пожалуйста, начните заново.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Создаем заказ в базе данных
        order = await create_order(user_id, username, "sell", order_data.get("total_rub", 0))
        
        # Возвращаем пользователя в главное меню
        keyboard = get_main_menu_keyboard(is_admin=is_admin)
        
        await update.message.reply_text(
            f"✅ *Заявка на продажу успешно создана!*\n\n"
            f"• Номер заявки: {order['order_number']}\n"
            f"• Количество: {order_data.get('ltc_amount', 0)} LTC\n"
            f"• Сумма: {order_data.get('total_rub', 0):.2f} ₽\n\n"
            f"Оператор свяжется с вами в ближайшее время для уточнения деталей.",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Очищаем данные операции
        if "current_operation" in context.user_data:
            del context.user_data["current_operation"]
        if "order_data" in context.user_data:
            del context.user_data["order_data"]
        
        return
        
    elif message_text == "❌ Отменить":
        # Отменяем операцию и возвращаем пользователя в главное меню
        keyboard = get_main_menu_keyboard(is_admin=is_admin)
        
        await update.message.reply_text(
            "❌ Операция отменена.",
            reply_markup=keyboard
        )
        
        # Очищаем данные операции
        if "current_operation" in context.user_data:
            del context.user_data["current_operation"]
        if "order_data" in context.user_data:
            del context.user_data["order_data"]
            
        return
        
    # Обработка кнопки "Мои заявки"
    elif message_text == "📋 Мои заявки":
        # Получаем заявки текущего пользователя
        from bot.database import get_user_orders
        user_orders = await get_user_orders(user_id)
        
        if not user_orders:
            await update.message.reply_text(
                "📋 *Ваши заявки*\n\n"
                "У вас пока нет заявок. Создайте новую заявку через кнопки покупки/продажи крипты.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Сортируем заявки по статусу
        active_orders = [order for order in user_orders if order.get("status") == "active"]
        in_progress_orders = [order for order in user_orders if order.get("status") == "in_progress"]
        completed_orders = [order for order in user_orders if order.get("status") == "completed"]
        
        # Создаем сообщение с информацией о заявках
        orders_text = "📋 *Ваши заявки:*\n\n"
        
        # Добавляем активные заявки
        if active_orders:
            orders_text += "*Активные заявки:*\n"
            for i, order in enumerate(active_orders):
                order_type = "Покупка" if order.get("type") == "buy" else "Продажа"
                amount = order.get("ltc_amount", order.get("amount", 0))
                total_rub = order.get("total_rub", 0)
                
                orders_text += (
                    f"{i+1}. *Заявка {order.get('order_number', 'б/н')}*\n"
                    f"   Тип: {order_type} LTC\n"
                    f"   Количество: {amount} LTC\n"
                    f"   Сумма: {total_rub:.2f} ₽\n"
                    f"   Статус: Ожидает обработки\n\n"
                )
        
        # Добавляем заявки в обработке
        if in_progress_orders:
            orders_text += "*В обработке:*\n"
            for i, order in enumerate(in_progress_orders):
                order_type = "Покупка" if order.get("type") == "buy" else "Продажа"
                amount = order.get("ltc_amount", order.get("amount", 0))
                total_rub = order.get("total_rub", 0)
                
                orders_text += (
                    f"{i+1}. *Заявка {order.get('order_number', 'б/н')}*\n"
                    f"   Тип: {order_type} LTC\n"
                    f"   Количество: {amount} LTC\n"
                    f"   Сумма: {total_rub:.2f} ₽\n"
                    f"   Статус: В обработке\n\n"
                )
        
        # Добавляем завершенные заявки (последние 3)
        if completed_orders:
            # Показываем только последние 3 завершенных заявки
            recent_completed = completed_orders[:3]
            orders_text += "*Последние завершенные:*\n"
            for i, order in enumerate(recent_completed):
                order_type = "Покупка" if order.get("type") == "buy" else "Продажа"
                amount = order.get("ltc_amount", order.get("amount", 0))
                total_rub = order.get("total_rub", 0)
                
                orders_text += (
                    f"{i+1}. *Заявка {order.get('order_number', 'б/н')}*\n"
                    f"   Тип: {order_type} LTC\n"
                    f"   Количество: {amount} LTC\n"
                    f"   Сумма: {total_rub:.2f} ₽\n"
                    f"   Статус: Завершена\n\n"
                )
                
            if len(completed_orders) > 3:
                orders_text += f"_Показано 3 из {len(completed_orders)} завершенных заявок._\n\n"
        
        # Добавляем общую статистику
        total_orders = len(user_orders)
        total_volume = sum(order.get("ltc_amount", order.get("amount", 0)) for order in user_orders)
        
        orders_text += (
            f"*Общая статистика:*\n"
            f"• Всего заявок: {total_orders}\n"
            f"• Общий объем: {total_volume:.4f} LTC\n"
        )
        
        try:
            await update.message.reply_text(
                orders_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Ошибка при отображении заявок: {e}")
            # Отправляем более простую версию сообщения без разметки при ошибке
            await update.message.reply_text(
                "Ваши заявки:\n\n" + 
                orders_text.replace('*', '').replace('_', '')
            )
        return
        
    # Обработка кнопки активных заявок для администраторов
    elif message_text == "📋 Активные заявки":
        # Проверяем, является ли пользователь оператором или администратором
        if is_admin:
            # Получаем активные заявки из базы данных
            from bot.database import get_active_orders
            active_orders = await get_active_orders()
            
            if not active_orders:
                await update.message.reply_text(
                    "📋 *Активные заявки*\n\n"
                    "На данный момент нет активных заявок.",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            
            # Создаем сообщение с информацией о заявках
            orders_text = "📋 *Активные заявки:*\n\n"
            
            for i, order in enumerate(active_orders[:10]):  # Показываем до 10 заявок
                order_type = "Покупка" if order.get("type", "") == "buy" else "Продажа"
                user_id = order.get("user_id", "Неизвестно")
                username = order.get("username", f"user_{user_id}")
                amount = order.get("ltc_amount", order.get("amount", 0))
                total_rub = order.get("total_rub", 0)
                
                orders_text += (
                    f"{i+1}. *Заявка {order.get('order_number', 'б/н')}*\n"
                    f"   Тип: {order_type} LTC\n"
                    f"   Количество: {amount} LTC\n"
                    f"   Сумма: {total_rub:.2f} ₽\n"
                    f"   Пользователь: @{username} (ID: {user_id})\n\n"
                )
            
            # Добавляем информацию о количестве всех заявок
            if len(active_orders) > 10:
                orders_text += f"Показано 10 из {len(active_orders)} активных заявок."
            
            await update.message.reply_text(
                orders_text,
                parse_mode=ParseMode.MARKDOWN
            )
            return
    
    # Обработка кнопок информационного меню
    elif message_text == "❓ Информация":
        # Показываем информационное меню
        buttons = [
            [KeyboardButton("ℹ️ Информация о боте")],
            [KeyboardButton("👨‍💻 Тех.Поддержка")],
            [KeyboardButton("📢 Реклама")],
            [KeyboardButton("📋 Правила")],
            [KeyboardButton("⭐ Отзывы наших клиентов")],
            [KeyboardButton("💬 Общий чат")],
            [KeyboardButton("↩️ Назад")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(
            "ℹ️ *Информация о боте*\n\n"
            "Здесь вы можете получить дополнительную информацию о "
            "нашем сервисе, связаться с технической поддержкой или узнать "
            "о возможностях размещения рекламы.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "ℹ️ Информация о боте":
        await update.message.reply_text(
            "ℹ️ *Информация о боте*\n\n"
            "Наш бот предоставляет услуги обмена криптовалюты Litecoin (LTC).\n\n"
            "• Быстрый обмен без лишних проверок\n"
            "• Выгодные курсы\n"
            "• Реферальная программа с вознаграждениями\n"
            "• Круглосуточная поддержка\n\n"
            "Выберите интересующий вас раздел из меню ниже.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "👨‍💻 Тех.Поддержка":
        await update.message.reply_text(
            "👨‍💻 *Техническая поддержка*\n\n"
            "Если у вас возникли вопросы или проблемы, напишите нам:\n"
            "@admin_support_username\n\n"
            "Время работы: 24/7\n"
            "Среднее время ответа: 15 минут",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "📢 Реклама":
        await update.message.reply_text(
            "📢 *Размещение рекламы*\n\n"
            "Для размещения рекламы в нашем боте или каналах, свяжитесь с администратором:\n"
            "@admin_ads_username\n\n"
            "Наша аудитория - более 1000 активных пользователей, интересующихся криптовалютой.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "📋 Правила":
        await update.message.reply_text(
            "📋 *Правила использования сервиса*\n\n"
            "1. Запрещено использование бота для нелегальной деятельности\n"
            "2. Минимальная сумма обмена: 0.01 LTC\n"
            "3. Комиссия за обмен: 1-3% в зависимости от суммы\n"
            "4. Время обработки заявки: до 30 минут\n"
            "5. При возникновении спорных ситуаций решение принимает администрация\n\n"
            "Используя наш сервис, вы автоматически соглашаетесь с данными правилами.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    # Обработка кнопки Наши Ресурсы
    elif message_text == "📋 Наши Ресурсы":
        buttons = [
            [KeyboardButton("📰 Новостной канал")],
            [KeyboardButton("⭐ Отзывы наших клиентов")],
            [KeyboardButton("💬 Общий чат")]
        ]
        reply_markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
        
        await update.message.reply_text(
            "📋 *Наши официальные ресурсы:*\n\n"
            "📰 Новостной канал\n"
            "└ Актуальные новости и выгодные акции\n\n"
            "⭐ Канал с отзывами\n"
            "└ Честные отзывы наших клиентов\n\n"
            "💬 Общий чат\n"
            "└ Обсуждения и взаимопомощь\n\n"
            "🔔 Подпишитесь на наши ресурсы, чтобы быть в курсе всех обновлений!",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "📰 Новостной канал":
        await update.message.reply_text(
            "📰 *Новостной канал*\n\n"
            "Подписывайтесь на наш официальный канал с новостями:\n"
            "https://t.me/crypto_exchange_news\n\n"
            "Там вы найдете:\n"
            "• Актуальные курсы криптовалют\n"
            "• Выгодные акции и предложения\n"
            "• Новости из мира криптовалют\n"
            "• Анонсы новых функций бота",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "⭐ Отзывы наших клиентов":
        await update.message.reply_text(
            "⭐ *Отзывы наших клиентов*\n\n"
            "Ознакомьтесь с честными отзывами пользователей нашего сервиса:\n"
            "https://t.me/crypto_exchange_reviews\n\n"
            "Мы гордимся нашей репутацией и стремимся предоставлять сервис высочайшего качества.",
            parse_mode=ParseMode.MARKDOWN
        )
        return
        
    elif message_text == "💬 Общий чат":
        await update.message.reply_text(
            "💬 *Общий чат*\n\n"
            "Присоединяйтесь к нашему общему чату:\n"
            "https://t.me/crypto_exchange_chat\n\n"
            "В чате вы можете:\n"
            "• Общаться с другими пользователями\n"
            "• Задавать вопросы и получать ответы\n"
            "• Делиться опытом использования сервиса\n"
            "• Получать помощь от сообщества",
            parse_mode=ParseMode.MARKDOWN
        )
        return

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений от администратора в разных состояниях"""
    message_text = update.message.text
    user_id = update.effective_user.id
    
    # Проверяем наличие и состояние пользователя
    if not context.user_data:
        return
    
    # Проверяем админские права
    is_admin = await check_admin(user_id)
    if not is_admin:
        return
    
    # Проверяем состояние админа
    admin_state = context.user_data.get("admin_state")
    if not admin_state:
        return
    
    # Обработка состояний админа
    if admin_state == "waiting_for_min_amount":
        # Обработка ввода минимальной суммы транзакции
        if message_text == "🔄 Отмена":
            # Отмена ввода, возврат в меню настроек
            await update.message.reply_text(
                "🔄 *Действие отменено*\n\n"
                "Вы вернулись в меню настроек.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["👨‍💼 Управление админами", "📋 Настройка комиссий"],
                    ["💰 Мин. сумма транзакции", "🔗 Реферальная система"],
                    ["📱 Настройка уведомлений"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            del context.user_data["admin_state"]
            return
        
        try:
            # Парсим введенное значение
            new_min_amount = float(message_text.strip())
            
            # Проверяем на корректность (положительное число)
            if new_min_amount <= 0:
                raise ValueError("Сумма должна быть положительной")
                
            # Обновляем значение
            set_min_amount(new_min_amount)
            
            # Подтверждаем изменение
            await update.message.reply_text(
                f"✅ *Минимальная сумма транзакции успешно обновлена!*\n\n"
                f"Новое значение: *{new_min_amount:.2f} PMR рублей*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["👨‍💼 Управление админами", "📋 Настройка комиссий"],
                    ["💰 Мин. сумма транзакции", "🔗 Реферальная система"],
                    ["📱 Настройка уведомлений"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
            # Сбрасываем состояние
            del context.user_data["admin_state"]
            
        except (ValueError, TypeError) as e:
            # Ошибка ввода
            await update.message.reply_text(
                f"❌ *Ошибка!*\n\n"
                f"Введено некорректное значение. Пожалуйста, введите положительное число.\n"
                f"Например: 500 или 1000.50",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["🔄 Отмена"]
                ], resize_keyboard=True)
            )
        
    elif admin_state == "waiting_for_user_id_search":
        # Обработка поиска пользователя
        try:
            # Проверка на кнопки навигации
            if message_text == "🔄 Назад в админ-панель":
                # Возвращаемся назад в админ-панель
                if "admin_state" in context.user_data:
                    del context.user_data["admin_state"]
                await handle_admin_panel(update, context)
                return
                
            if message_text == "👥 Управление пользователями":
                # Возвращаемся назад в раздел управления пользователями
                if "admin_state" in context.user_data:
                    del context.user_data["admin_state"]
                await update.message.reply_text(
                    "👥 *Управление пользователями*\n\n"
                    "Выберите действие из меню ниже:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👤 Найти пользователя", "🧩 Изменить роль"],
                        ["💰 Изменить баланс", "🚫 Заблокировать/Разблокировать"],
                        ["👥 Список пользователей"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Получаем текст запроса (ID или @username)
            search_query = message_text.strip() if message_text else ""
            
            # Логгируем входные данные для отладки
            logger.info(f"Поиск пользователя: {search_query}")
            logger.info(f"Тип запроса: {type(search_query)}")
            
            # Для справки, покажем ID текущего пользователя
            user_id = update.effective_user.id
            
            # Проверка на пустой запрос
            if not search_query:
                logger.warning("Получен пустой поисковый запрос")
                await update.message.reply_text(
                    f"ℹ️ *Информация для поиска*\n\n"
                    f"Ваш ID: `{user_id}`\n\n"
                    f"❌ Необходимо указать ID или @username пользователя.\n"
                    f"Например: `{user_id}` или `@username`\n\n"
                    f"Пожалуйста, введите корректные данные для поиска:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Проверяем формат запроса
            if isinstance(search_query, str) and search_query.startswith('@'):
                username = search_query[1:]  # Убираем @ из начала
                logger.info(f"Ищем пользователя по username: {username}")
                # Логика поиска по имени пользователя
                users_data = await get_users()
                if not users_data:
                    users_data = {}
                logger.info(f"Найдено пользователей: {len(users_data)}")
                found_user = None
                
                # Проверяем все ключи и значения в словаре users_data
                for user_id_str, user_data in users_data.items():
                    try:
                        user_id = int(user_id_str)
                        user_username = user_data.get('username', '')
                        logger.info(f"Проверяем пользователя ID:{user_id} с username:{user_username}")
                        
                        if user_username and user_username.lower() == username.lower():
                            found_user = (user_id, user_data)
                            logger.info(f"Пользователь найден: {user_id}")
                            break
                    except (ValueError, TypeError) as e:
                        logger.error(f"Ошибка при обработке пользователя {user_id_str}: {e}")
                        continue
                
                if found_user:
                    user_id, user_data = found_user
                    role = user_data.get('role', 'user')
                    balance = user_data.get('balance', 0)
                    username = user_data.get('username', 'Нет имени')
                    registration_date = user_data.get('registration_date', 'Неизвестно')
                    
                    await update.message.reply_text(
                        f"👤 *Информация о пользователе*\n\n"
                        f"*ID:* `{user_id}`\n"
                        f"*Имя:* {username}\n"
                        f"*Роль:* {role}\n"
                        f"*Баланс:* {balance} LTC\n"
                        f"*Дата регистрации:* {registration_date}\n\n"
                        f"Для управления пользователем используйте админ-панель.",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=ReplyKeyboardMarkup([
                            ["👥 Управление пользователями"],
                            ["🔄 Назад в админ-панель"]
                        ], resize_keyboard=True)
                    )
                else:
                    logger.warning(f"Пользователь с именем '{search_query[1:]}' не найден")
                    await update.message.reply_text(
                        f"❌ Пользователь с именем {search_query} не найден.",
                        reply_markup=ReplyKeyboardMarkup([
                            ["👥 Управление пользователями"],
                            ["🔄 Назад в админ-панель"]
                        ], resize_keyboard=True)
                    )
            elif search_query.isdigit() or (search_query.startswith('-') and search_query[1:].isdigit()):
                # Поиск по ID (также покрывает случаи с отрицательными числами, такими как ID чатов)
                try:
                    user_id = int(search_query)
                    logger.info(f"Ищем пользователя по ID: {user_id}")
                    
                    # Специальная обработка для групповых чатов (отрицательные ID)
                    if user_id < 0:
                        logger.info(f"Обнаружен ID группового чата: {user_id}")
                        await update.message.reply_text(
                            f"ℹ️ ID {user_id} принадлежит групповому чату, а не пользователю.\n"
                            "Для поиска пользователя введите положительный числовой ID или @username.",
                            reply_markup=ReplyKeyboardMarkup([
                                ["👥 Управление пользователями"],
                                ["🔄 Назад в админ-панель"]
                            ], resize_keyboard=True)
                        )
                        return
                    
                    user = await get_user(user_id)
                    logger.info(f"Результат поиска: {user}")
                    
                    if user:
                        role = user.get('role', 'user')
                        balance = user.get('balance', 0)
                        username = user.get('username', 'Нет имени')
                        registration_date = user.get('registration_date', 'Неизвестно')
                        
                        await update.message.reply_text(
                            f"👤 *Информация о пользователе*\n\n"
                            f"*ID:* `{user_id}`\n"
                            f"*Имя:* {username}\n"
                            f"*Роль:* {role}\n"
                            f"*Баланс:* {balance} LTC\n"
                            f"*Дата регистрации:* {registration_date}\n\n"
                            f"Для управления пользователем используйте админ-панель.",
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=ReplyKeyboardMarkup([
                                ["👥 Управление пользователями"],
                                ["🔄 Назад в админ-панель"]
                            ], resize_keyboard=True)
                        )
                    else:
                        logger.warning(f"Пользователь с ID {user_id} не найден")
                        await update.message.reply_text(
                            "❌ Пользователь с таким ID не найден.",
                            reply_markup=ReplyKeyboardMarkup([
                                ["👥 Управление пользователями"],
                                ["🔄 Назад в админ-панель"]
                            ], resize_keyboard=True)
                        )
                except Exception as e:
                    logger.error(f"Ошибка при поиске пользователя по ID: {e}")
                    await update.message.reply_text(
                        "❌ Произошла ошибка при поиске пользователя.",
                        reply_markup=ReplyKeyboardMarkup([
                            ["👥 Управление пользователями"],
                            ["🔄 Назад в админ-панель"]
                        ], resize_keyboard=True)
                    )
            else:
                await update.message.reply_text(
                    "❌ Некорректный формат. Введите ID (числовой) или @username пользователя.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
            
            # Сбрасываем состояние
            del context.user_data["admin_state"]
            
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при поиске пользователя. Попробуйте ещё раз.",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            # Сбрасываем состояние при ошибке
            del context.user_data["admin_state"]
            
    elif admin_state == "waiting_for_user_role_change":
        # Обработка изменения роли пользователя
        try:
            # Парсим входные данные
            parts = message_text.strip().split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: `ID роль`\n"
                    "Например: `123456789 operator`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
                
            user_id_str, role = parts
            
            try:
                user_id = int(user_id_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ ID пользователя должен быть числом.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Проверяем корректность роли
            if role not in ["user", "operator", "admin"]:
                await update.message.reply_text(
                    "❌ Недопустимая роль. Используйте: `user`, `operator` или `admin`.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Получаем пользователя
            user = await get_user(user_id)
            if not user:
                await update.message.reply_text(
                    f"⚠️ Пользователь с ID {user_id} не найден.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Обновляем роль пользователя
            user["role"] = role
            await save_user(user_id, user)
            
            # Если роль "admin", также добавим в список администраторов
            if role == "admin":
                add_admin(user_id)
            elif role != "admin" and is_admin(user_id):
                remove_admin(user_id)
            
            # Подтверждаем изменение
            username = user.get("username", f"user_{user_id}")
            await update.message.reply_text(
                f"✅ Роль пользователя @{username} (ID: {user_id}) изменена на: {role}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
            # Сбрасываем состояние
            del context.user_data["admin_state"]
            
        except Exception as e:
            logger.error(f"Ошибка изменения роли пользователя: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка при изменении роли пользователя: {e}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
    elif admin_state == "waiting_for_balance_change":
        # Обработка изменения баланса пользователя
        try:
            # Парсим входные данные
            parts = message_text.strip().split()
            if len(parts) != 2:
                await update.message.reply_text(
                    "❌ Неверный формат. Используйте: `ID сумма`\n"
                    "Например: `123456789 +500` или `123456789 -200`",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
                
            user_id_str, amount_str = parts
            
            try:
                user_id = int(user_id_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ ID пользователя должен быть числом.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            try:
                amount = float(amount_str)
            except ValueError:
                await update.message.reply_text(
                    "❌ Сумма должна быть числом.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Получаем пользователя
            user = await get_user(user_id)
            if not user:
                await update.message.reply_text(
                    f"⚠️ Пользователь с ID {user_id} не найден.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Обновляем баланс пользователя
            current_balance = user.get("balance", 0)
            new_balance = current_balance + amount
            
            # Проверяем, чтобы баланс не стал отрицательным
            if new_balance < 0:
                await update.message.reply_text(
                    f"⚠️ Невозможно установить отрицательный баланс. "
                    f"Текущий баланс: {current_balance}, запрошенное изменение: {amount}",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            user["balance"] = new_balance
            await save_user(user_id, user)
            
            # Подтверждаем изменение
            username = user.get("username", f"user_{user_id}")
            amount_text = f"+{amount}" if amount >= 0 else f"{amount}"
            await update.message.reply_text(
                f"✅ Баланс пользователя @{username} (ID: {user_id}) изменен: {amount_text}\n"
                f"Старый баланс: {current_balance}\n"
                f"Новый баланс: {new_balance}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
            # Сбрасываем состояние
            del context.user_data["admin_state"]
            
        except Exception as e:
            logger.error(f"Ошибка изменения баланса пользователя: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка при изменении баланса пользователя: {e}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
    elif admin_state == "waiting_for_user_block":
        # Обработка блокировки пользователя
        try:
            # Парсим входные данные
            try:
                user_id = int(message_text.strip())
            except ValueError:
                await update.message.reply_text(
                    "❌ ID пользователя должен быть числом.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Получаем пользователя
            user = await get_user(user_id)
            if not user:
                await update.message.reply_text(
                    f"⚠️ Пользователь с ID {user_id} не найден.",
                    reply_markup=ReplyKeyboardMarkup([
                        ["👥 Управление пользователями"],
                        ["🔄 Назад в админ-панель"]
                    ], resize_keyboard=True)
                )
                return
            
            # Устанавливаем статус блокировки
            user["is_blocked"] = True
            await save_user(user_id, user)
            
            # Подтверждаем изменение
            username = user.get("username", f"user_{user_id}")
            await update.message.reply_text(
                f"✅ Пользователь @{username} (ID: {user_id}) заблокирован.",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
            # Сбрасываем состояние
            del context.user_data["admin_state"]
            
        except Exception as e:
            logger.error(f"Ошибка блокировки пользователя: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка при блокировке пользователя: {e}",
                reply_markup=ReplyKeyboardMarkup([
                    ["👥 Управление пользователями"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
    elif admin_state == "waiting_for_referral_settings":
        # Обработка изменения настроек реферальной системы
        await update_referral_settings(update, context)
        
    elif admin_state == "waiting_rates":
        # Обработка ввода новых курсов
        try:
            # Парсинг введенных значений
            values = [float(x) for x in message_text.split()]
            if len(values) != 4:
                raise ValueError("Необходимо ввести 4 значения")
            
            ltc_usd_buy, ltc_usd_sell, usd_rub_buy, usd_rub_sell = values
            
            # Обновление курсов
            update_rates(ltc_usd_buy, ltc_usd_sell, usd_rub_buy, usd_rub_sell)
            
            # Показ обновленных курсов
            rates = get_current_rates()
            await update.message.reply_text(
                f"✅ *Курсы успешно обновлены!*\n\n"
                f"*Новые курсы обмена:*\n\n"
                f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                f"*Курсы USD/RUB:*\n"
                f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_keyboard()
            )
            
            # Отправка уведомления в чат об изменении курсов
            bot = context.bot
            chat_id = load_config().get("main_chat_id")
            if chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📢 *ИЗМЕНЕНИЕ КУРСОВ*\n\n"
                    f"🔄 Администратор обновил курсы обмена:\n\n"
                    f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                    f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                    f"*Курсы USD/RUB:*\n"
                    f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                    f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Сброс состояния
            del context.user_data["admin_state"]
            
        except (ValueError, IndexError) as e:
            await update.message.reply_text(
                f"❌ *Ошибка!*\n\n"
                f"Неверный формат ввода. Необходимо ввести 4 числа через пробел, например:\n"
                f"`70 68 90 88`\n\n"
                f"Попробуйте еще раз или нажмите на кнопку отмены.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_keyboard()
            )
    
    # Состояние выбора курса для изменения
    elif context.user_data.get("admin_state") == "select_rate_to_change":
        if message_text == "🔄 Назад в админ-панель":
            # Отмена операции и возврат в админ-панель
            await update.message.reply_text(
                "🔙 Возвращаемся в админ-панель",
                reply_markup=get_admin_keyboard()
            )
            del context.user_data["admin_state"]
            return
            
        # Определяем какой курс выбран для изменения
        rate_type = None
        
        if message_text == "💰 Покупка LTC (USD)" or message_text == "💰 Покупка LTC (USD)" or message_text == "🪙 Покупка LTC (USD)":
            rate_type = "ltc_usd_buy"
            rate_name = "Покупка LTC"
            rate_unit = "USD"
            current_value = get_current_rates()["ltc_usd_buy"]
        elif message_text == "💰 Продажа LTC (USD)" or message_text == "💰 Продажа LTC (USD)" or message_text == "🪙 Продажа LTC (USD)":
            rate_type = "ltc_usd_sell"
            rate_name = "Продажа LTC" 
            rate_unit = "USD"
            current_value = get_current_rates()["ltc_usd_sell"]
        elif message_text == "💵 Покупка USD (RUB)" or message_text == "💵 Покупка USD (RUB)" or message_text == "💱 Покупка USD (RUB)":
            rate_type = "usd_rub_buy"
            rate_name = "Покупка USD"
            rate_unit = "RUB"
            current_value = get_current_rates()["usd_rub_buy"]
        elif message_text == "💵 Продажа USD (RUB)" or message_text == "💵 Продажа USD (RUB)" or message_text == "💱 Продажа USD (RUB)":
            rate_type = "usd_rub_sell"
            rate_name = "Продажа USD"
            rate_unit = "RUB"
            current_value = get_current_rates()["usd_rub_sell"]
        else:
            # Неверный ввод
            await update.message.reply_text(
                "❌ Выберите один из предложенных вариантов или вернитесь в админ-панель",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 Покупка LTC (USD)", "💰 Продажа LTC (USD)"],
                    ["💵 Покупка USD (RUB)", "💵 Продажа USD (RUB)"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            return
            
        # Запрашиваем новое значение
        keyboard = ReplyKeyboardMarkup([
            [f"+1% ({(current_value * 1.01):.2f})", f"+5% ({(current_value * 1.05):.2f})"],
            [f"-1% ({(current_value * 0.99):.2f})", f"-5% ({(current_value * 0.95):.2f})"],
            ["📝 Ввести вручную", "🔙 Назад к выбору курса"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            f"💱 *Изменение курса: {rate_name}*\n\n"
            f"Текущее значение: {current_value} {rate_unit}\n\n"
            f"Выберите действие или введите новое значение:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Сохраняем данные о выбранном курсе
        context.user_data["admin_state"] = "change_rate_value"
        context.user_data["rate_data"] = {
            "type": rate_type,
            "name": rate_name,
            "unit": rate_unit,
            "current_value": current_value
        }
        
    # Состояние изменения значения выбранного курса
    elif context.user_data.get("admin_state") == "change_rate_value":
        rate_data = context.user_data.get("rate_data", {})
        
        if message_text == "🔄 Назад к выбору курса":
            # Возвращаемся к выбору курса
            rates = get_current_rates()
            await update.message.reply_text(
                f"💱 *Текущие курсы обмена:*\n\n"
                f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                f"*Курсы USD/RUB:*\n"
                f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
                f"Выберите, какой курс вы хотите изменить:",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 Покупка LTC (USD)", "💰 Продажа LTC (USD)"],
                    ["💵 Покупка USD (RUB)", "💵 Продажа USD (RUB)"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data["admin_state"] = "select_rate_to_change"
            if "rate_data" in context.user_data:
                del context.user_data["rate_data"]
            return
            
        elif message_text == "📝 Ввести вручную":
            # Запрашиваем ручной ввод
            await update.message.reply_text(
                f"📝 *Ручной ввод значения курса*\n\n"
                f"Текущее значение: {rate_data.get('current_value')} {rate_data.get('unit')}\n\n"
                f"Введите новое числовое значение (например, 70.5):",
                reply_markup=ReplyKeyboardMarkup([["🔄 Назад к выбору курса"]], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data["admin_state"] = "manual_rate_input"
            return
            
        # Обработка кнопок быстрого изменения
        new_value = None
        current_value = rate_data.get("current_value", 0)
        
        if message_text == f"+1% ({(current_value * 1.01):.2f})":
            new_value = current_value * 1.01
        elif message_text == f"+5% ({(current_value * 1.05):.2f})":
            new_value = current_value * 1.05
        elif message_text == f"-1% ({(current_value * 0.99):.2f})":
            new_value = current_value * 0.99
        elif message_text == f"-5% ({(current_value * 0.95):.2f})":
            new_value = current_value * 0.95
        else:
            # Пробуем парсить введенное число
            try:
                new_value = float(message_text)
            except ValueError:
                # Неверный ввод
                keyboard = ReplyKeyboardMarkup([
                    [f"+1% ({(current_value * 1.01):.2f})", f"+5% ({(current_value * 1.05):.2f})"],
                    [f"-1% ({(current_value * 0.99):.2f})", f"-5% ({(current_value * 0.95):.2f})"],
                    ["📝 Ввести вручную", "🔄 Назад к выбору курса"]
                ], resize_keyboard=True)
                
                await update.message.reply_text(
                    f"❌ *Ошибка ввода*\n\n"
                    f"Введите числовое значение или выберите один из предложенных вариантов.",
                    reply_markup=keyboard,
                    parse_mode=ParseMode.MARKDOWN
                )
                return
                
        # Применяем новое значение
        rates = get_current_rates()
        rate_type = rate_data.get("type")
        
        # Обновляем выбранный курс
        if rate_type == "ltc_usd_buy":
            update_rates(new_value, rates["ltc_usd_sell"], rates["usd_rub_buy"], rates["usd_rub_sell"])
        elif rate_type == "ltc_usd_sell":
            update_rates(rates["ltc_usd_buy"], new_value, rates["usd_rub_buy"], rates["usd_rub_sell"])
        elif rate_type == "usd_rub_buy":
            update_rates(rates["ltc_usd_buy"], rates["ltc_usd_sell"], new_value, rates["usd_rub_sell"])
        elif rate_type == "usd_rub_sell":
            update_rates(rates["ltc_usd_buy"], rates["ltc_usd_sell"], rates["usd_rub_buy"], new_value)
            
        # Показываем обновленные курсы
        rates = get_current_rates()
        await update.message.reply_text(
            f"✅ *Курс успешно обновлен!*\n\n"
            f"*Новые курсы обмена:*\n\n"
            f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
            f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
            f"*Курсы USD/RUB:*\n"
            f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
            f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
            f"Хотите изменить другой курс?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["💰 Покупка LTC (USD)", "💰 Продажа LTC (USD)"],
                ["💵 Покупка USD (RUB)", "💵 Продажа USD (RUB)"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True)
        )
        
        # Отправка уведомления в чат об изменении курсов
        bot = context.bot
        chat_id = load_config().get("main_chat_id")
        if chat_id:
            await bot.send_message(
                chat_id=chat_id,
                text=f"📢 *ИЗМЕНЕНИЕ КУРСОВ*\n\n"
                f"🔄 Администратор обновил курсы обмена:\n\n"
                f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                f"*Курсы USD/RUB:*\n"
                f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Обновляем состояние до выбора курса
        context.user_data["admin_state"] = "select_rate_to_change"
        if "rate_data" in context.user_data:
            del context.user_data["rate_data"]
            
    # Состояние ручного ввода значения курса
    elif context.user_data.get("admin_state") == "manual_rate_input":
        rate_data = context.user_data.get("rate_data", {})
        
        if message_text == "🔄 Назад к выбору курса":
            # Возвращаемся к выбору курса
            rates = get_current_rates()
            await update.message.reply_text(
                f"💱 *Текущие курсы обмена:*\n\n"
                f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                f"*Курсы USD/RUB:*\n"
                f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
                f"Выберите, какой курс вы хотите изменить:",
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 Покупка LTC (USD)", "💰 Продажа LTC (USD)"],
                    ["💵 Покупка USD (RUB)", "💵 Продажа USD (RUB)"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data["admin_state"] = "select_rate_to_change"
            if "rate_data" in context.user_data:
                del context.user_data["rate_data"]
            return
            
        # Пробуем парсить введенное число
        try:
            new_value = float(message_text)
            
            # Применяем новое значение
            rates = get_current_rates()
            rate_type = rate_data.get("type")
            
            # Обновляем выбранный курс
            if rate_type == "ltc_usd_buy":
                update_rates(new_value, rates["ltc_usd_sell"], rates["usd_rub_buy"], rates["usd_rub_sell"])
            elif rate_type == "ltc_usd_sell":
                update_rates(rates["ltc_usd_buy"], new_value, rates["usd_rub_buy"], rates["usd_rub_sell"])
            elif rate_type == "usd_rub_buy":
                update_rates(rates["ltc_usd_buy"], rates["ltc_usd_sell"], new_value, rates["usd_rub_sell"])
            elif rate_type == "usd_rub_sell":
                update_rates(rates["ltc_usd_buy"], rates["ltc_usd_sell"], rates["usd_rub_buy"], new_value)
                
            # Показываем обновленные курсы
            rates = get_current_rates()
            await update.message.reply_text(
                f"✅ *Курс успешно обновлен!*\n\n"
                f"*Новые курсы обмена:*\n\n"
                f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                f"*Курсы USD/RUB:*\n"
                f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB\n\n"
                f"Хотите изменить другой курс?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["💰 Покупка LTC (USD)", "💰 Продажа LTC (USD)"],
                    ["💵 Покупка USD (RUB)", "💵 Продажа USD (RUB)"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            
            # Отправка уведомления в чат об изменении курсов
            bot = context.bot
            chat_id = load_config().get("main_chat_id")
            if chat_id:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"📢 *ИЗМЕНЕНИЕ КУРСОВ*\n\n"
                    f"🔄 Администратор обновил курсы обмена:\n\n"
                    f"• *Покупка LTC*: 1 LTC = {rates['ltc_usd_buy']} USD = {rates['ltc_usd_buy'] * rates['usd_rub_buy']} RUB\n"
                    f"• *Продажа LTC*: 1 LTC = {rates['ltc_usd_sell']} USD = {rates['ltc_usd_sell'] * rates['usd_rub_sell']} RUB\n\n"
                    f"*Курсы USD/RUB:*\n"
                    f"• *Покупка USD*: 1 USD = {rates['usd_rub_buy']} RUB\n"
                    f"• *Продажа USD*: 1 USD = {rates['usd_rub_sell']} RUB",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Обновляем состояние до выбора курса
            context.user_data["admin_state"] = "select_rate_to_change"
            if "rate_data" in context.user_data:
                del context.user_data["rate_data"]
                
        except ValueError:
            # Неверный ввод
            await update.message.reply_text(
                f"❌ *Ошибка ввода*\n\n"
                f"Введите числовое значение для курса (например, 70.5):",
                reply_markup=ReplyKeyboardMarkup([["🔄 Назад к выбору курса"]], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Обработка кнопки Управление текстами
    elif message_text == "💬 Управление текстами" and is_admin:
        # Меню управления текстами различных сообщений
        await update.message.reply_text(
            "💬 *Управление текстами*\n\n"
            "Здесь вы можете изменить тексты различных сообщений. "
            "Поддерживаются специальные теги:\n"
            "• @USERNAME - имя пользователя\n"
            "• @USERID - ID пользователя\n"
            "• @BALANCE - баланс пользователя\n"
            "• @DATE - текущая дата\n\n"
            "Вы также можете использовать Markdown-разметку.\n\n"
            "Выберите, какой текст вы хотите изменить:",
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Приветствие", "🔄 Профиль"],
                ["💰 Покупка крипты", "💱 Продажа крипты"],
                ["📞 Тех. поддержка", "👥 Реферальная система"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "select_text_to_edit"
        return
    
    # Обработка выбора текста для редактирования
    elif context.user_data.get("admin_state") == "select_text_to_edit":
        if message_text == "🔄 Назад в админ-панель":
            # Отмена операции и возврат в админ-панель
            await update.message.reply_text(
                "🔄 Возвращаемся в админ-панель",
                reply_markup=get_admin_keyboard()
            )
            del context.user_data["admin_state"]
            return
        
        # Определяем какой текст выбран для редактирования
        text_type = None
        text_name = ""
        text_content = ""
        
        if message_text == "📝 Приветствие":
            text_type = "welcome_text"
            text_name = "Приветственное сообщение"
            # Заглушка, в реальном проекте получаем из базы или конфига
            text_content = (
                "👋 Добро пожаловать, @USERNAME!\n\n"
                "Я бот для обмена и покупки криптовалюты LTC.\n"
                "Ваш ID: @USERID\n\n"
                "Чтобы начать, выберите действие из меню."
            )
        elif message_text == "🔄 Профиль":
            text_type = "profile_text"
            text_name = "Информация о профиле"
            text_content = (
                "👤 *Профиль* @USERNAME\n\n"
                "ID: `@USERID`\n\n"
                "📊 *Статистика:*\n"
                "🟢 Всего успешных сделок: 0 шт.\n"
                "📈 Сделок на покупку: 0 шт.\n"
                "📉 Сделок на продажу: 0 шт.\n"
                "💰 Общая сумма сделок: 0.00 $\n\n"
                "📅 *Статистика за месяц:*\n"
                "🟢 Всего успешных сделок: 0 шт.\n"
                "📈 Сделок на покупку: 0 шт.\n"
                "📉 Сделок на продажу: 0 шт.\n"
                "💰 Общая сумма сделок: 0.00 $\n\n"
                "💵 Ваша скидка: 0 %"
            )
        elif message_text == "💰 Покупка крипты":
            text_type = "buy_crypto_text"
            text_name = "Информация о покупке криптовалюты"
            text_content = (
                "💰 *Покупка LTC*\n\n"
                "Курс обмена: 1 LTC = @LTC_USD_BUY USD = @LTC_RUB_BUY RUB\n\n"
                "Выберите сумму или введите свою:"
            )
        elif message_text == "💱 Продажа крипты":
            text_type = "sell_crypto_text"
            text_name = "Информация о продаже криптовалюты"
            text_content = (
                "💱 *Продажа LTC*\n\n"
                "Курс обмена: 1 LTC = @LTC_USD_SELL USD = @LTC_RUB_SELL RUB\n\n"
                "Выберите сумму или введите свою:"
            )
        elif message_text == "📞 Тех. поддержка":
            text_type = "support_text"
            text_name = "Информация о технической поддержке"
            text_content = (
                "📞 *Техническая поддержка*\n\n"
                "Если у вас возникли вопросы или проблемы, обратитесь к нашему оператору:\n"
                "👨‍💻 @OperatorUsername\n\n"
                "Время работы: 24/7"
            )
        elif message_text == "👥 Реферальная система":
            text_type = "referral_text"
            text_name = "Информация о реферальной системе"
            text_content = (
                "👥 *Реферальная система*\n\n"
                "Приглашайте друзей и получайте вознаграждение с каждой их сделки!\n\n"
                "Ваша реферальная ссылка:\n"
                "`https://t.me/YourBot?start=@USERID`\n\n"
                "Ваша текущая скидка: 0%\n"
                "Приглашено пользователей: 0\n\n"
                "Условия:\n"
                "• 1-10 рефералов: 10% от комиссии\n"
                "• 11-25 рефералов: 12.5% от комиссии\n"
                "• 26-50 рефералов: 15% от комиссии\n"
                "• 51-100 рефералов: 17.5% от комиссии\n"
                "• 101+ рефералов: 20% от комиссии"
            )
        else:
            # Неверный ввод
            await update.message.reply_text(
                "❌ Выберите один из предложенных вариантов или вернитесь в админ-панель",
                reply_markup=ReplyKeyboardMarkup([
                    ["📝 Приветствие", "🔄 Профиль"],
                    ["💰 Покупка крипты", "💱 Продажа крипты"],
                    ["📞 Тех. поддержка", "👥 Реферальная система"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            return
        
        # Запрашиваем новый текст
        await update.message.reply_text(
            f"📝 *Редактирование текста: {text_name}*\n\n"
            f"Текущий текст:\n"
            f"```\n{text_content}\n```\n\n"
            f"Доступные теги:\n"
            f"• @USERNAME - имя пользователя\n"
            f"• @USERID - ID пользователя\n"
            f"• @BALANCE - баланс пользователя\n"
            f"• @DATE - текущая дата\n"
            f"• @LTC_USD_BUY - курс покупки LTC в USD\n"
            f"• @LTC_USD_SELL - курс продажи LTC в USD\n"
            f"• @LTC_RUB_BUY - курс покупки LTC в RUB\n"
            f"• @LTC_RUB_SELL - курс продажи LTC в RUB\n\n"
            f"Введите новый текст или нажмите 'Отмена':",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([["🔄 Отмена"]], resize_keyboard=True)
        )
        
        # Сохраняем данные о выбранном тексте
        context.user_data["admin_state"] = "edit_text"
        context.user_data["text_data"] = {
            "type": text_type,
            "name": text_name,
            "content": text_content
        }
    
    # Обработка ввода нового текста
    elif context.user_data.get("admin_state") == "edit_text":
        text_data = context.user_data.get("text_data", {})
        
        if message_text == "🔄 Отмена":
            # Отмена редактирования и возврат к выбору текста
            await update.message.reply_text(
                "💬 *Управление текстами*\n\n"
                "Выберите, какой текст вы хотите изменить:",
                reply_markup=ReplyKeyboardMarkup([
                    ["📝 Приветствие", "🔄 Профиль"],
                    ["💰 Покупка крипты", "💱 Продажа крипты"],
                    ["📞 Тех. поддержка", "👥 Реферальная система"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data["admin_state"] = "select_text_to_edit"
            if "text_data" in context.user_data:
                del context.user_data["text_data"]
            return
        
        # Здесь должна быть логика сохранения текста в базу или конфиг
        # В этом примере просто показываем, что текст обновлен
        
        await update.message.reply_text(
            f"✅ *Текст успешно обновлен!*\n\n"
            f"*{text_data.get('name')}* был изменен.\n\n"
            f"Хотите изменить другой текст?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["📝 Приветствие", "🔄 Профиль"],
                ["💰 Покупка крипты", "💱 Продажа крипты"],
                ["📞 Тех. поддержка", "👥 Реферальная система"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True)
        )
        
        # Обновляем состояние до выбора текста
        context.user_data["admin_state"] = "select_text_to_edit"
        if "text_data" in context.user_data:
            del context.user_data["text_data"]
    
    # Обработка кнопки Управление кнопками
    elif message_text == "🔘 Управление кнопками" and is_admin:
        # Меню управления кнопками
        await update.message.reply_text(
            "🔘 *Управление кнопками*\n\n"
            "Здесь вы можете изменить количество и текст кнопок в различных меню бота.\n\n"
            "Выберите, какие кнопки вы хотите изменить:",
            reply_markup=ReplyKeyboardMarkup([
                ["🏠 Главное меню", "ℹ️ Информационное меню"],
                ["🛒 Меню покупки", "💸 Меню продажи"],
                ["🔄 Назад в админ-панель"]
            ], resize_keyboard=True),
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data["admin_state"] = "select_buttons_to_edit"
        return
    
    # Обработка выбора кнопок для редактирования
    elif context.user_data.get("admin_state") == "select_buttons_to_edit":
        if message_text == "🔄 Назад в админ-панель":
            # Отмена операции и возврат в админ-панель
            await update.message.reply_text(
                "🔄 Возвращаемся в админ-панель",
                reply_markup=get_admin_keyboard()
            )
            del context.user_data["admin_state"]
            return
        
        # Определяем какие кнопки выбраны для редактирования
        buttons_type = None
        buttons_name = ""
        buttons_list = []
        
        if message_text == "🏠 Главное меню":
            buttons_type = "main_menu"
            buttons_name = "Кнопки главного меню"
            buttons_list = [
                "💰 Купить крипту",
                "💱 Продать крипту",
                "👤 Профиль",
                "ℹ️ Информация",
                "📋 Активные заявки"
            ]
        elif message_text == "ℹ️ Информационное меню":
            buttons_type = "info_menu"
            buttons_name = "Кнопки информационного меню"
            buttons_list = [
                "📋 Правила",
                "📋 Наши Ресурсы",
                "👥 Реферальная система",
                "💰 Тарифы и комиссии"
            ]
        elif message_text == "🛒 Меню покупки":
            buttons_type = "buy_menu"
            buttons_name = "Кнопки меню покупки"
            buttons_list = [
                "0.1 LTC",
                "0.25 LTC",
                "0.5 LTC",
                "1 LTC",
                "Другая сумма"
            ]
        elif message_text == "💸 Меню продажи":
            buttons_type = "sell_menu"
            buttons_name = "Кнопки меню продажи"
            buttons_list = [
                "0.1 LTC",
                "0.25 LTC",
                "0.5 LTC",
                "1 LTC",
                "Другая сумма"
            ]
        else:
            # Неверный ввод
            await update.message.reply_text(
                "❌ Выберите один из предложенных вариантов или вернитесь в админ-панель",
                reply_markup=ReplyKeyboardMarkup([
                    ["🏠 Главное меню", "ℹ️ Информационное меню"],
                    ["🛒 Меню покупки", "💸 Меню продажи"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True)
            )
            return
        
        # Показываем текущие кнопки и предлагаем варианты изменения
        buttons_text = "\n".join([f"• {button}" for button in buttons_list])
        
        await update.message.reply_text(
            f"🔘 *Редактирование кнопок: {buttons_name}*\n\n"
            f"Текущие кнопки:\n{buttons_text}\n\n"
            f"Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["➕ Добавить кнопку", "✏️ Изменить кнопку"],
                ["❌ Удалить кнопку", "🔄 Отмена"]
            ], resize_keyboard=True)
        )
        
        # Сохраняем данные о выбранных кнопках
        context.user_data["admin_state"] = "edit_buttons_action"
        context.user_data["buttons_data"] = {
            "type": buttons_type,
            "name": buttons_name,
            "list": buttons_list
        }
    
    # Обработка выбора действия для редактирования кнопок
    elif context.user_data.get("admin_state") == "edit_buttons_action":
        buttons_data = context.user_data.get("buttons_data", {})
        
        if message_text == "🔄 Отмена":
            # Отмена редактирования и возврат к выбору кнопок
            await update.message.reply_text(
                "🔘 *Управление кнопками*\n\n"
                "Выберите, какие кнопки вы хотите изменить:",
                reply_markup=ReplyKeyboardMarkup([
                    ["🏠 Главное меню", "ℹ️ Информационное меню"],
                    ["🛒 Меню покупки", "💸 Меню продажи"],
                    ["🔄 Назад в админ-панель"]
                ], resize_keyboard=True),
                parse_mode=ParseMode.MARKDOWN
            )
            context.user_data["admin_state"] = "select_buttons_to_edit"
            if "buttons_data" in context.user_data:
                del context.user_data["buttons_data"]
            return
        
        if message_text == "➕ Добавить кнопку":
            # Запрос текста для новой кнопки
            await update.message.reply_text(
                f"➕ *Добавление новой кнопки*\n\n"
                f"Введите текст для новой кнопки:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([["🔄 Отмена"]], resize_keyboard=True)
            )
            context.user_data["admin_state"] = "add_button"
            context.user_data["buttons_action"] = "add"
            return
        
        elif message_text == "✏️ Изменить кнопку":
            # Формируем список кнопок для выбора
            buttons = []
            for button in buttons_data.get("list", []):
                buttons.append([button])
            buttons.append(["🔄 Отмена"])
            
            # Запрос выбора кнопки для изменения
            await update.message.reply_text(
                f"✏️ *Изменение кнопки*\n\n"
                f"Выберите кнопку, которую хотите изменить:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            )
            context.user_data["admin_state"] = "select_button_to_edit"
            context.user_data["buttons_action"] = "edit"
            return
        
        elif message_text == "❌ Удалить кнопку":
            # Формируем список кнопок для выбора
            buttons = []
            for button in buttons_data.get("list", []):
                buttons.append([button])
            buttons.append(["🔄 Отмена"])
            
            # Запрос выбора кнопки для удаления
            await update.message.reply_text(
                f"❌ *Удаление кнопки*\n\n"
                f"Выберите кнопку, которую хотите удалить:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True)
            )
            context.user_data["admin_state"] = "select_button_to_delete"
            context.user_data["buttons_action"] = "delete"
            return
        
        else:
            # Неверный ввод
            await update.message.reply_text(
                f"❌ Выберите одно из предложенных действий или нажмите 'Отмена'",
                reply_markup=ReplyKeyboardMarkup([
                    ["➕ Добавить кнопку", "✏️ Изменить кнопку"],
                    ["❌ Удалить кнопку", "🔄 Отмена"]
                ], resize_keyboard=True)
            )
            return
    
    # Обработка состояний редактирования и добавления кнопок
    elif admin_state == "select_button_to_edit":
        if message_text == "🔄 Отмена":
            # Возвращаемся назад в меню кнопок
            await update.message.reply_text(
                "🔄 *Действие отменено*\n\n"
                "Вы вернулись в меню управления кнопками.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["➕ Добавить кнопку", "✏️ Изменить кнопку"],
                    ["❌ Удалить кнопку", "🔄 Отмена"]
                ], resize_keyboard=True)
            )
            del context.user_data["admin_state"]
            del context.user_data["buttons_action"]
            return
        
        # Получаем данные о кнопках
        config = load_config()
        buttons_data = config.get("buttons", {"list": []})
        button_list = buttons_data.get("list", [])
        
        # Проверяем, существует ли выбранная кнопка
        if message_text in button_list:
            # Запоминаем выбранную кнопку
            context.user_data["selected_button"] = message_text
            
            # Запрашиваем новое название кнопки
            await update.message.reply_text(
                "✏️ *Изменение кнопки*\n\n"
                f"Вы выбрали кнопку: *{message_text}*\n\n"
                "Введите новое название для кнопки или используйте текущее:\n\n"
                "Текущее название: " + message_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["Оставить текущее название"],
                    ["🔄 Отмена"]
                ], resize_keyboard=True)
            )
            context.user_data["admin_state"] = "edit_button_name"
        else:
            # Кнопка не найдена
            await update.message.reply_text(
                "❌ *Ошибка*\n\n"
                f"Кнопка '{message_text}' не найдена в списке.\n"
                "Пожалуйста, выберите кнопку из списка или нажмите 'Отмена'.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_keyboard()
            )
    
    elif admin_state == "edit_button_name":
        if message_text == "🔄 Отмена":
            # Возвращаемся назад в меню кнопок
            await update.message.reply_text(
                "🔄 *Действие отменено*\n\n"
                "Вы вернулись в меню управления кнопками.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["➕ Добавить кнопку", "✏️ Изменить кнопку"],
                    ["❌ Удалить кнопку", "🔄 Отмена"]
                ], resize_keyboard=True)
            )
            # Очистка состояний
            for key in ["admin_state", "buttons_action", "selected_button"]:
                if key in context.user_data:
                    del context.user_data[key]
            return
        
        # Получаем выбранную кнопку
        selected_button = context.user_data.get("selected_button")
        if not selected_button:
            await update.message.reply_text(
                "❌ *Ошибка*\n\n"
                "Произошла ошибка при обработке запроса.\n"
                "Пожалуйста, попробуйте заново.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_keyboard()
            )
            # Очистка состояний
            for key in ["admin_state", "buttons_action", "selected_button"]:
                if key in context.user_data:
                    del context.user_data[key]
            return
        
        # Обработаем случай "Оставить текущее название"
        new_button_name = selected_button if message_text == "Оставить текущее название" else message_text
        
        # Запоминаем новое название
        context.user_data["new_button_name"] = new_button_name
        
        # Запрашиваем текст, который будет отображаться при нажатии
        await update.message.reply_text(
            "✏️ *Изменение кнопки*\n\n"
            f"Название кнопки: *{new_button_name}*\n\n"
            "Теперь введите текст, который будет отображаться при нажатии на кнопку.\n"
            "Вы можете использовать специальные теги @TAG для динамического содержимого.\n\n"
            "Например: \"Текущий курс: @LTC_USD_BUY USD\"",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=ReplyKeyboardMarkup([
                ["🔄 Отмена"]
            ], resize_keyboard=True)
        )
        context.user_data["admin_state"] = "edit_button_content"
    
    elif admin_state == "edit_button_content":
        if message_text == "🔄 Отмена":
            # Возвращаемся назад в меню кнопок
            await update.message.reply_text(
                "🔄 *Действие отменено*\n\n"
                "Вы вернулись в меню управления кнопками.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=ReplyKeyboardMarkup([
                    ["➕ Добавить кнопку", "✏️ Изменить кнопку"],
                    ["❌ Удалить кнопку", "🔄 Отмена"]
                ], resize_keyboard=True)
            )
            # Очистка состояний
            for key in ["admin_state", "buttons_action", "selected_button", "new_button_name"]:
                if key in context.user_data:
                    del context.user_data[key]
            return
        
        # Получаем данные кнопки
        selected_button = context.user_data.get("selected_button")
        new_button_name = context.user_data.get("new_button_name")
        
        if not selected_button or not new_button_name:
            await update.message.reply_text(
                "❌ *Ошибка*\n\n"
                "Произошла ошибка при обработке запроса.\n"
                "Пожалуйста, попробуйте заново.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=get_admin_keyboard()
            )
            # Очистка состояний
            for key in ["admin_state", "buttons_action", "selected_button", "new_button_name"]:
                if key in context.user_data:
                    del context.user_data[key]
            return
        
        # Сохраняем изменения кнопки
        config = load_config()
        buttons_data = config.get("buttons", {"list": [], "content": {}})
        button_list = buttons_data.get("list", [])
        button_content = buttons_data.get("content", {})
        
        # Обновляем название кнопки если оно изменилось
        if selected_button != new_button_name:
            # Копируем содержимое старой кнопки на новую
            if selected_button in button_content:
                button_content[new_button_name] = button_content[selected_button]
                # Удаляем старую кнопку
                del button_content[selected_button]
            
            # Обновляем список кнопок
            if selected_button in button_list:
                idx = button_list.index(selected_button)
                button_list[idx] = new_button_name
        
        # Обновляем текст кнопки
        button_content[new_button_name] = message_text
        
        # Сохраняем обновленные данные
        buttons_data["list"] = button_list
        buttons_data["content"] = button_content
        config["buttons"] = buttons_data
        save_config(config)
        
        # Подтверждаем успешное изменение
        await update.message.reply_text(
            "✅ *Кнопка успешно изменена!*\n\n"
            f"Название: *{new_button_name}*\n"
            f"Текст: {message_text}\n\n"
            "Изменения сохранены и вступили в силу.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=get_admin_keyboard()
        )
        
        # Очистка состояний
        for key in ["admin_state", "buttons_action", "selected_button", "new_button_name"]:
            if key in context.user_data:
                del context.user_data[key]
    
    # Другие состояния админа можно добавить здесь


def register_common_handlers(app: Application) -> None:
    """Register common handlers available to all users"""
    # Help command
    app.add_handler(CommandHandler("help", help_command))
    
    # Add callback handlers first (they don't conflict with commands)
    app.add_handler(CallbackQueryHandler(handle_custom_button, pattern="^custom_button_"))
    app.add_handler(CallbackQueryHandler(handle_custom_back, pattern="^custom_back_"))
    app.add_handler(CallbackQueryHandler(handle_main_menu_callback, pattern="^go_main_menu$"))
    
    # Обработчик для текстовых кнопок
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_text_buttons
    ))
    
    # Обработчик для управления валютами (с наивысшим приоритетом)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_admin_currency_message
    ), group=2)
    
    # Обработчики кнопок настройки в админ-панели
    app.add_handler(MessageHandler(
        filters.Regex("^📋 Настройка комиссий$") & filters.ChatType.PRIVATE,
        handle_commission_button
    ), group=3)
    
    app.add_handler(MessageHandler(
        filters.Regex("^🔗 Реферальная система$") & filters.ChatType.PRIVATE,
        handle_referral_system_button
    ), group=3)
    
    app.add_handler(MessageHandler(
        filters.Regex("^🔔 Уведомления$") & filters.ChatType.PRIVATE,
        handle_notification_settings_button
    ), group=3)
    
    app.add_handler(MessageHandler(
        filters.Regex("^🔄 Назад в админ-панель$") & filters.ChatType.PRIVATE, 
        handle_admin_panel
    ), group=3)
    
    # Обработчик для переключения настроек уведомлений
    app.add_handler(MessageHandler(
        filters.Regex("^(✅|❌) .*$") & filters.ChatType.PRIVATE,
        handle_notification_toggle
    ), group=3)
    
    # Обработчик для администраторских состояний (с более высоким приоритетом)
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
        handle_admin_message
    ), group=1)
    
    # Custom commands should be registered AFTER all other regular commands in the register_handlers function
    # This will be done in register_handlers after all other handlers are registered
