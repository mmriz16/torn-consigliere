"""
Item Cache System for Torn City.
Fetches all items from Torn API on startup and provides fuzzy matching.
"""
import logging
import requests
from typing import Optional
from difflib import get_close_matches

from config import TORN_API_KEY, TORN_API_BASE_URL

logger = logging.getLogger(__name__)

# Global item cache: { "item_name_lowercase": item_id }
ITEM_CACHE: dict[str, int] = {}
ITEM_NAMES: dict[int, str] = {}  # Reverse lookup: { item_id: "Item Name" }


def fetch_all_items() -> bool:
    """
    Fetch all items from Torn API and populate cache.
    Should be called on bot startup.
    
    Returns:
        bool: True if successful, False otherwise
    """
    global ITEM_CACHE, ITEM_NAMES
    
    url = f"{TORN_API_BASE_URL}/torn/?selections=items&key={TORN_API_KEY}"
    
    try:
        logger.info("Fetching item database from Torn API...")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            logger.error(f"Torn API error: {data['error']}")
            return False
        
        items = data.get("items", {})
        
        for item_id_str, item_data in items.items():
            item_id = int(item_id_str)
            item_name = item_data.get("name", "")
            
            if item_name:
                ITEM_CACHE[item_name.lower()] = item_id
                ITEM_NAMES[item_id] = item_name
        
        logger.info(f"Item cache loaded: {len(ITEM_CACHE)} items")
        return True
        
    except Exception as e:
        logger.error(f"Failed to fetch items: {e}")
        return False


def get_item_id(name: str) -> Optional[int]:
    """
    Get item ID from name using exact or fuzzy matching.
    
    Args:
        name: Item name (case-insensitive)
    
    Returns:
        int: Item ID if found, None otherwise
    """
    name_lower = name.lower().strip()
    
    # Exact match first
    if name_lower in ITEM_CACHE:
        return ITEM_CACHE[name_lower]
    
    # Fuzzy matching
    matches = get_close_matches(name_lower, ITEM_CACHE.keys(), n=1, cutoff=0.6)
    if matches:
        return ITEM_CACHE[matches[0]]
    
    return None


def get_item_name(item_id: int) -> Optional[str]:
    """
    Get item name from ID.
    
    Args:
        item_id: Torn item ID
    
    Returns:
        str: Item name if found, None otherwise
    """
    return ITEM_NAMES.get(item_id)


def search_items(query: str, limit: int = 5) -> list[tuple[str, int]]:
    """
    Search items by partial name match.
    
    Args:
        query: Search query
        limit: Max results
    
    Returns:
        list: List of (name, id) tuples
    """
    query_lower = query.lower()
    results = []
    
    for name, item_id in ITEM_CACHE.items():
        if query_lower in name:
            results.append((ITEM_NAMES.get(item_id, name), item_id))
            if len(results) >= limit:
                break
    
    return results


# Medical and Booster item categories for /stock
# Expanded keywords to catch more items
MEDICAL_KEYWORDS = [
    "first aid", "morphine", "blood bag", "medical", "painkiller",
    "vicodin", "codeine", "aspirin", "bandage", "gauze", "stitches"
]
BOOSTER_KEYWORDS = [
    "energy", "candy", "lollipop", "chocolate", "dvd", "coupon", 
    "munster", "red cow", "can of", "feathery", "fhc", "hotel",
    "energy drink", "e-dvd", "christmas", "easter", "hash brownies"
]

# Drug keywords for separate display
DRUG_KEYWORDS = [
    "xanax", "ecstasy", "vicodin", "shrooms", "speed", "pcp", 
    "lsd", "ketamine", "cannabis", "opium", "love juice"
]
