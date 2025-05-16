from typing import Dict, List, Any, Optional

# Rate model for reference
RATES_MODEL = {
    "ltc_usd_buy": 70.0,    # Price to buy LTC in USD
    "ltc_usd_sell": 68.0,   # Price to sell LTC in USD
    "usd_rub_buy": 90.0,    # USD to RUB rate for buying
    "usd_rub_sell": 88.0,   # USD to RUB rate for selling
}

def calculate_ltc_price_in_rubles(
    ltc_amount: float,
    is_buy: bool,
    rates: Dict[str, float]
) -> float:
    """
    Calculate price of LTC in rubles
    
    Args:
        ltc_amount: Amount of LTC
        is_buy: True if buying LTC, False if selling
        rates: Current exchange rates
        
    Returns:
        Price in rubles
    """
    if is_buy:
        # Buying LTC: Use LTC buy price and USD buy rate
        return ltc_amount * rates["ltc_usd_buy"] * rates["usd_rub_buy"]
    else:
        # Selling LTC: Use LTC sell price and USD sell rate
        return ltc_amount * rates["ltc_usd_sell"] * rates["usd_rub_sell"]

def calculate_ltc_amount_from_rubles(
    rub_amount: float,
    is_buy: bool,
    rates: Dict[str, float]
) -> float:
    """
    Calculate how much LTC can be bought/sold for a given amount of rubles
    
    Args:
        rub_amount: Amount in rubles
        is_buy: True if buying LTC, False if selling
        rates: Current exchange rates
        
    Returns:
        Amount of LTC
    """
    if is_buy:
        # Buying LTC
        return rub_amount / (rates["ltc_usd_buy"] * rates["usd_rub_buy"])
    else:
        # Selling LTC
        return rub_amount / (rates["ltc_usd_sell"] * rates["usd_rub_sell"])

def calculate_spread(
    rub_amount: float,
    is_buy: bool,
    rates: Dict[str, float]
) -> float:
    """
    Calculate spread (profit) for a transaction
    
    Args:
        rub_amount: Amount in rubles
        is_buy: True if buying LTC, False if selling
        rates: Current exchange rates
        
    Returns:
        Spread amount in rubles
    """
    # Calculate LTC amount
    ltc_amount = calculate_ltc_amount_from_rubles(rub_amount, is_buy, rates)
    
    # Calculate price difference between buy and sell rates
    if is_buy:
        # When user buys LTC, we buy at sell rate and sell at buy rate
        buy_price = ltc_amount * rates["ltc_usd_sell"] * rates["usd_rub_sell"]
        sell_price = ltc_amount * rates["ltc_usd_buy"] * rates["usd_rub_buy"]
    else:
        # When user sells LTC, we buy at sell rate and sell at buy rate
        buy_price = ltc_amount * rates["ltc_usd_buy"] * rates["usd_rub_buy"]
        sell_price = ltc_amount * rates["ltc_usd_sell"] * rates["usd_rub_sell"]
    
    # The spread is the difference
    return abs(sell_price - buy_price)
