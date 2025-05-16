import logging
from typing import Dict, List, Any, Optional, Union, Tuple, cast

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

from bot.database import get_custom_command

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

async def handler_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle all messages that are not commands"""
    if not update.message or not update.message.text:
        return
        
    from bot.handlers.button_handler import is_known_button, process_button
        
    # Get message text
    message_text = update.message.text.strip()
    
    # Check if this is a button press
    if is_known_button(message_text):
        # Process button centrally
        button_processed = await process_button(update, context, message_text)
        if button_processed:
            return
            
    # Not a button or not processed, handle as regular message
    # Here you can add any other message handling logic
    
    # If no specific handlers matched, we can give a generic response
    # only if this wasn't a button press
    if not is_known_button(message_text):
        await update.message.reply_text(
            "Я не понимаю эту команду. Используйте /help для списка доступных команд или кнопки меню для навигации."
        )

def register_common_handlers(app: Application) -> None:
    """Register common handlers available to all users"""
    # Help command
    app.add_handler(CommandHandler("help", help_command))
    
    # Add message handler for buttons and other messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler_message))
    
    # Add callback handlers first (they don't conflict with commands)
    app.add_handler(CallbackQueryHandler(handle_custom_button, pattern="^custom_button_"))
    app.add_handler(CallbackQueryHandler(handle_custom_back, pattern="^custom_back_"))
    
    # Custom commands should be registered AFTER all other regular commands in the register_handlers function
    # This will be done in register_handlers after all other handlers are registered
