# Import the constants and functions so they can be imported directly from bot.config
from bot.config.constants import BOT_TOKEN, ADMIN_ID, MAIN_CHAT_ID

# Import all public functions from bot.config module
from bot.config.config import (
    load_config, save_config, get_referral_percentage,
    update_rates, get_current_rates, add_admin,
    remove_admin, is_admin
)