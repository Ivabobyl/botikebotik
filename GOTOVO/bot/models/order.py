from typing import Dict, List, Any, Optional

# Order model structure (for reference)
ORDER_MODEL = {
    "id": 0,                    # Order ID (internal)
    "order_number": "",         # Human-readable order number (Z00001)
    "user_id": 0,               # User who created the order
    "username": "",             # Username for reference
    "order_type": "buy",        # "buy" or "sell"
    "amount": 0.0,              # Order amount in rubles
    "status": "active",         # "active", "in_progress", "completed"
    "created_at": "",           # ISO format datetime
    "updated_at": "",           # ISO format datetime
    "operator_id": None,        # Operator who took the order
    "operator_username": None,  # Operator username for reference
    "completed_at": None,       # When order was completed
    "spread": None              # Profit margin on completed order
}

class OrderStatus:
    """Order status constants"""
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

class OrderType:
    """Order type constants"""
    BUY = "buy"
    SELL = "sell"

def create_order_dict(
    order_id: int,
    order_number: str,
    user_id: int,
    username: str,
    order_type: str,
    amount: float
) -> Dict[str, Any]:
    """Create a new order dictionary"""
    import datetime
    now = datetime.datetime.now().isoformat()
    
    return {
        "id": order_id,
        "order_number": order_number,
        "user_id": user_id,
        "username": username,
        "order_type": order_type,
        "amount": amount,
        "status": OrderStatus.ACTIVE,
        "created_at": now,
        "updated_at": now,
        "operator_id": None,
        "operator_username": None,
        "completed_at": None,
        "spread": None
    }

def assign_order_to_operator(
    order: Dict[str, Any],
    operator_id: int,
    operator_username: str
) -> Dict[str, Any]:
    """Assign order to an operator"""
    import datetime
    
    order["status"] = OrderStatus.IN_PROGRESS
    order["operator_id"] = operator_id
    order["operator_username"] = operator_username
    order["updated_at"] = datetime.datetime.now().isoformat()
    
    return order

def complete_order(
    order: Dict[str, Any],
    spread: float
) -> Dict[str, Any]:
    """Mark order as completed"""
    import datetime
    
    order["status"] = OrderStatus.COMPLETED
    order["completed_at"] = datetime.datetime.now().isoformat()
    order["updated_at"] = datetime.datetime.now().isoformat()
    order["spread"] = spread
    
    return order
