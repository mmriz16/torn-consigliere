"""
Property & Real-Estate Data for Bot Consigliere v4.3
Contains property types, happiness values, and market helpers.
"""

# =============================================================================
# PROPERTY TYPES (ordered by tier)
# =============================================================================

PROPERTY_TYPES = {
    1: {"name": "Trailer", "emoji": "🏕️", "happy": 25, "upkeep": 5},
    2: {"name": "Apartment", "emoji": "🏢", "happy": 50, "upkeep": 10},
    3: {"name": "Semi-Detached", "emoji": "🏘️", "happy": 75, "upkeep": 15},
    4: {"name": "Detached House", "emoji": "🏠", "happy": 100, "upkeep": 25},
    5: {"name": "Beach House", "emoji": "🏖️", "happy": 150, "upkeep": 50},
    6: {"name": "Chalet", "emoji": "🛖", "happy": 200, "upkeep": 75},
    7: {"name": "Villa", "emoji": "🏡", "happy": 350, "upkeep": 100},
    8: {"name": "Penthouse", "emoji": "🌆", "happy": 500, "upkeep": 150},
    9: {"name": "Mansion", "emoji": "🏛️", "happy": 1000, "upkeep": 250},
    10: {"name": "Ranch", "emoji": "🌾", "happy": 1500, "upkeep": 500},
    11: {"name": "Palace", "emoji": "👑", "happy": 2500, "upkeep": 750},
    12: {"name": "Castle", "emoji": "🏰", "happy": 3500, "upkeep": 1000},
    13: {"name": "Private Island", "emoji": "🏝️", "happy": 4225, "upkeep": 1500},
}

# Property type name to ID mapping (for API compatibility)
PROPERTY_NAME_TO_ID = {
    "trailer": 1,
    "apartment": 2,
    "semi-detached house": 3,
    "detached house": 4,
    "beach house": 5,
    "chalet": 6,
    "villa": 7,
    "penthouse": 8,
    "mansion": 9,
    "ranch": 10,
    "palace": 11,
    "castle": 12,
    "private island": 13,
}


def get_property_type_buttons(mode: str = "rent") -> list:
    """
    Generate inline keyboard button data for property type selection.
    Groups into 3 rows for better display.
    
    Args:
        mode: "rent" or "sell"
    
    Returns:
        list of button rows: [[{text, callback_data}, ...], ...]
    """
    buttons = []
    current_row = []
    
    for type_id, prop in PROPERTY_TYPES.items():
        btn = {
            "text": f"{prop['emoji']} {prop['name'][:8]}",
            "callback_data": f"prop_{mode}_{type_id}"
        }
        current_row.append(btn)
        
        # 5 buttons per row for first 2 rows, 3 for last row
        if len(current_row) >= 5:
            buttons.append(current_row)
            current_row = []
    
    # Add remaining buttons
    if current_row:
        buttons.append(current_row)
    
    return buttons


def format_rental_listings(listings: list, user_cash: int = 0) -> str:
    """
    Format rental listings as table text.
    Sorted by cost ascending. Shows 🔥 for best deals, ⚠️ if over budget.
    
    Args:
        listings: List of rental property dicts from API
        user_cash: User's current cash for budget warning
    
    Returns:
        Formatted text string
    """
    if not listings:
        return "📭 Tidak ada listing tersedia saat ini."
    
    # Sort by cost ascending
    sorted_listings = sorted(listings, key=lambda x: x.get('cost', 0))
    
    # Calculate average for best deal indicator
    avg_cost = sum(l.get('cost', 0) for l in sorted_listings) / len(sorted_listings)
    
    lines = []
    for i, listing in enumerate(sorted_listings[:10], 1):  # Max 10 listings
        owner = listing.get('owner', {}).get('name', 'Unknown')[:12]
        happy = listing.get('happy', 0)
        cost = listing.get('cost', 0)
        days = listing.get('days_left', 0)
        cost_per_day = cost // days if days > 0 else cost
        
        # Indicators
        deal_indicator = "🔥" if cost < avg_cost * 0.8 else ""
        budget_indicator = "⚠️" if user_cash > 0 and cost > user_cash else ""
        
        lines.append(
            f"{i}. {deal_indicator}{budget_indicator}"
            f"<code>${cost:>10,}</code> | "
            f"😊{happy:>4} | "
            f"{days}d | "
            f"@{owner}"
        )
    
    return "\n".join(lines)


def format_property_stats(property_data: dict) -> str:
    """
    Format current property information.
    """
    if not property_data:
        return "🏠 Bos belum memiliki properti."
    
    prop_type = property_data.get('property_type', 0)
    prop_info = PROPERTY_TYPES.get(prop_type, {})
    
    return (
        f"🏠 <b>MY PROPERTY</b>\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📍 <b>Tipe:</b> {prop_info.get('emoji', '🏠')} {prop_info.get('name', 'Unknown')}\n"
        f"😊 <b>Happy:</b> +{property_data.get('happy', 0):,}\n"
        f"💰 <b>Upkeep:</b> ${property_data.get('upkeep', 0):,}/day\n"
    )
