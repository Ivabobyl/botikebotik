import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

from telegram import Bot

from bot.database import get_user, save_user, update_order
from bot.config.constants import ADMIN_ID, MAIN_CHAT_ID

logger = logging.getLogger(__name__)

async def check_admin(user_id: int) -> bool:
    """Check if user is an admin"""
    # Import here to avoid circular imports
    from bot.config.config import is_admin
    
    # Check against hardcoded admin ID first
    if user_id == ADMIN_ID:
        return True
        
    user = await get_user(user_id)
    if not user:
        return False
    
    return user.get("role") == "admin" or is_admin(user_id)

async def check_operator(user_id: int) -> bool:
    """Check if user is an operator or admin"""
    # Admin is always an operator
    if await check_admin(user_id):
        return True
        
    user = await get_user(user_id)
    if not user:
        return False
    
    return user.get("role") in ["operator", "admin"]

def is_valid_user_id(user_id_str: str) -> bool:
    """Check if a string is a valid user ID"""
    try:
        user_id = int(user_id_str)
        return user_id > 0
    except ValueError:
        return False

def generate_referral_link(user_id: int) -> str:
    """Generate a referral link for a user"""
    bot_username = "your_crypto_exchange_bot"  # Замените на фактическое имя вашего бота
    return f"https://t.me/{bot_username}?start={user_id}"

async def calculate_spread(amount: float, order_type: str) -> float:
    """Calculate spread (profit) for an order"""
    # Import here to avoid circular imports
    from bot.config.config import get_current_rates
    
    rates = get_current_rates()
    
    # Calculate spread based on order type (buy/sell)
    is_buy = order_type == "buy"
    
    # Simple spread calculation (more complex logic can be implemented)
    if is_buy:
        # User is buying LTC, we sell at a higher rate
        actual_rate = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
        our_cost_rate = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
    else:
        # User is selling LTC, we buy at a lower rate
        actual_rate = rates["ltc_usd_sell"] * rates["usd_rub_sell"]
        our_cost_rate = rates["ltc_usd_buy"] * rates["usd_rub_buy"]
    
    # Calculate LTC amount from rubles
    ltc_amount = amount / actual_rate
    
    # Calculate our cost
    our_cost = ltc_amount * our_cost_rate
    
    # Calculate spread
    if is_buy:
        spread = amount - our_cost
    else:
        spread = our_cost - amount
    
    return round(spread, 2)  # Round to 2 decimal places

async def process_referral_bonus(bot: Bot, user_id: int, spread: float) -> None:
    """Process referral bonus for completed order"""
    user = await get_user(user_id)
    
    if not user:
        logger.error(f"User not found for referral bonus: {user_id}")
        return
    
    # Check if user has a referrer
    referrer_id = user.get("referrer_id")
    
    if not referrer_id:
        return  # No referrer to reward
    
    # Get referrer data
    referrer = await get_user(referrer_id)
    
    if not referrer:
        logger.error(f"Referrer not found: {referrer_id}")
        return
    
    # Import here to avoid circular imports
    from bot.config.config import get_referral_percentage
    
    # Calculate bonus based on referral count
    referral_count = len(referrer.get("referrals", []))
    bonus_percentage = get_referral_percentage(referral_count)
    
    if bonus_percentage <= 0:
        return  # No bonus to process
    
    # Calculate bonus amount
    bonus_amount = (spread * bonus_percentage) / 100
    
    if bonus_amount <= 0:
        return
    
    # Add bonus to referrer's balance
    current_balance = referrer.get("balance", 0)
    referrer["balance"] = current_balance + bonus_amount
    
    # Save updated referrer data
    await save_user(referrer_id, referrer)
    
    # Notify referrer about the bonus
    try:
        username = user.get("username", f"ID:{user_id}")
        
        notification_text = (
            f"💰 *Реферальный бонус!*\n\n"
            f"Вы получили бонус от сделки вашего реферала:\n"
            f"• Реферал: {username}\n"
            f"• Размер бонуса: {bonus_amount:.2f} руб. ({bonus_percentage}% от спреда)\n"
            f"• Ваш текущий баланс: {referrer['balance']:.2f} руб."
        )
        
        await bot.send_message(
            chat_id=referrer_id,
            text=notification_text,
            parse_mode="MARKDOWN"
        )
    except Exception as e:
        logger.error(f"Failed to send referral bonus notification: {e}")

async def send_order_notification(bot: Bot, order: Dict[str, Any]) -> None:
    """Send order completion notification and process referral bonus"""
    try:
        # Get order details
        user_id = order.get("user_id")
        if not user_id:
            logger.error("Cannot send notification: user_id is missing in order")
            return
            
        order_number = order.get("order_number", "N/A")
        username = order.get("username", "Нет имени")
        operator_username = order.get("operator_username", "Оператор")
        order_type = "Покупка LTC" if order.get("order_type") == "buy" else "Продажа LTC"
        amount = order.get("amount", 0)
        spread = order.get("spread", 0)
        
        # Format notification for client (without spread info)
        client_notification = (
            f"✅ *Заявка {order_number} завершена!*\n\n"
            f"• Тип сделки: {order_type}\n"
            f"• Сумма: {amount} рублей\n"
            f"• Оператор: {operator_username}"
        )
        
        # Format notification for group chat (with spread info)
        group_notification = (
            f"✅ *Заявка {order_number} завершена!*\n\n"
            f"• Пользователь: {username} | ID: `{user_id}`\n"
            f"• Оператор: {operator_username}\n"
            f"• Тип сделки: {order_type}\n"
            f"• Сумма: {amount} рублей\n"
            f"• Спред: +{spread} рублей"
        )
        
        # Send notification to client
        await bot.send_message(
            chat_id=user_id,
            text=client_notification,
            parse_mode="MARKDOWN"
        )
        
        # Send notification to group chat
        try:
            await bot.send_message(
                chat_id=MAIN_CHAT_ID,
                text=group_notification,
                parse_mode="MARKDOWN"
            )
        except Exception as e:
            logger.error(f"Failed to send group notification: {e}")
            # Try to notify admin directly
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ Не удалось отправить уведомление в чат. Ошибка: {e}\n\n{group_notification}",
                parse_mode="MARKDOWN"
            )
        
        # Process referral bonus if applicable
        if spread > 0 and user_id:
            await process_referral_bonus(bot, int(user_id), spread)
            
        # Update user total volume
        if user_id:
            user = await get_user(int(user_id))
            if user:
                # Update user stats
                user["total_volume"] = user.get("total_volume", 0) + amount
                user["completed_orders"] = user.get("completed_orders", 0) + 1
                
                # Save updated user data
                await save_user(int(user_id), user)
            
    except Exception as e:
        logger.error(f"Failed to send order notification: {e}")
        # Try to notify admin about the error
        try:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=f"❌ Ошибка при отправке уведомления о заявке: {e}"
            )
        except:
            pass

def format_datetime(dt_str: str) -> str:
    """Format ISO datetime string to a readable format"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except (ValueError, TypeError):
        return "N/A"

async def is_user_blocked(user_id: int) -> bool:
    """Check if a user is blocked"""
    user = await get_user(user_id)
    if not user:
        return False
    
    return user.get("role") == "blocked"
