"""
Travel & Smuggling Data for Bot Consigliere v4.2
Contains item mappings, country info, and profit calculation helpers.
"""

# =============================================================================
# COUNTRY DATA
# =============================================================================

COUNTRIES = {
    "mexico": {
        "name": "Mexico",
        "flag": "🇲🇽",
        "flight_min": 26,
        "items": ["jaguar_plushie", "dahlia"]
    },
    "cayman": {
        "name": "Cayman Islands",
        "flag": "🇰🇾",
        "flight_min": 35,
        "items": ["stingray_plushie", "banana_orchid"]
    },
    "canada": {
        "name": "Canada",
        "flag": "🇨🇦",
        "flight_min": 41,
        "items": ["wolverine_plushie", "crocus"]
    },
    "hawaii": {
        "name": "Hawaii",
        "flag": "🌺",
        "flight_min": 134,
        "items": ["orchid"]
    },
    "uk": {
        "name": "United Kingdom",
        "flag": "🇬🇧",
        "flight_min": 159,
        "items": ["nessie_plushie", "red_fox_plushie", "heather"]
    },
    "argentina": {
        "name": "Argentina",
        "flag": "🇦🇷",
        "flight_min": 167,
        "items": ["monkey_plushie", "ceibo_flower"]
    },
    "switzerland": {
        "name": "Switzerland",
        "flag": "🇨🇭",
        "flight_min": 175,
        "items": ["chamois_plushie", "edelweiss"]
    },
    "japan": {
        "name": "Japan",
        "flag": "🇯🇵",
        "flight_min": 225,
        "items": ["cherry_blossom"]
    },
    "china": {
        "name": "China",
        "flag": "🇨🇳",
        "flight_min": 242,
        "items": ["panda_plushie", "peony"]
    },
    "uae": {
        "name": "UAE",
        "flag": "🇦🇪",
        "flight_min": 271,
        "items": ["camel_plushie", "tribulus"]
    },
    "south_africa": {
        "name": "South Africa",
        "flag": "🇿🇦",
        "flight_min": 297,
        "items": ["lion_plushie", "african_violet"]
    },
}

# =============================================================================
# TRAVEL ITEMS - ID, Name, Country, Buy Price, Market Value (estimated)
# =============================================================================

TRAVEL_ITEMS = {
    # === PLUSHIES ===
    # UAE
    273: {"name": "Camel Plushie", "key": "camel_plushie", "country": "uae", "buy": 14000, "market_est": 78000},
    # China
    258: {"name": "Panda Plushie", "key": "panda_plushie", "country": "china", "buy": 400, "market_est": 58000},
    # UK
    261: {"name": "Nessie Plushie", "key": "nessie_plushie", "country": "uk", "buy": 200, "market_est": 29000},
    266: {"name": "Red Fox Plushie", "key": "red_fox_plushie", "country": "uk", "buy": 1000, "market_est": 31000},
    # South Africa
    268: {"name": "Lion Plushie", "key": "lion_plushie", "country": "south_africa", "buy": 400, "market_est": 63000},
    # Argentina
    269: {"name": "Monkey Plushie", "key": "monkey_plushie", "country": "argentina", "buy": 400, "market_est": 30000},
    # Switzerland
    274: {"name": "Chamois Plushie", "key": "chamois_plushie", "country": "switzerland", "buy": 400, "market_est": 8500},
    # Mexico
    281: {"name": "Jaguar Plushie", "key": "jaguar_plushie", "country": "mexico", "buy": 10000, "market_est": 14000},
    # Cayman
    384: {"name": "Stingray Plushie", "key": "stingray_plushie", "country": "cayman", "buy": 400, "market_est": 6400},
    # Canada
    618: {"name": "Wolverine Plushie", "key": "wolverine_plushie", "country": "canada", "buy": 30, "market_est": 6000},
    
    # === FLOWERS ===
    # South Africa
    260: {"name": "African Violet", "key": "african_violet", "country": "south_africa", "buy": 2000, "market_est": 63000},
    # Cayman
    264: {"name": "Banana Orchid", "key": "banana_orchid", "country": "cayman", "buy": 4000, "market_est": 8800},
    # Argentina
    272: {"name": "Ceibo Flower", "key": "ceibo_flower", "country": "argentina", "buy": 500, "market_est": 27000},
    # Japan
    263: {"name": "Cherry Blossom", "key": "cherry_blossom", "country": "japan", "buy": 500, "market_est": 43000},
    # Canada
    617: {"name": "Crocus", "key": "crocus", "country": "canada", "buy": 600, "market_est": 3900},
    # Mexico
    282: {"name": "Dahlia", "key": "dahlia", "country": "mexico", "buy": 300, "market_est": 1200},
    # Switzerland
    277: {"name": "Edelweiss", "key": "edelweiss", "country": "switzerland", "buy": 900, "market_est": 3200},
    # UK
    271: {"name": "Heather", "key": "heather", "country": "uk", "buy": 5000, "market_est": 33000},
    # Hawaii
    385: {"name": "Orchid", "key": "orchid", "country": "hawaii", "buy": 700, "market_est": 12800},
    # China
    276: {"name": "Peony", "key": "peony", "country": "china", "buy": 5000, "market_est": 62000},
    # UAE
    262: {"name": "Tribulus Omanense", "key": "tribulus", "country": "uae", "buy": 6000, "market_est": 66000},
}


def get_carry_capacity(level: int, has_suitcase: bool = False) -> int:
    """
    Calculate carry capacity based on level.
    Base: 5 items, +1 per 5 levels, +10 if Large Suitcase.
    """
    base = 5 + (level // 5)
    return base + (10 if has_suitcase else 0)


def calculate_profit(item_id: int, market_price: int, quantity: int = 1) -> dict:
    """
    Calculate profit for a travel item.
    
    Returns:
        dict: {profit_per_item, total_profit, buy_price, market_price}
    """
    item = TRAVEL_ITEMS.get(item_id, {})
    buy_price = item.get("buy", 0)
    profit_per = market_price - buy_price
    
    return {
        "item_name": item.get("name", "Unknown"),
        "country": item.get("country", "unknown"),
        "buy_price": buy_price,
        "market_price": market_price,
        "profit_per": profit_per,
        "total_profit": profit_per * quantity
    }


def get_top_profitable_items(market_prices: dict = None, top_n: int = 5) -> list:
    """
    Get top N most profitable items based on profit margin.
    Uses estimated market prices if real prices not provided.
    
    Returns:
        list: [{item_id, name, country, profit, ...}, ...]
    """
    results = []
    
    for item_id, item in TRAVEL_ITEMS.items():
        # Use real market price if available, otherwise use estimate
        if market_prices and item_id in market_prices:
            market = market_prices[item_id]
        else:
            market = item.get("market_est", 0)
        
        profit = market - item["buy"]
        country_data = COUNTRIES.get(item["country"], {})
        
        results.append({
            "item_id": item_id,
            "name": item["name"],
            "country_key": item["country"],
            "country_name": country_data.get("name", item["country"]),
            "flag": country_data.get("flag", "🌍"),
            "flight_min": country_data.get("flight_min", 0),
            "buy_price": item["buy"],
            "market_price": market,
            "profit": profit,
            "profit_ratio": profit / item["buy"] if item["buy"] > 0 else 0
        })
    
    # Sort by profit descending
    results.sort(key=lambda x: x["profit"], reverse=True)
    
    return results[:top_n]
