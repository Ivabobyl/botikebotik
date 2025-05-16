"""
Configuration module for the bot.
"""
import os
import json
import logging
from typing import Dict, Any, List

# Path to the configuration file
CONFIG_FILE = "config.json"

# Default configuration
DEFAULT_CONFIG = {
    "admin_ids": [],  # List of admin user IDs
    "rates": {
        "ltc_usd_buy": 80.0,   # Rate for buying LTC in USD
        "ltc_usd_sell": 78.0,  # Rate for selling LTC in USD
        "usd_rub_buy": 73.5,   # Rate for buying USD in RUB
        "usd_rub_sell": 72.0   # Rate for selling USD in RUB
    },
    "referral_levels": {
        "1": 0.1,  # 10% for direct referrals
        "5": 0.15,  # 15% for 5+ referrals
        "10": 0.2,  # 20% for 10+ referrals
        "20": 0.25  # 25% for 20+ referrals
    }
}

logger = logging.getLogger(__name__)

def load_config() -> Dict[str, Any]:
    """Load bot configuration from file or create default"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
            logger.info("Configuration loaded from file")
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            logger.info("Using default configuration")
            return DEFAULT_CONFIG.copy()
    else:
        logger.info("Configuration file not found, creating default")
        config = DEFAULT_CONFIG.copy()
        save_config(config)
        return config

def save_config(config: Dict[str, Any]) -> None:
    """Save configuration to file"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved to file")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")

def get_referral_percentage(referral_count: int) -> float:
    """Get referral percentage based on referral count"""
    config = load_config()
    levels = config["referral_levels"]
    
    # Find the highest applicable level
    percentage = 0.0
    for level, value in sorted([(int(k), v) for k, v in levels.items()]):
        if referral_count >= level:
            percentage = value
        else:
            break
    
    return percentage

def update_rates(ltc_usd_buy: float, ltc_usd_sell: float, 
                 usd_rub_buy: float, usd_rub_sell: float) -> None:
    """Update cryptocurrency exchange rates"""
    config = load_config()
    
    config["rates"]["ltc_usd_buy"] = ltc_usd_buy
    config["rates"]["ltc_usd_sell"] = ltc_usd_sell
    config["rates"]["usd_rub_buy"] = usd_rub_buy
    config["rates"]["usd_rub_sell"] = usd_rub_sell
    
    save_config(config)
    logger.info("Exchange rates updated")

def get_current_rates() -> Dict[str, float]:
    """Get current cryptocurrency exchange rates"""
    config = load_config()
    return config["rates"]

def add_admin(user_id: int) -> None:
    """Add a user to admin list"""
    config = load_config()
    
    if user_id not in config["admin_ids"]:
        config["admin_ids"].append(user_id)
        save_config(config)
        logger.info(f"User {user_id} added to admin list")

def remove_admin(user_id: int) -> None:
    """Remove a user from admin list"""
    config = load_config()
    
    if user_id in config["admin_ids"]:
        config["admin_ids"].remove(user_id)
        save_config(config)
        logger.info(f"User {user_id} removed from admin list")

def is_admin(user_id: int) -> bool:
    """Check if a user is an admin"""
    from bot.config.constants import ADMIN_ID
    
    if user_id == ADMIN_ID:
        return True
        
    config = load_config()
    return user_id in config["admin_ids"]