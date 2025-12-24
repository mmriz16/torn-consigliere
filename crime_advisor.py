"""
Crime Advisor for Bot Consigliere v5.1
Calculates Effective Arsons (EA) and provides crime safety recommendations.
EA is a community metric to estimate hidden Crime Experience (CE).
"""

# EA Multipliers based on TornStats/community data
# Higher multiplier = more CE gained per crime
EA_MULTIPLIERS = {
    "selling_illegal_products": 0.05,  # Lowest CE
    "theft": 0.10,                     # Low CE
    "auto_theft": 0.25,                # Medium CE
    "drug_deals": 0.33,                # Medium CE
    "computer_crimes": 0.50,           # High CE
    "fraud_crimes": 0.66,              # High CE
    "murder": 0.80,                    # Very High CE
    "other": 0.15,                     # Mixed (includes arson, vandalism, etc)
}

# EA Milestones and Level Names
EA_LEVELS = [
    (0, "Novice", "🌱"),
    (50, "Amateur", "🔰"),
    (100, "Professional", "🦾"),
    (250, "Expert", "⚡"),
    (500, "Elite", "💎"),
    (1000, "Master", "👑"),
    (2500, "Legend", "🏆"),
]

# Crime safety thresholds (minimum EA to safely attempt)
CRIME_THRESHOLDS = {
    "selling_illegal_products": 0,    # Always safe
    "theft": 25,                       # Need some experience
    "auto_theft": 100,                 # Need Professional level
    "drug_deals": 250,                 # Need Expert level
    "computer_crimes": 500,            # Need Elite level
    "fraud_crimes": 750,               # Need high Elite
    "murder": 1000,                    # Need Master level
    "other": 50,                       # Varies
}

# Crime display names (Indonesian friendly)
CRIME_NAMES = {
    "selling_illegal_products": "Jual Produk Ilegal",
    "theft": "Pencurian",
    "auto_theft": "Pencurian Mobil (GTA)",
    "drug_deals": "Transaksi Narkoba",
    "computer_crimes": "Kejahatan Komputer",
    "fraud_crimes": "Penipuan",
    "murder": "Pembunuhan",
    "other": "Lainnya (Arson, dll)",
}


def calculate_ea(criminal_record: dict) -> float:
    """
    Calculate Effective Arsons (EA) from criminal record.
    
    Args:
        criminal_record: Dict from Torn API criminalrecord selection
        
    Returns:
        float: Total EA score
    """
    total_ea = 0.0
    
    for crime_type, multiplier in EA_MULTIPLIERS.items():
        crime_count = criminal_record.get(crime_type, 0)
        if crime_count is None:
            crime_count = 0
        total_ea += crime_count * multiplier
    
    return round(total_ea, 1)


def get_ea_level(ea: float) -> tuple:
    """
    Get current level based on EA score.
    
    Returns:
        tuple: (level_name, level_icon, next_milestone, next_level_name)
    """
    current_level = EA_LEVELS[0]
    next_level = EA_LEVELS[1] if len(EA_LEVELS) > 1 else None
    
    for i, (threshold, name, icon) in enumerate(EA_LEVELS):
        if ea >= threshold:
            current_level = (threshold, name, icon)
            if i + 1 < len(EA_LEVELS):
                next_level = EA_LEVELS[i + 1]
            else:
                next_level = None
    
    return {
        "name": current_level[1],
        "icon": current_level[2],
        "threshold": current_level[0],
        "next_threshold": next_level[0] if next_level else None,
        "next_name": next_level[1] if next_level else None,
    }


def get_crime_safety(ea: float, crime_type: str) -> dict:
    """
    Get safety status for a specific crime type.
    
    Returns:
        dict: {status: "safe"|"caution"|"danger", icon: str, message: str}
    """
    threshold = CRIME_THRESHOLDS.get(crime_type, 100)
    
    if ea >= threshold * 1.2:
        return {
            "status": "safe",
            "icon": "🟢",
            "message": "Very Safe"
        }
    elif ea >= threshold * 0.8:
        return {
            "status": "caution", 
            "icon": "🟡",
            "message": f"Caution (Need {threshold}+ EA)"
        }
    else:
        return {
            "status": "danger",
            "icon": "🔴",
            "message": f"Danger (Need {threshold}+ EA)"
        }


def get_all_crime_safety(ea: float) -> list:
    """
    Get safety status for all crime types, sorted by safety.
    
    Returns:
        list: List of dicts with crime info and safety status
    """
    results = []
    
    for crime_type in CRIME_THRESHOLDS.keys():
        safety = get_crime_safety(ea, crime_type)
        results.append({
            "type": crime_type,
            "name": CRIME_NAMES.get(crime_type, crime_type),
            "threshold": CRIME_THRESHOLDS.get(crime_type, 0),
            **safety
        })
    
    # Sort: safe first, then caution, then danger
    order = {"safe": 0, "caution": 1, "danger": 2}
    results.sort(key=lambda x: (order.get(x["status"], 3), x["threshold"]))
    
    return results


def format_progress_bar(current: float, target: float, width: int = 10) -> str:
    """Create visual progress bar."""
    if target <= 0:
        return "█" * width
    
    pct = min(current / target, 1.0)
    filled = int(pct * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def get_consigliere_tip(ea: float, level: dict) -> str:
    """Get personalized recommendation based on current EA."""
    if ea < 50:
        return "Fokus ke Selling Products & Theft dulu untuk bangun CE dengan aman!"
    elif ea < 100:
        return "Bagus! Terus lakukan Theft sampai EA 100+ sebelum coba Auto Theft."
    elif ea < 250:
        return "Kamu sudah Professional! Auto Theft sudah aman. Target 250 EA untuk Drug Deals."
    elif ea < 500:
        return "Expert level! Drug Deals sudah aman. Target 500 EA untuk Computer Crimes."
    elif ea < 1000:
        return "Elite! Computer Crimes sudah aman. Target 1000 EA untuk jadi Master!"
    else:
        return "Master Criminal! Semua kejahatan sudah aman untukmu. 👑"
