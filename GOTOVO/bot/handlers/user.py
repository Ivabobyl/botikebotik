import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.config.config import (
    get_current_rates, get_referral_percentage, load_config
)
from bot.database import (
    get_user, save_user, get_user_orders, create_order,
    get_referrals, add_referral
)
from bot.utils.keyboards import user_keyboard, back_button, get_main_menu_keyboard
from bot.utils.helpers import generate_referral_link

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
    
    # Create keyboard with main options using ReplyKeyboardMarkup
    # Определяем, является ли пользователь оператором или админом
    is_operator = user_data.get("role") == "operator"
    is_admin = user_data.get("role") == "admin" or user_id in load_config().get("admin_ids", [])
    
    keyboard = get_main_menu_keyboard(is_operator, is_admin)
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=keyboard
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
    """Handle order type selection and show cryptocurrency options"""
    await update.callback_query.answer()
    
    # Get order type from callback data
    query_data = update.callback_query.data
    order_type = query_data.split('_')[-1]  # "buy" or "sell"
    
    # Save order type in user data
    context.user_data["order_type"] = order_type
    
    # Get current rates
    rates = get_current_rates()
    ltc_usd_rate = rates["ltc_usd_buy"] if order_type == "buy" else rates["ltc_usd_sell"]
    rub_usd_rate = rates["usd_rub_buy"] if order_type == "buy" else rates["usd_rub_sell"]
    ltc_rub_rate = ltc_usd_rate * rub_usd_rate
    
    # For now, we only have Litecoin, so we'll directly show LTC options
    crypto_type = "ltc"
    context.user_data["crypto_type"] = crypto_type
    
    action_text = "покупки" if order_type == "buy" else "продажи"
    
    await update.callback_query.edit_message_text(
        f"📊 *Покупка Litecoin (LTC)*\n\n"
        f"Текущий курс: ${ltc_usd_rate:.2f} (≈ {ltc_rub_rate:.2f} ₽)\n\n"
        f"Выберите количество LTC для {action_text} или введите свою сумму.\n"
        f"Минимальная сумма {action_text}: 0.1 LTC",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("0.1 LTC", callback_data=f"ltc_amount_{order_type}_0.1"),
                InlineKeyboardButton("0.25 LTC", callback_data=f"ltc_amount_{order_type}_0.25"),
                InlineKeyboardButton("0.5 LTC", callback_data=f"ltc_amount_{order_type}_0.5")
            ],
            [
                InlineKeyboardButton("1 LTC", callback_data=f"ltc_amount_{order_type}_1"),
                InlineKeyboardButton("2 LTC", callback_data=f"ltc_amount_{order_type}_2"),
                InlineKeyboardButton("5 LTC", callback_data=f"ltc_amount_{order_type}_5")
            ],
            [
                InlineKeyboardButton("Другая сумма", callback_data=f"ltc_amount_{order_type}_other")
            ],
            [back_button("user_create_order_menu")]
        ]),
        parse_mode=ParseMode.MARKDOWN
    )

async def ltc_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle LTC amount selection for order"""
    await update.callback_query.answer()
    
    # Get order type and amount from callback data
    query_data = update.callback_query.data
    parts = query_data.split('_')
    order_type = parts[2]  # "buy" or "sell"
    amount_choice = parts[3]  # numeric value or "other"
    
    # Get current rates
    rates = get_current_rates()
    ltc_usd_rate = rates["ltc_usd_buy"] if order_type == "buy" else rates["ltc_usd_sell"]
    rub_usd_rate = rates["usd_rub_buy"] if order_type == "buy" else rates["usd_rub_sell"]
    ltc_rub_rate = ltc_usd_rate * rub_usd_rate
    
    # If user selected "other", prompt for custom amount
    if amount_choice == "other":
        keyboard = [[back_button(f"user_create_order_{order_type}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        action_text = "покупки" if order_type == "buy" else "продажи"
        
        await update.callback_query.edit_message_text(
            f"💰 *Введите количество LTC для {action_text}*\n\n"
            f"Текущий курс: ${ltc_usd_rate:.2f} (≈ {ltc_rub_rate:.2f} ₽)\n\n"
            f"Введите количество LTC (например: 0.5):",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Set state to wait for custom amount
        context.user_data["awaiting_ltc_amount"] = True
        context.user_data["order_type"] = order_type
        return
    
    # Process predefined amount
    try:
        ltc_amount = float(amount_choice)
        # Add the function definition since it doesn't exist yet
        async def process_ltc_order_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, order_type: str, ltc_amount: float) -> None:
            """Create an order with the specified LTC amount"""
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.first_name
            
            # Get rates for conversion
            rates = get_current_rates()
            
            # Calculate equivalent amounts in USD and RUB
            ltc_usd_rate = rates["ltc_usd_buy"] if order_type == "buy" else rates["ltc_usd_sell"]
            usd_rub_rate = rates["usd_rub_buy"] if order_type == "buy" else rates["usd_rub_sell"]
            
            usd_amount = ltc_amount * ltc_usd_rate
            rub_amount = usd_amount * usd_rub_rate
            
            # Create order
            order = await create_order(user_id, username, order_type, ltc_amount)
            order_id = order["id"]
            order_number = order["order_number"]

            # Format message
            action_text = "Покупка" if order_type == "buy" else "Продажа"
            
            # Clear user data
            context.user_data.pop("order_type", None)
            context.user_data.pop("awaiting_ltc_amount", None)
            
            # Notify admin and group about the new order
            rates_info = f"LTC/USD: ${ltc_usd_rate:.2f}, USD/RUB: {usd_rub_rate:.2f} ₽"
            
            # Create message for user
            message = (
                f"✅ *Заявка создана успешно*\n\n"
                f"Номер заявки: `{order_number}`\n"
                f"Тип: {action_text} LTC\n"
                f"Количество: {ltc_amount:.8f} LTC\n"
                f"Сумма: ${usd_amount:.2f} (≈{rub_amount:.2f} ₽)\n\n"
                f"Статус: 🕒 *Ожидание*\n\n"
                f"Оператор свяжется с вами в ближайшее время."
            )
            
            # Send confirmation to user
            if hasattr(update, 'callback_query'):
                await update.callback_query.edit_message_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            
            # Send notification to admin and group
            admin_message = (
                f"🆕 *Новая заявка*\n\n"
                f"Номер: `{order_number}`\n"
                f"Пользователь: {'@' + username if username else f'ID: {user_id}'}\n"
                f"Тип: {action_text} LTC\n"
                f"Количество: {ltc_amount:.8f} LTC\n"
                f"Сумма: ${usd_amount:.2f} (≈{rub_amount:.2f} ₽)\n\n"
                f"Курс обмена: {rates_info}"
            )
            
            # Send to group chat
            from main import admin_send_message, chat_send_message
            await admin_send_message(admin_message)
            await chat_send_message(admin_message)
            
        await process_ltc_order_creation(update, context, order_type, ltc_amount)
    except ValueError:
        await update.callback_query.edit_message_text(
            "❌ Произошла ошибка. Попробуйте создать заявку заново."
        )

async def amount_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle amount choice from predefined buttons or ask for custom amount"""
    await update.callback_query.answer()
    
    # Get amount, currency and order type from callback data
    query_data = update.callback_query.data
    parts = query_data.split('_')
    currency = parts[1]  # "usd" or "rub"
    order_type = parts[2]  # "buy" or "sell"
    amount_choice = parts[3]  # numerical value or "other"
    
    context.user_data["currency"] = currency
    context.user_data["order_type"] = order_type
    
    # If user selected "other", prompt for custom amount
    if amount_choice == "other":
        keyboard = [[back_button(f"currency_choice_{currency}_{order_type}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        order_type_text = "покупки" if order_type == "buy" else "продажи"
        currency_symbol = "$" if currency == "usd" else "₽"
        
        await update.callback_query.edit_message_text(
            f"💰 *Введите сумму {order_type_text}*\n\n"
            f"Введите сумму в {currency_symbol} для {order_type_text} LTC:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Set state to wait for custom amount
        context.user_data["awaiting_amount"] = True
        return
    
    # Process predefined amount
    try:
        amount = float(amount_choice)
        await process_order_creation(update, context, amount)
    except ValueError:
        await update.callback_query.edit_message_text(
            "❌ Произошла ошибка. Попробуйте создать заявку заново."
        )

async def process_order_creation(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: float = None):
    """Create an order with the specified amount"""
    is_callback = update.callback_query is not None
    
    user_id = update.effective_user.id
    
    # Get order details from user data
    order_type = context.user_data.get("order_type")
    currency = context.user_data.get("currency")
    
    if not order_type or not currency:
        message = "❌ Произошла ошибка. Попробуйте создать заявку заново."
        if is_callback:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    # If no amount provided (from callback), parse it from message
    if amount is None:
        try:
            amount_text = update.message.text.strip()
            amount = float(amount_text.replace(',', '.'))
        except (ValueError, AttributeError):
            await update.message.reply_text("❌ Пожалуйста, введите корректное число.")
            return
    
    # Validate amount
    if amount <= 0:
        message = "❌ Сумма должна быть положительным числом."
        if is_callback:
            await update.callback_query.edit_message_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    # Convert USD to Rubles if currency is USD
    rubles_amount = amount
    if currency == "usd":
        rates = get_current_rates()
        if order_type == "buy":
            rubles_amount = amount * rates["usd_rub_buy"]
        else:
            rubles_amount = amount * rates["usd_rub_sell"]
    
    # Clear awaiting state
    if context.user_data.get("awaiting_amount"):
        context.user_data["awaiting_amount"] = False
    
    # Get user data
    user = await get_user(user_id)
    username = user.get("username") if user else update.effective_user.username
    
    if not username:
        username = f"user_{user_id}"
    
    # Create order
    order = await create_order(user_id, username, order_type, rubles_amount)
    
    # Create keyboard to view orders
    keyboard = [
        [InlineKeyboardButton("📋 Мои заявки", callback_data="user_my_orders")],
        [InlineKeyboardButton("🔙 Главное меню", callback_data="user_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    order_type_text = "покупку" if order_type == "buy" else "продажу"
    currency_symbol = "$" if currency == "usd" else "₽"
    
    message_text = (
        f"✅ *Заявка успешно создана!*\n\n"
        f"• Номер заявки: {order['order_number']}\n"
        f"• Тип: {order_type_text} LTC\n"
        f"• Сумма: {amount} {currency_symbol}"
    )
    
    # Add conversion if currency is USD
    if currency == "usd":
        message_text += f" ({rubles_amount:.2f} ₽)"
    
    message_text += "\n\nОператор свяжется с вами в ближайшее время."
    
    if is_callback:
        await update.callback_query.edit_message_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

async def user_process_order_amount(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process custom order amount entered by user"""
    # Check if we are waiting for LTC amount
    if context.user_data.get("awaiting_ltc_amount"):
        # Get order type
        order_type = context.user_data.get("order_type")
        if not order_type:
            await update.message.reply_text("❌ Ошибка: не указан тип заявки. Пожалуйста, начните заново.")
            return
        
        # Parse the LTC amount
        try:
            ltc_amount_text = update.message.text.strip()
            ltc_amount = float(ltc_amount_text.replace(',', '.'))
            
            # Check if amount is positive
            if ltc_amount <= 0:
                await update.message.reply_text("❌ Количество LTC должно быть положительным числом.")
                return
            
            # Check if amount is at least 0.1 LTC
            if ltc_amount < 0.1:
                await update.message.reply_text("❌ Минимальное количество LTC для заявки: 0.1")
                return
            
            # Process the order creating and using the same inline function as defined above
            await process_ltc_order_creation(update, context, order_type, ltc_amount)
            
        except ValueError:
            await update.message.reply_text("❌ Пожалуйста, введите корректное число.")
            return
    
    # For backward compatibility (old amount handler)
    elif context.user_data.get("awaiting_amount"):
        # Process the order with the entered amount
        await process_order_creation(update, context)

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
    
    # LTC amount selection handler
    app.add_handler(CallbackQueryHandler(ltc_amount_handler, pattern="^ltc_amount_(buy|sell)_(.+)$"))
    
    # For backward compatibility
    app.add_handler(CallbackQueryHandler(amount_choice_handler, pattern="^amount_(usd|rub)_(buy|sell)_([0-9]+|other)$"))
    
    # Message handler for order amount
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, user_process_order_amount))
