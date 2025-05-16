import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union

logger = logging.getLogger(__name__)

# Database file paths
USERS_DB = "data/users.json"
ORDERS_DB = "data/orders.json"
CUSTOM_COMMANDS_DB = "data/commands.json"

# Initialize database locks for thread safety
user_lock = asyncio.Lock()
order_lock = asyncio.Lock()
command_lock = asyncio.Lock()

async def init_db() -> None:
    """Initialize database files if they don't exist"""
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Initialize users database
    if not os.path.exists(USERS_DB):
        async with user_lock:
            with open(USERS_DB, 'w', encoding='utf-8') as f:
                json.dump({}, f)
    
    # Initialize orders database
    if not os.path.exists(ORDERS_DB):
        async with order_lock:
            with open(ORDERS_DB, 'w', encoding='utf-8') as f:
                json.dump({"orders": [], "next_id": 1}, f)
    
    # Initialize custom commands database
    if not os.path.exists(CUSTOM_COMMANDS_DB):
        async with command_lock:
            with open(CUSTOM_COMMANDS_DB, 'w', encoding='utf-8') as f:
                json.dump({"commands": []}, f)
    
    logger.info("Database initialized")

# User database functions
async def get_users() -> Dict[str, Any]:
    """Get all users from database"""
    async with user_lock:
        try:
            with open(USERS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading users database: {str(e)}")
            return {}

async def save_users(users: Dict[str, Any]) -> None:
    """Save users to database"""
    async with user_lock:
        try:
            with open(USERS_DB, 'w', encoding='utf-8') as f:
                json.dump(users, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving users database: {str(e)}")

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID"""
    users = await get_users()
    return users.get(str(user_id))

async def save_user(user_id: int, user_data: Dict[str, Any]) -> None:
    """Save user data"""
    users = await get_users()
    users[str(user_id)] = user_data
    await save_users(users)

async def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Get users by role"""
    users = await get_users()
    return [user for user_id, user in users.items() if user.get("role") == role]

async def get_referrals(user_id: int) -> List[int]:
    """Get referrals for a user"""
    user = await get_user(user_id)
    if user:
        return user.get("referrals", [])
    return []

async def add_referral(user_id: int, referral_id: int) -> None:
    """Add a referral to a user"""
    user = await get_user(user_id)
    if user:
        if "referrals" not in user:
            user["referrals"] = []
        if referral_id not in user["referrals"]:
            user["referrals"].append(referral_id)
            await save_user(user_id, user)

# Order database functions
async def get_orders() -> Dict[str, Any]:
    """Get all orders from database"""
    async with order_lock:
        try:
            with open(ORDERS_DB, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading orders database: {str(e)}")
            return {"orders": [], "next_id": 1}

async def save_orders(orders_data: Dict[str, Any]) -> None:
    """Save orders to database"""
    async with order_lock:
        try:
            with open(ORDERS_DB, 'w', encoding='utf-8') as f:
                json.dump(orders_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving orders database: {str(e)}")

async def create_order(user_id: int, username: str, 
                      order_type: str, amount: float) -> Dict[str, Any]:
    """Create a new order"""
    orders_data = await get_orders()
    order_id = orders_data["next_id"]
    
    # Create order with Z prefix and zero-padded ID (e.g., Z00001)
    order_number = f"Z{order_id:05d}"
    
    import datetime
    now = datetime.datetime.now().isoformat()
    
    order = {
        "id": order_id,
        "order_number": order_number,
        "user_id": user_id,
        "username": username,
        "order_type": order_type,  # "buy" or "sell"
        "amount": amount,
        "status": "active",  # active, in_progress, completed
        "created_at": now,
        "updated_at": now,
        "operator_id": None,
        "operator_username": None,
        "completed_at": None,
        "spread": None
    }
    
    orders_data["orders"].append(order)
    orders_data["next_id"] = order_id + 1
    
    await save_orders(orders_data)
    return order

async def get_order(order_id: int) -> Optional[Dict[str, Any]]:
    """Get order by ID"""
    orders_data = await get_orders()
    for order in orders_data["orders"]:
        if order["id"] == order_id:
            return order
    return None

async def get_order_by_number(order_number: str) -> Optional[Dict[str, Any]]:
    """Get order by order number (Z12345)"""
    orders_data = await get_orders()
    for order in orders_data["orders"]:
        if order["order_number"] == order_number:
            return order
    return None

async def update_order(order_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update an order"""
    orders_data = await get_orders()
    
    for i, order in enumerate(orders_data["orders"]):
        if order["id"] == order_id:
            import datetime
            updates["updated_at"] = datetime.datetime.now().isoformat()
            orders_data["orders"][i] = {**order, **updates}
            await save_orders(orders_data)
            return orders_data["orders"][i]
    
    return None

async def get_active_orders() -> List[Dict[str, Any]]:
    """Get all active orders"""
    orders_data = await get_orders()
    return [order for order in orders_data["orders"] if order["status"] == "active"]

async def get_in_progress_orders() -> List[Dict[str, Any]]:
    """Get all in-progress orders"""
    orders_data = await get_orders()
    return [order for order in orders_data["orders"] if order["status"] == "in_progress"]

async def get_completed_orders() -> List[Dict[str, Any]]:
    """Get all completed orders"""
    orders_data = await get_orders()
    return [order for order in orders_data["orders"] if order["status"] == "completed"]

async def get_user_orders(user_id: int) -> List[Dict[str, Any]]:
    """Get all orders for a user"""
    orders_data = await get_orders()
    return [order for order in orders_data["orders"] if order["user_id"] == user_id]

async def get_operator_orders(operator_id: int) -> List[Dict[str, Any]]:
    """Get all orders for an operator"""
    orders_data = await get_orders()
    return [order for order in orders_data["orders"] 
            if order["operator_id"] == operator_id]

# Custom commands database functions
async def get_commands() -> List[Dict[str, Any]]:
    """Get all custom commands"""
    async with command_lock:
        try:
            with open(CUSTOM_COMMANDS_DB, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("commands", [])
        except Exception as e:
            logger.error(f"Error reading commands database: {str(e)}")
            return []

async def save_commands(commands: List[Dict[str, Any]]) -> None:
    """Save custom commands"""
    async with command_lock:
        try:
            with open(CUSTOM_COMMANDS_DB, 'w', encoding='utf-8') as f:
                json.dump({"commands": commands}, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving commands database: {str(e)}")

async def add_custom_command(command: str, response: str, buttons: Optional[List[str]] = None) -> None:
    """Add a custom command"""
    commands = await get_commands()
    
    # Check if command already exists
    for i, cmd in enumerate(commands):
        if cmd["command"] == command:
            # Update existing command
            commands[i] = {
                "command": command,
                "response": response,
                "buttons": buttons or []
            }
            await save_commands(commands)
            return
    
    # Add new command
    commands.append({
        "command": command,
        "response": response,
        "buttons": buttons or []
    })
    await save_commands(commands)

async def remove_custom_command(command: str) -> bool:
    """Remove a custom command"""
    commands = await get_commands()
    initial_length = len(commands)
    
    commands = [cmd for cmd in commands if cmd["command"] != command]
    
    if len(commands) < initial_length:
        await save_commands(commands)
        return True
    return False

async def get_custom_command(command: str) -> Optional[Dict[str, Any]]:
    """Get a custom command by name"""
    commands = await get_commands()
    for cmd in commands:
        if cmd["command"] == command:
            return cmd
    return None
