"""
Модуль для управления валютами в админ-панели.
"""

import logging
from typing import Dict, Any, Optional, List

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from bot.config.config import load_config, save_config
from bot.utils.helpers import check_admin

logger = logging.getLogger(__name__)

async def handle_currency_management(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отображает меню управления валютами"""
    user_id = update.effective_user.id
    
    # Проверяем права администратора
    if not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для управления валютами."
        )
        return
    
    # Получаем текущие валюты
    config = load_config()
    crypto_currencies = config.get("currencies", {}).get("crypto", [])
    fiat_currencies = config.get("currencies", {}).get("fiat", [])
    
    # Формируем сообщение
    crypto_list = "\n".join([
        f"{'✅' if c.get('enabled', True) else '❌'} {c.get('name', '')} ({c.get('code', '')})"
        for c in crypto_currencies if c.get('code') not in ['➕', '🔙']
    ])
    
    fiat_list = "\n".join([
        f"{'✅' if c.get('enabled', True) else '❌'} {c.get('name', '')} ({c.get('code', '')})"
        for c in fiat_currencies if c.get('code') not in ['➕', '🔙']
    ])
    
    message_text = (
        "💱 *Управление валютами*\n\n"
        "*Криптовалюты:*\n"
        f"{crypto_list or 'Нет добавленных криптовалют'}\n\n"
        "*Фиатные валюты:*\n"
        f"{fiat_list or 'Нет добавленных фиатных валют'}\n\n"
        "Выберите действие:"
    )
    
    # Создаем клавиатуру
    keyboard = ReplyKeyboardMarkup([
        ["➕ Добавить крипту", "➕ Добавить фиат"],
        ["✅ Вкл/Выкл валюту"],
        ["🔄 Назад в админ-панель"],
        ["🏠 Главное меню"]
    ], resize_keyboard=True)
    
    # Устанавливаем состояние
    context.user_data["admin_state"] = "currency_management"
    
    await update.message.reply_text(
        message_text,
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_add_crypto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик добавления криптовалюты"""
    # Устанавливаем состояние
    context.user_data["admin_state"] = "add_crypto"
    
    await update.message.reply_text(
        "🪙 *Добавление криптовалюты*\n\n"
        "Отправьте информацию о криптовалюте в формате:\n"
        "```\n"
        "код название\n"
        "```\n"
        "Например: `BTC Bitcoin`\n\n"
        "или нажмите кнопку для возврата.",
        reply_markup=ReplyKeyboardMarkup([
            ["🔄 Назад в админ-панель"],
            ["🏠 Главное меню"]
        ], resize_keyboard=True),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_add_fiat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик добавления фиатной валюты"""
    # Устанавливаем состояние
    context.user_data["admin_state"] = "add_fiat"
    
    await update.message.reply_text(
        "💵 *Добавление фиатной валюты*\n\n"
        "Отправьте информацию о валюте в формате:\n"
        "```\n"
        "код название символ\n"
        "```\n"
        "Например: `EUR Евро €`\n\n"
        "или нажмите кнопку для возврата.",
        reply_markup=ReplyKeyboardMarkup([
            ["🔄 Назад в админ-панель"],
            ["🏠 Главное меню"]
        ], resize_keyboard=True),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_toggle_currency_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик включения/выключения валюты"""
    # Устанавливаем состояние
    context.user_data["admin_state"] = "toggle_currency_status"
    
    # Получаем список валют
    config = load_config()
    crypto_currencies = config.get("currencies", {}).get("crypto", [])
    fiat_currencies = config.get("currencies", {}).get("fiat", [])
    
    # Формируем список всех валют
    all_currencies = [
        f"CRYPTO:{c.get('code')}" for c in crypto_currencies if c.get('code') not in ['➕', '🔙']
    ] + [
        f"FIAT:{c.get('code')}" for c in fiat_currencies if c.get('code') not in ['➕', '🔙']
    ]
    
    # Формируем сообщение
    message_text = (
        "✅ *Включение/выключение валюты*\n\n"
        "Отправьте код валюты для переключения её статуса.\n"
        "Например: `BTC` или `USD`\n\n"
        "Список доступных валют:\n"
    )
    
    for currency_code in all_currencies:
        currency_type, code = currency_code.split(":")
        if currency_type == "CRYPTO":
            currency = next((c for c in crypto_currencies if c.get('code') == code), None)
        else:
            currency = next((c for c in fiat_currencies if c.get('code') == code), None)
            
        if currency:
            status = "✅" if currency.get("enabled", True) else "❌"
            message_text += f"{status} {currency.get('name', '')} ({code})\n"
    
    await update.message.reply_text(
        message_text,
        reply_markup=ReplyKeyboardMarkup([
            ["🔄 Назад в админ-панель"],
            ["🏠 Главное меню"]
        ], resize_keyboard=True),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_admin_currency_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений при управлении валютами"""
    user_id = update.effective_user.id
    
    # Проверяем права администратора
    if not await check_admin(user_id):
        await update.message.reply_text(
            "⛔ У вас нет прав администратора для управления валютами."
        )
        return
    
    message_text = update.message.text
    admin_state = context.user_data.get("admin_state", None)
    
    # Обработка кнопок навигации
    if message_text == "🔄 Назад в админ-панель":
        # Вызываем обработчик кнопки возврата в админ-панель
        from bot.handlers.button_handler import process_button
        await process_button(update, context, message_text)
        return
        
    elif message_text == "🏠 Главное меню":
        # Вызываем обработчик кнопки возврата в главное меню
        from bot.handlers.button_handler import process_button
        await process_button(update, context, message_text)
        return
    
    # Обработка добавления или переключения валют
    if admin_state == "currency_management":
        if message_text == "➕ Добавить крипту":
            await handle_add_crypto(update, context)
            return
        elif message_text == "➕ Добавить фиат":
            await handle_add_fiat(update, context)
            return
        elif message_text == "✅ Вкл/Выкл валюту":
            await handle_toggle_currency_status(update, context)
            return
    
    # Обработка добавления криптовалюты
    elif admin_state == "add_crypto":
        try:
            parts = message_text.split()
            if len(parts) >= 2:
                code = parts[0].upper()
                name = " ".join(parts[1:])
                
                # Получаем текущие валюты
                config = load_config()
                crypto_currencies = config.get("currencies", {}).get("crypto", [])
                
                # Проверяем, не существует ли уже такая валюта
                if any(c.get("code") == code for c in crypto_currencies):
                    await update.message.reply_text(
                        f"❌ Криптовалюта с кодом {code} уже существует.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Добавляем новую валюту
                crypto_currencies.append({
                    "code": code,
                    "name": name,
                    "enabled": True
                })
                
                # Сохраняем изменения
                config["currencies"]["crypto"] = crypto_currencies
                save_config(config)
                
                await update.message.reply_text(
                    f"✅ Криптовалюта {name} ({code}) успешно добавлена.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Возвращаемся в меню управления валютами
                await handle_currency_management(update, context)
            else:
                await update.message.reply_text(
                    "❌ Неверный формат. Отправьте в формате: `код название`",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error adding crypto: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при добавлении криптовалюты.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Обработка добавления фиатной валюты
    elif admin_state == "add_fiat":
        try:
            parts = message_text.split()
            if len(parts) >= 3:
                code = parts[0].upper()
                symbol = parts[-1]
                name = " ".join(parts[1:-1])
                
                # Получаем текущие валюты
                config = load_config()
                fiat_currencies = config.get("currencies", {}).get("fiat", [])
                
                # Проверяем, не существует ли уже такая валюта
                if any(c.get("code") == code for c in fiat_currencies):
                    await update.message.reply_text(
                        f"❌ Валюта с кодом {code} уже существует.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Добавляем новую валюту
                fiat_currencies.append({
                    "code": code,
                    "name": name,
                    "symbol": symbol,
                    "enabled": True
                })
                
                # Сохраняем изменения
                config["currencies"]["fiat"] = fiat_currencies
                save_config(config)
                
                await update.message.reply_text(
                    f"✅ Валюта {name} ({code}) {symbol} успешно добавлена.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Возвращаемся в меню управления валютами
                await handle_currency_management(update, context)
            else:
                await update.message.reply_text(
                    "❌ Неверный формат. Отправьте в формате: `код название символ`",
                    parse_mode=ParseMode.MARKDOWN
                )
        except Exception as e:
            logger.error(f"Error adding fiat: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при добавлении валюты.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    # Обработка включения/выключения валюты
    elif admin_state == "toggle_currency_status":
        try:
            code = message_text.strip().upper()
            
            # Получаем текущие валюты
            config = load_config()
            crypto_currencies = config.get("currencies", {}).get("crypto", [])
            fiat_currencies = config.get("currencies", {}).get("fiat", [])
            
            # Ищем валюту в списке крипто
            crypto_currency = next((c for c in crypto_currencies if c.get("code") == code), None)
            if crypto_currency:
                crypto_currency["enabled"] = not crypto_currency.get("enabled", True)
                config["currencies"]["crypto"] = crypto_currencies
                save_config(config)
                
                status = "включена" if crypto_currency["enabled"] else "отключена"
                await update.message.reply_text(
                    f"✅ Криптовалюта {crypto_currency.get('name')} ({code}) {status}.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Возвращаемся в меню управления валютами
                await handle_currency_management(update, context)
                return
            
            # Ищем валюту в списке фиатных
            fiat_currency = next((c for c in fiat_currencies if c.get("code") == code), None)
            if fiat_currency:
                fiat_currency["enabled"] = not fiat_currency.get("enabled", True)
                config["currencies"]["fiat"] = fiat_currencies
                save_config(config)
                
                status = "включена" if fiat_currency["enabled"] else "отключена"
                await update.message.reply_text(
                    f"✅ Валюта {fiat_currency.get('name')} ({code}) {status}.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Возвращаемся в меню управления валютами
                await handle_currency_management(update, context)
                return
            
            # Если валюта не найдена
            await update.message.reply_text(
                f"❌ Валюта с кодом {code} не найдена.",
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            logger.error(f"Error toggling currency status: {e}")
            await update.message.reply_text(
                "❌ Произошла ошибка при изменении статуса валюты.",
                parse_mode=ParseMode.MARKDOWN
            )