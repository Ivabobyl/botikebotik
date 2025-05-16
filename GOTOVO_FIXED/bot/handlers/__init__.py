from telegram.ext import Application

from bot.handlers.admin import register_admin_handlers
from bot.handlers.operator import register_operator_handlers
from bot.handlers.user import register_user_handlers
from bot.handlers.common import register_common_handlers

def register_handlers(app: Application) -> None:
    """Register all message handlers with the application"""
    # Register common handlers first (commands available to all users)
    register_common_handlers(app)
    
    # Register user handlers
    register_user_handlers(app)
    
    # Register operator handlers
    register_operator_handlers(app)
    
    # Register admin handlers last (to handle admin-specific commands)
    register_admin_handlers(app)
    
    # Register custom commands handler at the end - this handles any commands not handled by the handlers above
    from bot.handlers.common import handle_custom_command
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.COMMAND, handle_custom_command))
