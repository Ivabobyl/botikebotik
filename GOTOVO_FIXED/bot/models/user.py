from typing import Dict, List, Any, Optional

# User model structure (for reference)
USER_MODEL = {
    "user_id": 0,               # Telegram user ID
    "username": "",             # Telegram username
    "role": "user",             # user, operator, admin, or blocked
    "balance": 0.0,             # User balance in rubles
    "total_volume": 0.0,        # Total trading volume
    "completed_orders": 0,      # Number of completed orders
    "discount": 0.0,            # Personal discount percentage
    "referrals": [],            # List of referral user IDs
    "referrer_id": None,        # ID of the user who referred this user
    "joined_at": ""             # ISO format datetime when user joined
}

class UserRole:
    """User role constants"""
    USER = "user"
    OPERATOR = "operator"
    ADMIN = "admin"
    BLOCKED = "blocked"

def create_user_dict(user_id: int, username: str, role: str = UserRole.USER) -> Dict[str, Any]:
    """Create a new user dictionary with default values"""
    import datetime
    
    return {
        "user_id": user_id,
        "username": username,
        "role": role,
        "balance": 0.0,
        "total_volume": 0.0,
        "completed_orders": 0,
        "discount": 0.0,
        "referrals": [],
        "referrer_id": None,
        "joined_at": datetime.datetime.now().isoformat()
    }

def update_user_balance(user_data: Dict[str, Any], amount: float) -> Dict[str, Any]:
    """Update user balance - positive amount adds to balance, negative subtracts"""
    user_data["balance"] = user_data.get("balance", 0) + amount
    return user_data

def add_referral_to_user(user_data: Dict[str, Any], referral_id: int) -> Dict[str, Any]:
    """Add a referral to user's referrals list"""
    if "referrals" not in user_data:
        user_data["referrals"] = []
    
    if referral_id not in user_data["referrals"]:
        user_data["referrals"].append(referral_id)
    
    return user_data

def set_user_role(user_data: Dict[str, Any], role: str) -> Dict[str, Any]:
    """Set user role"""
    user_data["role"] = role
    return user_data
