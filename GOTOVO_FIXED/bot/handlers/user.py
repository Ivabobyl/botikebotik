import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.config.config import (
    get_current_rates, get_referral_percentage
)
from bot.database import (
    get_user, save_user, get_user_orders, create_order,
    get_referrals, add_referral
)
from bot.utils.keyboards import user_keyboard, back_button, get_main_menu_keyboard
from bot.utils.helpers import generate_referral_link, check_admin, check_operator

logger = logging.getLogger(__name__)

# User commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start command handler - registers user and shows welcome message"""
    user = update.effective_user
    user_id = user.id
    username = user.username or f"user_{user_id}"
    
    # Check for referral parameter
    referral_id = None
    if context.args and len(context.args) > 0:
        try:
            referral_id = int(context.args[0])
            
            # Don't allow self-referrals
            if referral_id == user_id:
                referral_id = None
        except ValueError:
            referral_id = None
    
    # Get or create user in database
    user_data = await get_user(user_id)
    
    if not user_data:
        # New user
        user_data = {
            "user_id": user_id,
            "username": username,
            "role": "user",
            "balance": 0,
            "total_volume": 0,
            "completed_orders": 0,
            "discount": 0,
            "referrals": [],
            "referrer_id": referral_id,
            "joined_at": update.message.date.isoformat()
        }
        await save_user(user_id, user_data)
        
        # Add user to referrer's referrals list if applicable
        if referral_id:
            await add_referral(referral_id, user_id)
            
            # Send notification to referrer
            try:
                referrer = await get_user(referral_id)
                if referrer:
                    referrer_username = referrer.get("username", f"user_{referral_id}")
                    await context.bot.send_message(
                        chat_id=referral_id,
                        text=f"🎉 *Новый реферал!*\n\n"
                             f"Пользователь {username} зарегистрировался по вашей реферальной ссылке!\n\n"
                             f"Вы будете получать бонусы от его сделок.",
                        parse_mode=ParseMode.MARKDOWN
                    )
            except Exception as e:
                logger.error(f"Failed to notify referrer: {e}")
    
    # Generate referral link
    referral_link = generate_referral_link(user_id)
    
    # Welcome message
    welcome_text = (
        f"👋 Добро пожаловать, {username}!\n\n"
        f"Я бот для обмена криптовалюты Litecoin (LTC).\n\n"
        f"🔄 С моей помощью вы можете создать заявку на покупку или продажу LTC, "
        f"просматривать текущие курсы и отслеживать статус ваших заявок.\n\n"
        f"🔗 Ваша реферальная ссылка: {referral_link}\n"
        f"Делитесь ею и получайте бонусы от сделок ваших рефералов!"
    )
    
    # Check if user is an admin or operator
    is_admin_user = await check_admin(user_id)
    is_operator_user = await check_operator(user_id)
    
    # Create keyboard with main options based on user role
    keyboard = get_main_menu_keyboard(is_operator=is_operator_user, is_admin=is_admin_user)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user profile with statistics"""
    query = update.callback_query
    if query:
        await query.answer()
        user_id = query.from_user.id
        edit_message = True
    else:
        user_id = update.effective_user.id
        edit_message = False
    
    # Get user data
    user_data = await get_user(user_id)
    
    if not user_data:
        # This should not happen if user used /start
        if edit_message:
            await query.edit_message_text("❌ Профиль не найден. Используйте /start для регистрации.")
        else:
            await update.message.reply_text("❌ Профиль не найден. Используйте /start для регистрации.")
        return
    
    # Get user orders
    user_orders = await get_user_orders(user_id)
    
    # Calculate statistics
    completed_orders = len([o for o in user_orders if o.get("status") == "completed"])
    active_orders = len([o for o in user_orders if o.get("status") in ["active", "in_progress"]])
    total_volume = user_data.get("total_volume", 0)
    balance = user_data.get("balance", 0)
    discount = user_data.get("discount", 0)
    
    # Get referrals
    referrals = await get_referrals(user_id)
    referral_count = len(referrals)
    referral_percentage = get_referral_percentage(referral_count)
    
    # Generate referral link
    referral_link = generate_referral_link(user_id)
    
    # Format profile text
    profile_text = (
        f"👤 *Профиль пользователя*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {user_data.get('username', 'Нет имени')}\n"
        f"💰 Баланс: {balance} руб.\n\n"
        f"📊 *Статистика*:\n"
        f"• Завершённых сделок: {completed_orders}\n"
        f"• Активных заявок: {active_orders}\n"
        f"• Общий оборот: {total_volume} руб.\n"
        f"• Персональная скидка: {discount}%\n\n"
        f"👥 *Реферальная программа*:\n"
        f"• Рефералов: {referral_count}\n"
        f"• Текущий бонус: {referral_percentage}% от спреда\n\n"
        f"🔗 Ваша реферальная ссылка:\n`{referral_link}`"
    )
    
    # Create keyboard
    keyboard = [
        [InlineKeyboardButton("📝 Мои заявки", callback_data="user_my_orders")],
        [InlineKeyboardButton("🔙 Назад", callback_data="user_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if edit_message:
        await query.edit_message_text(
            profile_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            profile_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show main user menu"""
    await update.callback_query.answer()
    
    keyboard = user_keyboard()
    
    await update.callback_query.edit_message_text(
        "🔄 *Главное меню*\n\nВыберите действие:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def user_view_rates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current exchange rates"""
    await update.callback_query.answer()
    
    # Get current rates
    rates = get_current_rates()
    
    # Create keyboard with back button
    keyboard = [[back_button("user_menu")]]
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

async def user_create_order_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show order creation menu"""
    await update.callback_query.answer()
    
    # Create keyboard with order type options
    keyboard = [
        [
            InlineKeyboardButton("🔵 Купить LTC", callback_data="user_create_order_buy"),
            InlineKeyboardButton("🔴 Продать LTC", callback_data="user_create_order_sell")
        ]
    ]
    keyboard.append([back_button("user_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "📝 *Создание заявки*\n\n"
        "Выберите тип операции:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def user_create_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle order type selection and ask for amount"""
    await update.callback_query.answer()
    
    # Get order type from callback data
    query_data = update.callback_query.data
    order_type = query_data.split('_')[-1]  # "buy" or "sell"
    
    # Save order type in user data
    context.user_data["order_type"] = order_type
    
    # Create keyboard with back button
    keyboard = [[back_button("user_create_order_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    order_type_text = "покупки" if order_type == "buy" else "продажи"
    
    await update.callback_query.edit_message_text(
        f"💰 *Сумма {order_type_text}*\n\n"
        f"Введите сумму в рублях для {order_type_text} LTC:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Set state to wait for amount
    context.user_data["awaiting_amount"] = True

async def user_process_order_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process order amount entered by user"""
    user_id = update.effective_user.id
    
    # Check if we are waiting for amount
    if not context.user_data.get("awaiting_amount"):
        return
    
    # Get order type from user data
    order_type = context.user_data.get("order_type")
    
    if not order_type:
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте создать заявку заново.")
        return
    
    # Parse amount from message
    try:
        amount_text = update.message.text.strip()
        amount = float(amount_text.replace(',', '.'))
        
        # Validate amount
        if amount <= 0:
            await update.message.reply_text("❌ Сумма должна быть положительным числом.")
            return
        
        # Clear awaiting state
        context.user_data["awaiting_amount"] = False
        
        # Get user data
        user = await get_user(user_id)
        username = user.get("username") if user else update.effective_user.username
        
        if not username:
            username = f"user_{user_id}"
        
        # Create order
        order = await create_order(user_id, username, order_type, amount)
        
        # Create keyboard to view orders
        keyboard = [
            [InlineKeyboardButton("📋 Мои заявки", callback_data="user_my_orders")],
            [InlineKeyboardButton("🔙 Главное меню", callback_data="user_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        order_type_text = "покупку" if order_type == "buy" else "продажу"
        
        await update.message.reply_text(
            f"✅ *Заявка успешно создана!*\n\n"
            f"• Номер заявки: {order['order_number']}\n"
            f"• Тип: {order_type_text} LTC\n"
            f"• Сумма: {amount} руб.\n\n"
            f"Оператор свяжется с вами в ближайшее время.",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректное число."
        )

async def user_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show user's orders"""
    await update.callback_query.answer()
    
    user_id = update.effective_user.id
    
    # Get user orders
    orders = await get_user_orders(user_id)
    
    # Create keyboard with back button
    keyboard = [[back_button("user_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text = "📋 *Мои заявки*\n\n"
    
    if not orders:
        text += "У вас еще нет заявок."
    else:
        # Group orders by status
        active_orders = [o for o in orders if o.get("status") == "active"]
        in_progress_orders = [o for o in orders if o.get("status") == "in_progress"]
        completed_orders = [o for o in orders if o.get("status") == "completed"]
        
        # Show active orders
        if active_orders:
            text += "*Активные заявки:*\n"
            for order in active_orders:
                order_number = order.get("order_number", "N/A")
                order_type = "Покупка" if order.get("order_type") == "buy" else "Продажа"
                amount = order.get("amount", 0)
                
                text += f"• {order_number}: {order_type} LTC, {amount} руб. ⏳\n"
            text += "\n"
        
        # Show in-progress orders
        if in_progress_orders:
            text += "*Заявки в работе:*\n"
            for order in in_progress_orders:
                order_number = order.get("order_number", "N/A")
                order_type = "Покупка" if order.get("order_type") == "buy" else "Продажа"
                amount = order.get("amount", 0)
                operator = order.get("operator_username", "Оператор")
                
                text += f"• {order_number}: {order_type} LTC, {amount} руб. 🔄 ({operator})\n"
            text += "\n"
        
        # Show completed orders (last 5)
        if completed_orders:
            text += "*Последние завершенные заявки:*\n"
            for order in completed_orders[-5:]:
                order_number = order.get("order_number", "N/A")
                order_type = "Покупка" if order.get("order_type") == "buy" else "Продажа"
                amount = order.get("amount", 0)
                
                text += f"• {order_number}: {order_type} LTC, {amount} руб. ✅\n"
    
    await update.callback_query.edit_message_text(
        text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command"""
    await user_profile(update, context)

def register_user_handlers(app: Application) -> None:
    """Register all user handlers"""
    # Start command
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("profile", profile_command))
    
    # User navigation
    app.add_handler(CallbackQueryHandler(user_menu, pattern="^user_menu$"))
    app.add_handler(CallbackQueryHandler(user_profile, pattern="^user_profile$"))
    app.add_handler(CallbackQueryHandler(user_view_rates, pattern="^user_rates$"))
    app.add_handler(CallbackQueryHandler(user_create_order_menu, pattern="^user_create_order$"))
    app.add_handler(CallbackQueryHandler(user_create_order_type, pattern="^user_create_order_(buy|sell)$"))
    app.add_handler(CallbackQueryHandler(user_my_orders, pattern="^user_my_orders$"))
    
    # Message handler for order amount
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_process_order_amount))
