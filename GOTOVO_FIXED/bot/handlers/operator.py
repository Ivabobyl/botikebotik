import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.config.config import (
    get_current_rates
)
from bot.database import (
    get_user, save_user, get_active_orders, get_in_progress_orders,
    get_order, get_order_by_number, update_order
)
from bot.utils.keyboards import operator_keyboard, back_button
from bot.utils.helpers import check_operator, calculate_spread, send_order_notification

logger = logging.getLogger(__name__)

# Operator commands
async def operator_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show operator panel with options"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.message.reply_text("У вас нет прав оператора.")
        return
    
    keyboard = operator_keyboard()
    await update.message.reply_text(
        "🛠️ *Панель оператора*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def operator_view_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View active orders that need processing"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    await update.callback_query.answer()
    
    # Get active orders
    active_orders = await get_active_orders()
    
    # Create keyboard with order buttons
    keyboard = []
    
    if active_orders:
        for order in active_orders[:10]:  # Limit to 10 orders per page
            order_number = order.get("order_number", "N/A")
            order_type = "Покупка" if order.get("order_type") == "buy" else "Продажа"
            amount = order.get("amount", 0)
            
            btn_text = f"{order_number}: {order_type} {amount}₽"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"operator_order_{order['id']}")])
    
    keyboard.append([back_button("operator_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "📋 *Активные заявки*\n\n"
    
    if not active_orders:
        text += "В данный момент нет активных заявок."
    else:
        text += f"Найдено {len(active_orders)} активных заявок.\nВыберите заявку для обработки:"
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def operator_view_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View orders assigned to the operator"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    await update.callback_query.answer()
    
    # Get in-progress orders
    in_progress_orders = await get_in_progress_orders()
    
    # Filter orders assigned to this operator
    my_orders = [order for order in in_progress_orders if order.get("operator_id") == user_id]
    
    # Create keyboard with order buttons
    keyboard = []
    
    if my_orders:
        for order in my_orders[:10]:  # Limit to 10 orders per page
            order_number = order.get("order_number", "N/A")
            order_type = "Покупка" if order.get("order_type") == "buy" else "Продажа"
            amount = order.get("amount", 0)
            
            btn_text = f"{order_number}: {order_type} {amount}₽"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"operator_order_{order['id']}")])
    
    keyboard.append([back_button("operator_panel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "🔄 *Мои заявки в работе*\n\n"
    
    if not my_orders:
        text += "У вас нет заявок в работе."
    else:
        text += f"У вас {len(my_orders)} заявок в работе.\nВыберите заявку для просмотра:"
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def operator_view_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View order details and actions"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    await update.callback_query.answer()
    
    # Get order ID from callback data
    query_data = update.callback_query.data
    order_id = int(query_data.split('_')[-1])
    
    # Get order details
    order = await get_order(order_id)
    
    if not order:
        await update.callback_query.edit_message_text("❌ Заявка не найдена.")
        return
    
    # Create keyboard with actions
    keyboard = []
    
    order_status = order.get("status", "active")
    
    if order_status == "active":
        # Order is active, show "Take Order" button
        keyboard.append([InlineKeyboardButton("🔄 Работаю", callback_data=f"operator_take_order_{order_id}")])
        back_callback = "operator_view_active_orders"
    elif order_status == "in_progress":
        # Order is in progress, show "Complete Order" button if assigned to this operator
        if order.get("operator_id") == user_id:
            keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data=f"operator_complete_order_{order_id}")])
            back_callback = "operator_view_my_orders"
        else:
            # Order is assigned to another operator
            back_callback = "operator_view_active_orders"
    else:
        # Order is completed, show info only
        back_callback = "operator_panel"
    
    keyboard.append([back_button(back_callback)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Format order details
    order_number = order.get("order_number", "N/A")
    username = order.get("username", "Нет имени")
    user_id_str = order.get("user_id", "N/A")
    order_type = "Покупка LTC" if order.get("order_type") == "buy" else "Продажа LTC"
    amount = order.get("amount", 0)
    created_at = order.get("created_at", "N/A").split("T")[0]  # Just the date part
    
    # Format status-specific information
    status_text = ""
    if order_status == "in_progress":
        operator_username = order.get("operator_username", "N/A")
        status_text = f"🔄 В работе у оператора: {operator_username}"
    elif order_status == "completed":
        operator_username = order.get("operator_username", "N/A")
        completed_at = order.get("completed_at", "N/A").split("T")[0]
        spread = order.get("spread", 0)
        status_text = (f"✅ Завершена {completed_at}\n"
                       f"Оператор: {operator_username}\n"
                       f"Спред: {spread} руб.")
    
    # Format message text
    text = (f"📝 *Заявка {order_number}*\n\n"
            f"👤 Пользователь: {username}\n"
            f"🆔 ID: `{user_id_str}`\n"
            f"💱 Тип: {order_type}\n"
            f"💰 Сумма: {amount} руб.\n"
            f"📅 Создана: {created_at}\n\n"
            f"{status_text}")
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def operator_take_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Take an order and start working on it"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    # Get order ID from callback data
    query_data = update.callback_query.data
    order_id = int(query_data.split('_')[-1])
    
    # Get order details
    order = await get_order(order_id)
    
    if not order:
        await update.callback_query.answer("❌ Заявка не найдена.")
        return
    
    # Check if order is still active
    if order.get("status") != "active":
        await update.callback_query.answer("❌ Заявка уже взята в работу или завершена.")
        return
    
    # Update order with operator info
    username = update.effective_user.username
    if not username:
        username = f"ID:{user_id}"
    
    updates = {
        "status": "in_progress",
        "operator_id": user_id,
        "operator_username": username
    }
    
    updated_order = await update_order(order_id, updates)
    
    if not updated_order:
        await update.callback_query.answer("❌ Не удалось обновить заявку.")
        return
    
    await update.callback_query.answer("✅ Вы взяли заявку в работу.")
    
    # Notify user
    client_id = order.get("user_id")
    order_number = order.get("order_number")
    
    # Notification for the client
    if client_id:
        try:
            notification_text = (
                f"🔄 *Заявка {order_number} в работе*\n\n"
                f"Ваша заявка взята в работу оператором: {username}\n"
                f"Ожидайте дальнейших инструкций."
            )
            
            await context.bot.send_message(
                chat_id=client_id,
                text=notification_text,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Failed to send client notification: {e}")
    
    # Notification for the group chat
    try:
        from bot import MAIN_CHAT_ID
        
        group_notification = (
            f"🔄 *Заявка {order_number} взята в работу*\n\n"
            f"• Клиент: {order.get('username')} (ID: `{client_id}`)\n"
            f"• Оператор: {username}\n"
            f"• Тип: {'Покупка' if order.get('order_type') == 'buy' else 'Продажа'} LTC\n"
            f"• Сумма: {order.get('amount')} рублей"
        )
        
        await context.bot.send_message(
            chat_id=MAIN_CHAT_ID,
            text=group_notification,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception as e:
        logger.error(f"Failed to send group notification: {e}")
    
    # Redirect to order details
    await operator_view_order(update, context)

async def operator_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Complete an order"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    # Get order ID from callback data
    query_data = update.callback_query.data
    order_id = int(query_data.split('_')[-1])
    
    # Get order details
    order = await get_order(order_id)
    
    if not order:
        await update.callback_query.answer("❌ Заявка не найдена.")
        return
    
    # Check if order is in progress and assigned to this operator
    if order.get("status") != "in_progress":
        await update.callback_query.answer("❌ Заявка не находится в работе.")
        return
    
    if order.get("operator_id") != user_id:
        await update.callback_query.answer("❌ Эта заявка назначена другому оператору.")
        return
    
    # Calculate spread
    amount = order.get("amount", 0)
    order_type = order.get("order_type", "buy")
    spread = await calculate_spread(amount, order_type)
    
    # Update order to completed status
    import datetime
    now = datetime.datetime.now().isoformat()
    
    updates = {
        "status": "completed",
        "completed_at": now,
        "spread": spread
    }
    
    updated_order = await update_order(order_id, updates)
    
    if not updated_order:
        await update.callback_query.answer("❌ Не удалось завершить заявку.")
        return
    
    await update.callback_query.answer("✅ Заявка успешно завершена.")
    
    # Create keyboard to return to operator panel
    keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="operator_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Format completed order message
    order_number = updated_order.get("order_number", "N/A")
    username = updated_order.get("username", "Нет имени")
    user_id_str = updated_order.get("user_id", "N/A")
    operator_username = updated_order.get("operator_username", "N/A")
    order_type_str = "Покупка LTC" if order_type == "buy" else "Продажа LTC"
    
    text = (
        f"✅ *Заявка {order_number} завершена!*\n\n"
        f"• Пользователь: {username} | ID: `{user_id_str}`\n"
        f"• Оператор: {operator_username}\n"
        f"• Тип сделки: {order_type_str}\n"
        f"• Сумма: {amount} рублей\n"
        f"• Спред: +{spread} рублей"
    )
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Send notification to user and process referral bonus if applicable
    await send_order_notification(context.bot, updated_order)

async def operator_view_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View current exchange rates"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    await update.callback_query.answer()
    
    # Get current rates
    rates = get_current_rates()
    
    # Create keyboard with back button
    keyboard = [[back_button("operator_panel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Calculate LTC price in rubles
    ltc_buy_rub = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
    ltc_sell_rub = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
    
    await update.callback_query.edit_message_text(
        f"💱 *Текущие курсы обмена*\n\n"
        f"*Litecoin (LTC):*\n"
        f"• Покупка: ${rates['ltc_usd_buy']:.2f} (₽{ltc_buy_rub:.2f})\n"
        f"• Продажа: ${rates['ltc_usd_sell']:.2f} (₽{ltc_sell_rub:.2f})\n\n"
        f"*Доллар США (USD):*\n"
        f"• Покупка: ₽{rates['usd_rub_buy']:.2f}\n"
        f"• Продажа: ₽{rates['usd_rub_sell']:.2f}",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def operator_back_to_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Return to operator panel"""
    user_id = update.effective_user.id
    
    # Check if user is operator or admin
    if not await check_operator(user_id):
        await update.callback_query.answer("У вас нет прав оператора.")
        return
    
    await update.callback_query.answer()
    
    keyboard = operator_keyboard()
    
    await update.callback_query.edit_message_text(
        "🛠️ *Панель оператора*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

def register_operator_handlers(app: Application) -> None:
    """Register all operator handlers"""
    # Operator panel command
    app.add_handler(CommandHandler("operator", operator_panel))
    
    # Operator panel navigation
    app.add_handler(CallbackQueryHandler(operator_view_active_orders, pattern="^operator_view_active_orders$"))
    app.add_handler(CallbackQueryHandler(operator_view_my_orders, pattern="^operator_view_my_orders$"))
    app.add_handler(CallbackQueryHandler(operator_view_order, pattern="^operator_order_"))
    app.add_handler(CallbackQueryHandler(operator_take_order, pattern="^operator_take_order_"))
    app.add_handler(CallbackQueryHandler(operator_complete_order, pattern="^operator_complete_order_"))
    app.add_handler(CallbackQueryHandler(operator_view_rates, pattern="^operator_view_rates$"))
    app.add_handler(CallbackQueryHandler(operator_back_to_panel, pattern="^operator_panel$"))
