from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

def user_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for regular users"""
    keyboard = [
        [
            InlineKeyboardButton("💱 Курсы валют", callback_data="user_rates"),
            InlineKeyboardButton("📝 Создать заявку", callback_data="user_create_order")
        ],
        [
            InlineKeyboardButton("👤 Мой профиль", callback_data="user_profile"),
            InlineKeyboardButton("📋 Мои заявки", callback_data="user_my_orders")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def operator_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for operators"""
    keyboard = [
        [
            InlineKeyboardButton("📋 Активные заявки", callback_data="operator_view_active_orders"),
            InlineKeyboardButton("🔄 Мои заявки", callback_data="operator_view_my_orders")
        ],
        [
            InlineKeyboardButton("💱 Курсы валют", callback_data="operator_view_rates")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_keyboard() -> InlineKeyboardMarkup:
    """Create a keyboard for admin panel"""
    keyboard = [
        [
            InlineKeyboardButton("👥 Управление пользователями", callback_data="admin_manage_users"),
            InlineKeyboardButton("💱 Управление курсами", callback_data="admin_manage_rates")
        ],
        [
            InlineKeyboardButton("💰 Управление балансом", callback_data="admin_manage_balance"),
            InlineKeyboardButton("📊 Статистика заявок", callback_data="admin_order_stats")
        ],
        [
            InlineKeyboardButton("🔧 Управление командами", callback_data="admin_custom_commands")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def confirm_keyboard(confirm_data: str, cancel_data: str) -> InlineKeyboardMarkup:
    """Create a confirmation keyboard with confirm/cancel buttons"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data=confirm_data),
            InlineKeyboardButton("❌ Отменить", callback_data=cancel_data)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def back_button(callback_data: str) -> list:
    """Create a back button for navigation"""
    return [InlineKeyboardButton("🔙 Назад", callback_data=callback_data)]

def pagination_keyboard(
    current_page: int, 
    total_pages: int, 
    base_callback: str,
    with_back: bool = True,
    back_callback: str = "user_menu"
) -> InlineKeyboardMarkup:
    """Create a pagination keyboard"""
    keyboard = []
    
    # Add pagination controls if more than one page
    if total_pages > 1:
        row = []
        if current_page > 1:
            row.append(InlineKeyboardButton("⬅️", callback_data=f"{base_callback}_{current_page-1}"))
        
        row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
        
        if current_page < total_pages:
            row.append(InlineKeyboardButton("➡️", callback_data=f"{base_callback}_{current_page+1}"))
        
        keyboard.append(row)
    
    # Add back button if requested
    if with_back:
        keyboard.append(back_button(back_callback))
    
    return InlineKeyboardMarkup(keyboard)

def order_actions_keyboard(order_id: int, status: str, user_is_operator: bool = False) -> InlineKeyboardMarkup:
    """Create keyboard with actions for an order based on its status"""
    keyboard = []
    
    if status == "active" and user_is_operator:
        # Order is active and user is an operator
        keyboard.append([InlineKeyboardButton("🔄 Работаю", callback_data=f"operator_take_order_{order_id}")])
    elif status == "in_progress" and user_is_operator:
        # Order is in progress and user is the assigned operator
        keyboard.append([InlineKeyboardButton("✅ Завершить", callback_data=f"operator_complete_order_{order_id}")])
    
    # Add appropriate back button based on user role and order status
    if user_is_operator:
        if status == "active":
            keyboard.append(back_button("operator_view_active_orders"))
        elif status == "in_progress":
            keyboard.append(back_button("operator_view_my_orders"))
        else:
            keyboard.append(back_button("operator_panel"))
    else:
        keyboard.append(back_button("user_my_orders"))
    
    return InlineKeyboardMarkup(keyboard)

def get_main_menu_keyboard(is_operator: bool = False, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Create main menu keyboard with appropriate buttons based on user role"""
    keyboard = []
    
    # Common buttons for all users
    keyboard.append(["📝 Купить крипту", "📉 Продать крипту"])
    keyboard.append(["👤 Профиль", "📋 Мои заявки"])
    keyboard.append(["🔍 Курсы обмена", "❓ Информация"])
    
    # Add operator buttons
    if is_operator or is_admin:
        keyboard.append(["📋 Активные заявки"])
        
    # Add admin button
    if is_admin:
        keyboard.append(["🔐 Админ-панель"])
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_keyboard() -> ReplyKeyboardMarkup:
    """Create admin panel keyboard"""
    keyboard = [
        ["⚙️ Установить курсы", "📝 Управление заявками"],
        ["📊 Статистика", "👥 Управление пользователями"],
        ["📨 Создать рассылку", "⚡ Настройки бота"],
        ["💬 Управление текстами", "🔘 Управление кнопками"],
        ["💱 Управление валютами", "🔔 Уведомления"],
        ["🔙 Назад", "🏠 Главное меню"]
    ]
    
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Create a simple keyboard with just back to main menu button"""
    keyboard = [["🏠 Главное меню"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
