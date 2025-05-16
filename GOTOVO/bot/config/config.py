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
    "operator_ids": [],  # List of operator user IDs
    "rates": {
        "ltc_usd_buy": 80.0,   # Rate for buying LTC in USD
        "ltc_usd_sell": 78.0,  # Rate for selling LTC in USD
        "usd_rub_buy": 73.5,   # Rate for buying USD in RUB
        "usd_rub_sell": 72.0   # Rate for selling USD in RUB
    },
    "min_amount": 1000.0,  # Минимальная сумма сделки в ПМР рублях
    "referral": {
        "levels": [
            {"min": 1, "max": 10, "percentage": 10.0},
            {"min": 11, "max": 25, "percentage": 12.5},
            {"min": 26, "max": 50, "percentage": 15.0},
            {"min": 51, "max": 100, "percentage": 17.5},
            {"min": 101, "max": float("inf"), "percentage": 20.0}
        ]
    },
    "currencies": {
        "crypto": [
            {"code": "LTC", "name": "Litecoin", "enabled": True}
        ],
        "fiat": [
            {"code": "USD", "name": "Доллар США", "symbol": "$", "enabled": True},
            {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "enabled": True}
        ]
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
    
    # Проверяем новую структуру конфигурации
    if "referral" in config and "levels" in config["referral"]:
        levels = config["referral"]["levels"]
        
        # Новая структура - список словарей с min, max, percentage
        for level in levels:
            if level["min"] <= referral_count <= level["max"]:
                return level["percentage"] / 100.0  # Преобразуем проценты в десятичную дробь
                
        # Если не нашли подходящий уровень, возвращаем базовый процент
        return 0.05  # 5% по умолчанию
    
    # Старая структура - словарь с ключами-уровнями
    elif "referral_levels" in config:
        levels = config["referral_levels"]
        
        # Find the highest applicable level
        percentage = 0.0
        for level, value in sorted([(int(k), v) for k, v in levels.items()]):
            if referral_count >= level:
                percentage = value
            else:
                break
        
        return percentage
    
    # Если структура не найдена, возвращаем базовый процент
    return 0.05  # 5% по умолчанию

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

def add_operator(user_id: int) -> None:
    """Add a user to operator list"""
    config = load_config()
    
    if "operator_ids" not in config:
        config["operator_ids"] = []
        
    if user_id not in config["operator_ids"]:
        config["operator_ids"].append(user_id)
        save_config(config)
        logger.info(f"User {user_id} added to operator list")

def remove_operator(user_id: int) -> None:
    """Remove a user from operator list"""
    config = load_config()
    
    if "operator_ids" not in config:
        config["operator_ids"] = []
        return
        
    if user_id in config["operator_ids"]:
        config["operator_ids"].remove(user_id)
        save_config(config)
        logger.info(f"User {user_id} removed from operator list")

def is_operator(user_id: int) -> bool:
    """Check if a user is an operator"""
    config = load_config()
    
    if "operator_ids" not in config:
        config["operator_ids"] = []
        save_config(config)
        return False
        
    return user_id in config["operator_ids"]

def get_min_amount() -> float:
    """Get minimum transaction amount in PMR rubles"""
    config = load_config()
    return config.get("min_amount", 1000.0)

def set_min_amount(amount: float) -> None:
    """Set minimum transaction amount in PMR rubles"""
    config = load_config()
    config["min_amount"] = amount
    save_config(config)
    logger.info(f"Updated minimum transaction amount to {amount} PMR")

def get_currencies() -> Dict[str, List[Dict[str, Any]]]:
    """Get all currencies (crypto and fiat)"""
    config = load_config()
    if "currencies" not in config:
        # Initialize currencies section if it doesn't exist
        config["currencies"] = {
            "crypto": [
                {"code": "LTC", "name": "Litecoin", "enabled": True}
            ],
            "fiat": [
                {"code": "USD", "name": "Доллар США", "symbol": "$", "enabled": True},
                {"code": "RUB", "name": "Российский рубль", "symbol": "₽", "enabled": True}
            ]
        }
        save_config(config)
    
    return config["currencies"]

def get_enabled_crypto_currencies() -> List[Dict[str, Any]]:
    """Get all enabled cryptocurrency options"""
    currencies = get_currencies()
    return [c for c in currencies.get("crypto", []) if c.get("enabled", False)]

def get_enabled_fiat_currencies() -> List[Dict[str, Any]]:
    """Get all enabled fiat currency options"""
    currencies = get_currencies()
    return [c for c in currencies.get("fiat", []) if c.get("enabled", False)]

def add_crypto_currency(code: str, name: str) -> None:
    """Add a new cryptocurrency to the system"""
    config = load_config()
    if "currencies" not in config:
        config["currencies"] = {"crypto": [], "fiat": []}
    
    # Check if currency already exists
    for crypto in config["currencies"]["crypto"]:
        if crypto["code"] == code:
            crypto["name"] = name
            crypto["enabled"] = True
            save_config(config)
            logger.info(f"Updated cryptocurrency {code}")
            return
    
    # Add new currency
    config["currencies"]["crypto"].append(
        {"code": code, "name": name, "enabled": True}
    )
    
    # Update rates for new cryptocurrency
    for fiat in config["currencies"]["fiat"]:
        if fiat["enabled"]:
            # Add default rates for each enabled fiat currency
            fiat_code = fiat["code"].lower()
            crypto_code = code.lower()
            
            # Default rates (1.0 for simplicity)
            rate_key_buy = f"{crypto_code}_{fiat_code}_buy"
            rate_key_sell = f"{crypto_code}_{fiat_code}_sell"
            
            if rate_key_buy not in config["rates"]:
                config["rates"][rate_key_buy] = 80.0  # Default value
            
            if rate_key_sell not in config["rates"]:
                config["rates"][rate_key_sell] = 78.0  # Default value
    
    save_config(config)
    logger.info(f"Added new cryptocurrency {code}")

def add_fiat_currency(code: str, name: str, symbol: str) -> None:
    """Add a new fiat currency to the system"""
    config = load_config()
    if "currencies" not in config:
        config["currencies"] = {"crypto": [], "fiat": []}
    
    # Check if currency already exists
    for fiat in config["currencies"]["fiat"]:
        if fiat["code"] == code:
            fiat["name"] = name
            fiat["symbol"] = symbol
            fiat["enabled"] = True
            save_config(config)
            logger.info(f"Updated fiat currency {code}")
            return
    
    # Add new currency
    config["currencies"]["fiat"].append(
        {"code": code, "name": name, "symbol": symbol, "enabled": True}
    )
    
    # Update rates for new fiat currency
    for crypto in config["currencies"]["crypto"]:
        if crypto["enabled"]:
            # Add default rates for each enabled cryptocurrency
            fiat_code = code.lower()
            crypto_code = crypto["code"].lower()
            
            # Default rates
            rate_key_buy = f"{crypto_code}_{fiat_code}_buy"
            rate_key_sell = f"{crypto_code}_{fiat_code}_sell"
            
            if rate_key_buy not in config["rates"]:
                config["rates"][rate_key_buy] = 80.0  # Default value
            
            if rate_key_sell not in config["rates"]:
                config["rates"][rate_key_sell] = 78.0  # Default value
    
    save_config(config)
    logger.info(f"Added new fiat currency {code}")

def enable_disable_currency(currency_type: str, code: str, enabled: bool) -> bool:
    """Enable or disable a currency"""
    config = load_config()
    if "currencies" not in config:
        return False
    
    currency_list = config["currencies"].get(currency_type, [])
    
    for currency in currency_list:
        if currency["code"] == code:
            currency["enabled"] = enabled
            save_config(config)
            action_text = "enabled" if enabled else "disabled"
            logger.info(f"{action_text} {currency_type} currency {code}")
            return True
    
    return False