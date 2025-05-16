import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.config.config import (
    load_config, save_config, update_rates, get_current_rates, 
    get_referral_percentage, add_admin, remove_admin, is_admin,
    add_operator, remove_operator, is_operator, get_min_amount, set_min_amount
)
from bot.database import (
    get_user, save_user, get_users, get_users_by_role, 
    get_active_orders, get_in_progress_orders, get_completed_orders,
    add_custom_command, remove_custom_command, get_custom_command
)
from bot.utils.keyboards import admin_keyboard, back_button
from bot.utils.helpers import is_valid_user_id, check_admin

logger = logging.getLogger(__name__)

# Admin commands
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel with options"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if this is a callback query or direct command
    if update.callback_query:
        await update.callback_query.answer()
        method = update.callback_query.edit_message_text
    else:
        method = update.message.reply_text
    
    keyboard = admin_keyboard()
    
    await method(
        "🔐 *Панель администратора*\n\n"
        "Выберите действие из меню ниже:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_manage_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user management panel"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create keyboard with users by role
    keyboard = []
    
    # Add buttons for each role
    keyboard.append([
        InlineKeyboardButton("👥 Пользователи", callback_data="admin_list_users_user"),
        InlineKeyboardButton("🛠️ Операторы", callback_data="admin_list_users_operator")
    ])
    keyboard.append([
        InlineKeyboardButton("🔑 Администраторы", callback_data="admin_list_users_admin")
    ])
    keyboard.append([
        InlineKeyboardButton("➕ Назначить роль", callback_data="admin_assign_role")
    ])
    keyboard.append([back_button("admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "👥 *Управление пользователями*\n\nВыберите категорию пользователей или действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_list_users_by_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List users by role"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get role from callback data
    query_data = update.callback_query.data
    role = query_data.split('_')[-1]  # Extract role from callback_data
    
    # Get users by role
    users = await get_users_by_role(role)
    
    # Create keyboard for pagination or back button
    keyboard = []
    
    # Add back button
    keyboard.append([back_button("admin_manage_users")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create message text
    role_names = {
        "user": "Пользователи",
        "operator": "Операторы",
        "admin": "Администраторы"
    }
    
    text = f"👥 *{role_names.get(role, 'Пользователи')}*\n\n"
    
    if not users:
        text += "Список пуст."
    else:
        for i, user in enumerate(users, 1):
            username = user.get("username", "Нет имени")
            text += f"{i}. {username} (ID: `{user.get('user_id')}`)\n"
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_assign_role_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of assigning a role to a user"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create back button
    keyboard = [[back_button("admin_manage_users")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "👤 *Назначение роли пользователю*\n\n"
        "Отправьте ID пользователя, которому хотите назначить роль:\n"
        "Например: `123456789`",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_user_id"

async def admin_handle_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle user ID input for role assignment"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for user ID
    if context.user_data.get("admin_action") != "waiting_for_user_id":
        return
    
    # Get the user ID from the message
    input_text = update.message.text.strip()
    
    # Validate user ID
    if not is_valid_user_id(input_text):
        await update.message.reply_text(
            "❌ Некорректный ID пользователя. Пожалуйста, отправьте числовой ID."
        )
        return
    
    target_user_id = int(input_text)
    
    # Check if user exists in database
    user = await get_user(target_user_id)
    
    if not user:
        await update.message.reply_text(
            "❌ Пользователь не найден в базе данных. "
            "Пользователь должен начать диалог с ботом, чтобы быть зарегистрированным."
        )
        return
    
    # Save target user ID in context
    context.user_data["target_user_id"] = target_user_id
    context.user_data["admin_action"] = "waiting_for_role"
    
    # Create keyboard with role options
    keyboard = [
        [
            InlineKeyboardButton("👤 Пользователь", callback_data="admin_set_role_user"),
            InlineKeyboardButton("🛠️ Оператор", callback_data="admin_set_role_operator")
        ],
        [
            InlineKeyboardButton("🔑 Администратор", callback_data="admin_set_role_admin")
        ],
        [InlineKeyboardButton("❌ Блокировать", callback_data="admin_set_role_blocked")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    username = user.get("username", "Нет имени")
    current_role = user.get("role", "user")
    
    await update.message.reply_text(
        f"👤 *Изменение роли пользователя*\n\n"
        f"Пользователь: {username}\n"
        f"ID: `{target_user_id}`\n"
        f"Текущая роль: {current_role}\n\n"
        f"Выберите новую роль для пользователя:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_set_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set role for a user"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    # Get the target user ID from context
    target_user_id = context.user_data.get("target_user_id")
    
    if not target_user_id:
        await update.callback_query.answer("Ошибка: ID пользователя не найден.")
        return
    
    # Get role from callback data
    query_data = update.callback_query.data
    role = query_data.split('_')[-1]  # Extract role from callback_data
    
    # Get user data
    user = await get_user(target_user_id)
    
    if not user:
        await update.callback_query.answer("Пользователь не найден.")
        return
    
    # Update user role
    user["role"] = role
    await save_user(target_user_id, user)
    
    # Update admin list if necessary
    if role == "admin":
        add_admin(target_user_id)
    elif user.get("role") == "admin" and role != "admin":
        remove_admin(target_user_id)
    
    await update.callback_query.answer(f"Роль пользователя изменена на: {role}")
    
    # Clear conversation state
    if "admin_action" in context.user_data:
        del context.user_data["admin_action"]
    if "target_user_id" in context.user_data:
        del context.user_data["target_user_id"]
    
    # Show confirmation and return to admin panel
    role_names = {
        "user": "Пользователь",
        "operator": "Оператор",
        "admin": "Администратор",
        "blocked": "Заблокирован"
    }
    
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"✅ *Роль успешно изменена*\n\n"
        f"Пользователь: {user.get('username', 'Нет имени')}\n"
        f"ID: `{target_user_id}`\n"
        f"Новая роль: {role_names.get(role, role)}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_manage_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current rates and options to change them"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get current rates
    rates = get_current_rates()
    
    # Расчет обменных курсов в формате "РУБЛЬ К ДОЛЛАРУ" и "ДОЛЛАР К LTC"
    ltc_to_usd_buy = rates['ltc_usd_buy']  # Покупка LTC (сколько USD нужно отдать за 1 LTC)
    ltc_to_usd_sell = rates['ltc_usd_sell']  # Продажа LTC (сколько USD получим за 1 LTC)
    usd_to_rub_buy = rates['usd_rub_buy']  # Покупка USD (сколько RUB нужно отдать за 1 USD)
    usd_to_rub_sell = rates['usd_rub_sell']  # Продажа USD (сколько RUB получим за 1 USD)
    
    # Расчет перекрестных курсов для информирования
    ltc_to_rub_buy = ltc_to_usd_buy * usd_to_rub_buy  # Покупка LTC в рублях
    ltc_to_rub_sell = ltc_to_usd_sell * usd_to_rub_sell  # Продажа LTC в рублях
    
    # Create keyboard for rate management
    keyboard = [
        [InlineKeyboardButton("💱 Изменить курсы", callback_data="admin_change_rates")]
    ]
    keyboard.append([back_button("admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"💱 *Управление курсами валют*\n\n"
        f"*Текущие курсы:*\n\n"
        f"*Курсы LTC/USD:*\n"
        f"• Покупка LTC: 1 LTC = ${rates['ltc_usd_buy']:.2f}\n"
        f"• Продажа LTC: 1 LTC = ${rates['ltc_usd_sell']:.2f}\n\n"
        f"*Курсы USD/RUB:*\n"
        f"• Покупка USD: 1 USD = ₽{rates['usd_rub_buy']:.2f}\n"
        f"• Продажа USD: 1 USD = ₽{rates['usd_rub_sell']:.2f}\n\n"
        f"*Расчетные курсы LTC/RUB:*\n"
        f"• Покупка LTC: 1 LTC ≈ ₽{ltc_to_rub_buy:.2f}\n"
        f"• Продажа LTC: 1 LTC ≈ ₽{ltc_to_rub_sell:.2f}\n\n"
        f"Выберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_change_rates_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of changing rates"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get current rates
    rates = get_current_rates()
    
    # Расчет обменных курсов в формате "РУБЛЬ К ДОЛЛАРУ" и "ДОЛЛАР К LTC"
    ltc_to_usd_buy = rates['ltc_usd_buy']  # Покупка LTC (сколько USD нужно отдать за 1 LTC)
    ltc_to_usd_sell = rates['ltc_usd_sell']  # Продажа LTC (сколько USD получим за 1 LTC)
    usd_to_rub_buy = rates['usd_rub_buy']  # Покупка USD (сколько RUB нужно отдать за 1 USD)
    usd_to_rub_sell = rates['usd_rub_sell']  # Продажа USD (сколько RUB получим за 1 USD)
    
    # Create back button
    keyboard = [[back_button("admin_manage_rates")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"💱 *Изменение курсов валют*\n\n"
        f"*Текущие курсы:*\n"
        f"• Покупка LTC: 1 LTC = ${rates['ltc_usd_buy']:.2f}\n"
        f"• Продажа LTC: 1 LTC = ${rates['ltc_usd_sell']:.2f}\n"
        f"• Покупка USD: 1 USD = ₽{rates['usd_rub_buy']:.2f}\n"
        f"• Продажа USD: 1 USD = ₽{rates['usd_rub_sell']:.2f}\n\n"
        f"Отправьте новые значения в формате:\n"
        f"`ltc_buy ltc_sell usd_buy usd_sell`\n\n"
        f"*Текущие значения:* `{rates['ltc_usd_buy']} {rates['ltc_usd_sell']} {rates['usd_rub_buy']} {rates['usd_rub_sell']}`\n\n"
        f"Пример:\n"
        f"• Для изменения всех курсов: `70 68 90 88`\n"
        f"• Для изменения только первого параметра: `72 {rates['ltc_usd_sell']} {rates['usd_rub_buy']} {rates['usd_rub_sell']}`",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_rates"

async def admin_handle_rates_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle rates input from admin"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for rates
    if context.user_data.get("admin_action") != "waiting_for_rates":
        return
    
    # Get rates input
    input_text = update.message.text.strip()
    
    try:
        # Parse rates
        values = input_text.split()
        
        if len(values) != 4:
            await update.message.reply_text(
                "❌ Неверный формат. Необходимо указать 4 значения: покупка LTC, продажа LTC, покупка USD, продажа USD."
            )
            return
        
        ltc_usd_buy = float(values[0])
        ltc_usd_sell = float(values[1])
        usd_rub_buy = float(values[2])
        usd_rub_sell = float(values[3])
        
        # Validate rates
        if ltc_usd_buy <= 0 or ltc_usd_sell <= 0 or usd_rub_buy <= 0 or usd_rub_sell <= 0:
            await update.message.reply_text("❌ Все курсы должны быть положительными числами.")
            return
        
        # Update rates
        update_rates(ltc_usd_buy, ltc_usd_sell, usd_rub_buy, usd_rub_sell)
        
        # Clear conversation state
        if "admin_action" in context.user_data:
            del context.user_data["admin_action"]
        
        # Create keyboard for going back to rate management
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_rates")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ *Курсы валют успешно обновлены*\n\n"
            f"*Новые курсы:*\n"
            f"• Покупка LTC: ${ltc_usd_buy:.2f}\n"
            f"• Продажа LTC: ${ltc_usd_sell:.2f}\n"
            f"• Покупка USD: ₽{usd_rub_buy:.2f}\n"
            f"• Продажа USD: ₽{usd_rub_sell:.2f}",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Все значения должны быть числами. Попробуйте еще раз."
        )

async def admin_manage_balance(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show balance management panel"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create keyboard for balance operations
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить баланс", callback_data="admin_add_balance"),
            InlineKeyboardButton("➖ Снять баланс", callback_data="admin_subtract_balance")
        ]
    ]
    keyboard.append([back_button("admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "💰 *Управление балансом пользователей*\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_start_balance_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of adding or subtracting balance"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get operation type from callback data
    operation = "add" if "add_balance" in update.callback_query.data else "subtract"
    
    # Save operation in context
    context.user_data["balance_operation"] = operation
    
    # Create back button
    keyboard = [[back_button("admin_manage_balance")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    operation_name = "добавления" if operation == "add" else "снятия"
    
    await update.callback_query.edit_message_text(
        f"💰 *Операция {operation_name} баланса*\n\n"
        "Отправьте ID пользователя и сумму в формате:\n"
        "`ID сумма`\n\n"
        "Например: `123456789 500`",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_balance_data"

async def admin_handle_balance_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle balance operation input from admin"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for balance data
    if context.user_data.get("admin_action") != "waiting_for_balance_data":
        return
    
    # Get operation type from context
    operation = context.user_data.get("balance_operation", "add")
    
    # Get input
    input_text = update.message.text.strip()
    
    try:
        # Parse input
        parts = input_text.split()
        
        if len(parts) != 2:
            await update.message.reply_text(
                "❌ Неверный формат. Необходимо указать ID пользователя и сумму."
            )
            return
        
        target_user_id = int(parts[0])
        amount = float(parts[1])
        
        # Validate amount
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительным числом.")
            return
        
        # Get user data
        user = await get_user(target_user_id)
        
        if not user:
            await update.message.reply_text("❌ Пользователь не найден.")
            return
        
        # Update balance
        current_balance = user.get("balance", 0)
        
        if operation == "add":
            new_balance = current_balance + amount
            action_text = "добавлено"
        else:  # subtract
            if current_balance < amount:
                await update.message.reply_text(
                    f"❌ Недостаточно средств на балансе пользователя. Текущий баланс: {current_balance} руб."
                )
                return
            
            new_balance = current_balance - amount
            action_text = "снято"
        
        user["balance"] = new_balance
        await save_user(target_user_id, user)
        
        # Clear conversation state
        if "admin_action" in context.user_data:
            del context.user_data["admin_action"]
        if "balance_operation" in context.user_data:
            del context.user_data["balance_operation"]
        
        # Create keyboard for going back
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_manage_balance")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ *Баланс успешно изменён*\n\n"
            f"Пользователь: {user.get('username', 'Нет имени')}\n"
            f"ID: `{target_user_id}`\n"
            f"{action_text.capitalize()}: {amount} руб.\n"
            f"Новый баланс: {new_balance} руб.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Send notification to user
        try:
            from telegram import Bot
            bot = context.bot
            
            await bot.send_message(
                chat_id=target_user_id,
                text=f"💰 *Ваш баланс изменён*\n\n"
                     f"- {action_text.capitalize()}: {amount} руб.\n"
                     f"- Текущий баланс: {new_balance} руб.",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send balance notification: {e}")
        
    except ValueError:
        await update.message.reply_text(
            "❌ ID пользователя и сумма должны быть числами. Попробуйте еще раз."
        )

async def admin_order_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show order statistics"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get order statistics
    active_orders = await get_active_orders()
    in_progress_orders = await get_in_progress_orders()
    completed_orders = await get_completed_orders()
    
    # Calculate total spread
    total_spread = sum(order.get("spread", 0) or 0 for order in completed_orders)
    
    # Create keyboard for detailed views
    keyboard = [
        [
            InlineKeyboardButton("📊 Активные заявки", callback_data="admin_view_active_orders"),
            InlineKeyboardButton("🔄 В работе", callback_data="admin_view_in_progress_orders")
        ],
        [
            InlineKeyboardButton("✅ Завершённые", callback_data="admin_view_completed_orders")
        ]
    ]
    keyboard.append([back_button("admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📊 *Статистика заявок*\n\n"
        f"• Активных заявок: {len(active_orders)}\n"
        f"• Заявок в работе: {len(in_progress_orders)}\n"
        f"• Завершённых заявок: {len(completed_orders)}\n"
        f"• Общая прибыль (спред): {total_spread:.2f} руб.\n\n"
        "Выберите категорию для просмотра деталей:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View orders by status"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get order status from callback data
    query_data = update.callback_query.data
    status = query_data.split('_')[-1]  # Extract status from callback_data
    
    # Get orders by status
    if status == "active_orders":
        orders = await get_active_orders()
        title = "Активные заявки"
        back_callback = "admin_order_stats"
    elif status == "in_progress_orders":
        orders = await get_in_progress_orders()
        title = "Заявки в работе"
        back_callback = "admin_order_stats"
    elif status == "completed_orders":
        orders = await get_completed_orders()
        title = "Завершённые заявки"
        back_callback = "admin_order_stats"
    else:
        await update.callback_query.edit_message_text("❌ Ошибка: неизвестный статус заявок.")
        return
    
    # Create keyboard with back button
    keyboard = [[back_button(back_callback)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Create message text
    text = f"📋 *{title}*\n\n"
    
    if not orders:
        text += "Список пуст."
    else:
        # Show most recent 10 orders
        for order in orders[-10:]:
            order_number = order.get("order_number", "N/A")
            username = order.get("username", "Нет имени")
            order_type = "Покупка LTC" if order.get("order_type") == "buy" else "Продажа LTC"
            amount = order.get("amount", 0)
            spread = order.get("spread", "N/A")
            
            text += f"• *{order_number}*: {username}\n"
            text += f"  {order_type}, {amount} руб."
            
            if spread and status == "completed_orders":
                text += f", Спред: {spread} руб."
            
            text += "\n\n"
        
        if len(orders) > 10:
            text += f"И еще {len(orders) - 10} заявок..."
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_custom_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show custom commands management panel"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create keyboard for custom commands management
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить команду", callback_data="admin_add_command"),
            InlineKeyboardButton("❌ Удалить команду", callback_data="admin_remove_command")
        ]
    ]
    keyboard.append([back_button("admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "🔧 *Управление командами*\n\n"
        "Здесь вы можете добавлять и удалять пользовательские команды бота.\n\n"
        "Выберите действие:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_add_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of adding a custom command"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create back button
    keyboard = [[back_button("admin_custom_commands")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "➕ *Добавление команды*\n\n"
        "Отправьте название команды (без символа /):\n"
        "Например: `info`",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_command_name"

async def admin_handle_command_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle command name input from admin"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for command name
    if context.user_data.get("admin_action") != "waiting_for_command_name":
        return
    
    # Get command name
    command_name = update.message.text.strip()
    
    # Validate command name
    if not command_name or " " in command_name or "/" in command_name:
        await update.message.reply_text(
            "❌ Название команды не должно содержать пробелов или символа /."
        )
        return
    
    # Save command name in context
    context.user_data["command_name"] = command_name
    context.user_data["admin_action"] = "waiting_for_command_response"
    
    # Create back button
    keyboard = [[InlineKeyboardButton("🔙 Отмена", callback_data="admin_custom_commands")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📝 *Добавление команды* /{command_name}\n\n"
        "Отправьте текст ответа на эту команду:\n\n"
        "Вы можете использовать Markdown форматирование:\n"
        "*жирный* _курсив_ `код` [ссылка](URL)",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_handle_command_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle command response input from admin"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for command response
    if context.user_data.get("admin_action") != "waiting_for_command_response":
        return
    
    # Get command name and response
    command_name = context.user_data.get("command_name")
    response = update.message.text
    
    if not command_name or not response:
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте еще раз.")
        return
    
    # Ask for buttons
    context.user_data["command_response"] = response
    context.user_data["admin_action"] = "waiting_for_command_buttons"
    
    # Create buttons for yes/no
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data="admin_add_command_buttons"),
            InlineKeyboardButton("❌ Нет", callback_data="admin_finish_command")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📝 *Добавление команды* /{command_name}\n\n"
        "Хотите добавить к команде кнопки?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_add_command_buttons_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of adding buttons to a command"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get command name
    command_name = context.user_data.get("command_name")
    
    if not command_name:
        await update.callback_query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")
        return
    
    # Initialize buttons list
    if "command_buttons" not in context.user_data:
        context.user_data["command_buttons"] = []
    
    # Create back button
    keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="admin_finish_command")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        f"🔘 *Добавление кнопок к команде* /{command_name}\n\n"
        "Отправьте текст для кнопки:\n\n"
        "Например: `Как создать заявку`\n\n"
        "После добавления всех кнопок нажмите 'Завершить'.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_button_text"

async def admin_handle_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button text input from admin"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for button text
    if context.user_data.get("admin_action") != "waiting_for_button_text":
        return
    
    # Get button text
    button_text = update.message.text.strip()
    
    if not button_text:
        await update.message.reply_text("❌ Текст кнопки не может быть пустым.")
        return
    
    # Add button to list
    if "command_buttons" not in context.user_data:
        context.user_data["command_buttons"] = []
    
    context.user_data["command_buttons"].append(button_text)
    
    # Get command name
    command_name = context.user_data.get("command_name")
    buttons = context.user_data.get("command_buttons", [])
    
    # Create keyboard to add more buttons or finish
    keyboard = [[InlineKeyboardButton("✅ Завершить", callback_data="admin_finish_command")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    button_list = "\n".join([f"• {btn}" for btn in buttons])
    
    await update.message.reply_text(
        f"🔘 *Добавление кнопок к команде* /{command_name}\n\n"
        f"Добавленные кнопки:\n{button_list}\n\n"
        "Отправьте текст для следующей кнопки или нажмите 'Завершить'.",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_finish_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Finish adding a custom command"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Get command data
    command_name = context.user_data.get("command_name")
    response = context.user_data.get("command_response")
    buttons = context.user_data.get("command_buttons", [])
    
    if not command_name or not response:
        await update.callback_query.edit_message_text("❌ Произошла ошибка. Попробуйте еще раз.")
        return
    
    # Add custom command
    await add_custom_command(command_name, response, buttons)
    
    # Clear conversation state
    for key in ["admin_action", "command_name", "command_response", "command_buttons"]:
        if key in context.user_data:
            del context.user_data[key]
    
    # Create keyboard to go back
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_custom_commands")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    button_text = ""
    if buttons:
        button_list = "\n".join([f"• {btn}" for btn in buttons])
        button_text = f"\n\nКнопки:\n{button_list}"
    
    await update.callback_query.edit_message_text(
        f"✅ *Команда успешно добавлена*\n\n"
        f"Команда: /{command_name}\n"
        f"Ответ: {response}{button_text}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_remove_command_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of removing a custom command"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Create back button
    keyboard = [[back_button("admin_custom_commands")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "❌ *Удаление команды*\n\n"
        "Отправьте название команды для удаления (без символа /):\n"
        "Например: `info`",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set conversation state
    context.user_data["admin_action"] = "waiting_for_command_to_remove"

async def admin_handle_command_to_remove(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle command name input for removal"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.message.reply_text("У вас нет прав администратора.")
        return
    
    # Check if we're waiting for command to remove
    if context.user_data.get("admin_action") != "waiting_for_command_to_remove":
        return
    
    # Get command name
    command_name = update.message.text.strip()
    
    # Remove command
    command = await get_custom_command(command_name)
    
    if not command:
        # Create keyboard to go back
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_custom_commands")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"❌ Команда /{command_name} не найдена.",
            reply_markup=reply_markup
        )
        return
    
    # Remove the command
    success = await remove_custom_command(command_name)
    
    # Clear conversation state
    if "admin_action" in context.user_data:
        del context.user_data["admin_action"]
    
    # Create keyboard to go back
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="admin_custom_commands")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if success:
        await update.message.reply_text(
            f"✅ Команда /{command_name} успешно удалена.",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"❌ Не удалось удалить команду /{command_name}.",
            reply_markup=reply_markup
        )

# Обработчики управления операторами
async def admin_manage_operators(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать панель управления операторами"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Получаем список операторов из конфига
    config = load_config()
    operators = config.get("operator_ids", [])
    
    # Формируем список операторов с именами пользователей
    operator_list = ""
    if operators:
        for op_id in operators:
            user = await get_user(op_id)
            username = user.get("username", "Неизвестно") if user else "Неизвестно"
            operator_list += f"• ID: {op_id}, @{username}\n"
    else:
        operator_list = "Операторы не назначены"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить оператора", callback_data="admin_add_operator"),
            InlineKeyboardButton("➖ Удалить оператора", callback_data="admin_remove_operator")
        ],
        back_button("admin_panel")
    ]
    
    await update.callback_query.edit_message_text(
        f"👮‍♂️ *Управление операторами*\n\n"
        f"Текущие операторы:\n{operator_list}\n\n"
        f"Выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_add_operator_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начать процесс добавления оператора"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Запрашиваем ID пользователя для назначения
    context.user_data["admin_action"] = "add_operator"
    
    keyboard = [back_button("admin_manage_operators")]
    
    await update.callback_query.edit_message_text(
        "👮‍♂️ *Добавление оператора*\n\n"
        "Введите ID пользователя, которого хотите назначить оператором:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_remove_operator_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начать процесс удаления оператора"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Получаем список операторов из конфига
    config = load_config()
    operators = config.get("operator_ids", [])
    
    if not operators:
        await update.callback_query.edit_message_text(
            "❌ *Ошибка*\n\n"
            "В системе нет назначенных операторов.",
            reply_markup=InlineKeyboardMarkup([back_button("admin_manage_operators")]),
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Создаем клавиатуру с кнопками для удаления операторов
    keyboard = []
    for op_id in operators:
        user = await get_user(op_id)
        username = user.get("username", "Неизвестно") if user else f"ID: {op_id}"
        keyboard.append([InlineKeyboardButton(
            f"❌ {username}", callback_data=f"admin_delete_operator_{op_id}"
        )])
    
    keyboard.append(back_button("admin_manage_operators"))
    
    await update.callback_query.edit_message_text(
        "👮‍♂️ *Удаление оператора*\n\n"
        "Выберите оператора для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_delete_operator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Удалить оператора по callback_data"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Получаем ID оператора из callback_data
    operator_id = int(update.callback_query.data.split("_")[-1])
    
    # Удаляем оператора
    remove_operator(operator_id)
    
    await update.callback_query.edit_message_text(
        f"✅ *Успех*\n\n"
        f"Оператор (ID: {operator_id}) был удален.",
        reply_markup=InlineKeyboardMarkup([back_button("admin_manage_operators")]),
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчики минимальной суммы сделки
async def admin_min_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать и изменить минимальную сумму сделки"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Получаем текущую минимальную сумму
    min_amount = get_min_amount()
    
    keyboard = [
        [InlineKeyboardButton("✏️ Изменить сумму", callback_data="admin_change_min_amount")],
        back_button("admin_panel")
    ]
    
    await update.callback_query.edit_message_text(
        f"💵 *Минимальная сумма сделки*\n\n"
        f"Текущая минимальная сумма: *{min_amount:.2f}* PMR рублей\n\n"
        f"Эта сумма используется как минимальный порог для создания заявок пользователями.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_change_min_amount_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начать процесс изменения минимальной суммы"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Устанавливаем действие в контексте
    context.user_data["admin_action"] = "change_min_amount"
    
    keyboard = [back_button("admin_min_amount")]
    
    await update.callback_query.edit_message_text(
        "💵 *Изменение минимальной суммы*\n\n"
        "Введите новую минимальную сумму в PMR рублях:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

# Обработчики управления текстами
async def admin_manage_texts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать панель управления текстами и кнопками"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    # Получаем список доступных текстов
    commands = await get_commands()
    
    # Формируем список команд
    command_list = ""
    if commands:
        for cmd in commands:
            command_list += f"• /{cmd['command']}\n"
    else:
        command_list = "Нет настраиваемых текстов"
    
    keyboard = [
        [
            InlineKeyboardButton("➕ Добавить текст", callback_data="admin_add_command"),
            InlineKeyboardButton("➖ Удалить текст", callback_data="admin_remove_command")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать текст", callback_data="admin_edit_command")
        ],
        back_button("admin_panel")
    ]
    
    await update.callback_query.edit_message_text(
        f"📝 *Управление текстами*\n\n"
        f"Настраиваемые тексты и команды:\n{command_list}\n\n"
        f"Используйте эти функции для настройки ответов бота на команды и кнопки.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_back_to_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to admin panel"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not await check_admin(user_id):
        await update.callback_query.answer("У вас нет прав администратора.")
        return
    
    await update.callback_query.answer()
    
    keyboard = admin_keyboard()
    
    await update.callback_query.edit_message_text(
        "🔐 *Панель администратора*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def admin_handle_min_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработать ввод новой минимальной суммы"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        return
    
    # Проверяем, что ждем ввод минимальной суммы
    if context.user_data.get("admin_action") != "change_min_amount":
        return
    
    # Получаем новую минимальную сумму
    try:
        amount = float(update.message.text.strip())
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат суммы. Введите положительное число.",
            reply_markup=InlineKeyboardMarkup([back_button("admin_min_amount")])
        )
        return
    
    # Устанавливаем новую минимальную сумму
    set_min_amount(amount)
    
    # Очищаем состояние разговора
    if "admin_action" in context.user_data:
        del context.user_data["admin_action"]
    
    await update.message.reply_text(
        f"✅ Минимальная сумма сделки установлена: {amount:.2f} PMR рублей.",
        reply_markup=InlineKeyboardMarkup([back_button("admin_min_amount")])
    )

async def admin_handle_operator_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработать ID пользователя для назначения оператором"""
    user_id = update.effective_user.id
    
    # Проверка на права администратора
    if not await check_admin(user_id):
        return
    
    # Проверяем, что ждем ID оператора
    if context.user_data.get("admin_action") != "add_operator":
        return
    
    # Получаем ID оператора
    try:
        operator_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат ID. Введите число.",
            reply_markup=InlineKeyboardMarkup([back_button("admin_manage_operators")])
        )
        return
    
    # Проверяем существование пользователя
    user = await get_user(operator_id)
    if not user:
        await update.message.reply_text(
            f"❌ Пользователь с ID {operator_id} не найден в системе.",
            reply_markup=InlineKeyboardMarkup([back_button("admin_manage_operators")])
        )
        return
    
    # Добавляем пользователя в операторы
    add_operator(operator_id)
    
    # Очищаем состояние разговора
    if "admin_action" in context.user_data:
        del context.user_data["admin_action"]
    
    await update.message.reply_text(
        f"✅ Пользователь {operator_id} (@{user.get('username', 'Неизвестно')}) добавлен в список операторов.",
        reply_markup=InlineKeyboardMarkup([back_button("admin_manage_operators")])
    )

def register_admin_handlers(app: Application) -> None:
    """Register all admin handlers"""
    # Admin panel command
    app.add_handler(CommandHandler("admin", admin_panel))
    
    # Admin panel navigation
    app.add_handler(CallbackQueryHandler(admin_manage_users, pattern="^admin_manage_users$"))
    app.add_handler(CallbackQueryHandler(admin_list_users_by_role, pattern="^admin_list_users_"))
    app.add_handler(CallbackQueryHandler(admin_assign_role_start, pattern="^admin_assign_role$"))
    app.add_handler(CallbackQueryHandler(admin_set_user_role, pattern="^admin_set_role_"))
    
    # Rates management
    app.add_handler(CallbackQueryHandler(admin_manage_rates, pattern="^admin_manage_rates$"))
    app.add_handler(CallbackQueryHandler(admin_change_rates_start, pattern="^admin_change_rates$"))
    
    # Balance management
    app.add_handler(CallbackQueryHandler(admin_manage_balance, pattern="^admin_manage_balance$"))
    app.add_handler(CallbackQueryHandler(admin_start_balance_operation, pattern="^admin_(add|subtract)_balance$"))
    
    # Order statistics
    app.add_handler(CallbackQueryHandler(admin_order_stats, pattern="^admin_order_stats$"))
    app.add_handler(CallbackQueryHandler(admin_view_orders, pattern="^admin_view_.*_orders$"))
    
    # Custom commands
    app.add_handler(CallbackQueryHandler(admin_custom_commands, pattern="^admin_custom_commands$"))
    app.add_handler(CallbackQueryHandler(admin_add_command_start, pattern="^admin_add_command$"))
    app.add_handler(CallbackQueryHandler(admin_add_command_buttons_start, pattern="^admin_add_command_buttons$"))
    app.add_handler(CallbackQueryHandler(admin_finish_command, pattern="^admin_finish_command$"))
    app.add_handler(CallbackQueryHandler(admin_remove_command_start, pattern="^admin_remove_command$"))
    
    # Manage operators
    app.add_handler(CallbackQueryHandler(admin_manage_operators, pattern="^admin_manage_operators$"))
    app.add_handler(CallbackQueryHandler(admin_add_operator_start, pattern="^admin_add_operator$"))
    app.add_handler(CallbackQueryHandler(admin_remove_operator_start, pattern="^admin_remove_operator$"))
    app.add_handler(CallbackQueryHandler(admin_delete_operator, pattern="^admin_delete_operator_"))
    
    # Minimum amount settings
    app.add_handler(CallbackQueryHandler(admin_min_amount, pattern="^admin_min_amount$"))
    app.add_handler(CallbackQueryHandler(admin_change_min_amount_start, pattern="^admin_change_min_amount$"))
    
    # Manage texts
    app.add_handler(CallbackQueryHandler(admin_manage_texts, pattern="^admin_manage_texts$"))
    
    # Back to panel
    app.add_handler(CallbackQueryHandler(admin_back_to_panel, pattern="^admin_panel$"))
    
    # Message handlers for conversations
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_user_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_rates_input))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_balance_operation))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_command_name))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_min_amount))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_operator_id))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_command_response))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_button_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, admin_handle_command_to_remove))
