"""
Torn API Client for fetching game data.
Endpoints: basic, bars, cooldowns, inventory, market, travel
"""
import logging
import requests
from typing import Optional
from config import TORN_API_KEY, TORN_API_BASE_URL

logger = logging.getLogger(__name__)


class TornAPIError(Exception):
    """Custom exception for Torn API errors."""
    pass


def fetch_user_data(selections: str = "basic,bars,cooldowns") -> dict:
    """
    Fetch user data from Torn API.
    
    Args:
        selections: Comma-separated list of data selections (basic, bars, cooldowns, etc.)
    
    Returns:
        dict: API response data
    
    Raises:
        TornAPIError: If API call fails
    """
    url = f"{TORN_API_BASE_URL}/user/?selections={selections}&key={TORN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Check for API error
        if "error" in data:
            raise TornAPIError(f"Torn API Error: {data['error'].get('error', 'Unknown error')}")
        
        return data
    except requests.RequestException as e:
        raise TornAPIError(f"Failed to fetch data from Torn API: {str(e)}")


def fetch_market_data_v2(item_id: int) -> dict:
    """
    Fetch market data for a specific item using API v2.
    
    Args:
        item_id: Torn item ID
    
    Returns:
        dict: Market data with itemmarket listings
    """
    # API v2 endpoint for itemmarket
    url = f"https://api.torn.com/v2/market/{item_id}/itemmarket?key={TORN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise TornAPIError(f"Torn API Error: {data['error'].get('error', 'Unknown error')}")
        
        return data
    except requests.RequestException as e:
        raise TornAPIError(f"Failed to fetch market data: {str(e)}")


def fetch_bazaar_data_v1(item_id: int) -> dict:
    """
    Fetch bazaar data for a specific item using API v1.
    API v1 provides direct price listings, unlike v2.
    
    Args:
        item_id: Torn item ID
    
    Returns:
        dict: { "bazaar": [ { "cost": int, "quantity": int }, ... ] }
    """
    # API v1 endpoint for bazaar - provides actual prices
    url = f"{TORN_API_BASE_URL}/market/{item_id}?selections=bazaar&key={TORN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise TornAPIError(f"Torn API Error: {data['error'].get('error', 'Unknown error')}")
        
        return data
    except requests.RequestException as e:
        raise TornAPIError(f"Failed to fetch bazaar data: {str(e)}")







def get_bars() -> dict:
    """
    Get Energy, Nerve, Happy, and Life bars.
    
    Returns:
        dict: {
            "energy": {"current": int, "maximum": int, "fulltime": int},
            "nerve": {"current": int, "maximum": int, "fulltime": int},
            "happy": {"current": int, "maximum": int, "fulltime": int},
            "life": {"current": int, "maximum": int, "fulltime": int}
        }
    """
    data = fetch_user_data("bars")
    return {
        "energy": data.get("energy", {}),
        "nerve": data.get("nerve", {}),
        "happy": data.get("happy", {}),
        "life": data.get("life", {})
    }


def get_cooldowns() -> dict:
    """
    Get Drug and Medical cooldowns.
    
    Returns:
        dict: {
            "drug": int (seconds remaining),
            "medical": int (seconds remaining),
            "booster": int (seconds remaining)
        }
    """
    data = fetch_user_data("cooldowns")
    cooldowns = data.get("cooldowns", {})
    return {
        "drug": cooldowns.get("drug", 0),
        "medical": cooldowns.get("medical", 0),
        "booster": cooldowns.get("booster", 0)
    }


def get_basic_info() -> dict:
    """
    Get basic user info including status.
    
    Returns:
        dict: Basic user information
    """
    return fetch_user_data("basic")


def get_full_stats() -> dict:
    """
    Get comprehensive stats for /stats command.
    
    Returns:
        dict: Combined basic, bars, and cooldowns data
    """
    data = fetch_user_data("basic,bars,cooldowns,money")
    return {
        "name": data.get("name", "Unknown"),
        "level": data.get("level", 0),
        "status": data.get("status", {}).get("description", "Unknown"),
        "energy": data.get("energy", {}),
        "nerve": data.get("nerve", {}),
        "happy": data.get("happy", {}),
        "life": data.get("life", {}),
        "money_onhand": data.get("money_onhand", 0),
        "cooldowns": data.get("cooldowns", {})
    }


def get_inventory() -> list:
    """
    Get user inventory.
    
    Returns:
        list: List of inventory items with id, name, quantity
    """
    data = fetch_user_data("inventory")
    inventory_raw = data.get("inventory", {})
    
    # Torn API returns dict with item_id as key, convert to list
    if isinstance(inventory_raw, dict):
        inventory_list = []
        for item_id, item_data in inventory_raw.items():
            if isinstance(item_data, dict):
                item_data["ID"] = int(item_id)
                inventory_list.append(item_data)
        return inventory_list
    elif isinstance(inventory_raw, list):
        return inventory_raw
    else:
        return []


def get_item_details(item_id: int) -> dict:
    """
    Get item details from Torn API (name, type, description, effect).
    
    Args:
        item_id: Torn item ID
    
    Returns:
        dict: {
            "name": str,
            "type": str,
            "description": str,
            "effect": str,
            "image_url": str
        }
    """
    url = f"{TORN_API_BASE_URL}/torn/{item_id}?selections=items&key={TORN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise TornAPIError(f"Torn API Error: {data['error'].get('error', 'Unknown')}")
        
        items = data.get("items", {})
        item = items.get(str(item_id), {})
        
        return {
            "name": item.get("name", "Unknown"),
            "type": item.get("type", "Unknown"),
            "description": item.get("description", ""),
            "effect": item.get("effect", ""),
            "image_url": f"https://www.torn.com/images/items/{item_id}/large.png"
        }
        
    except requests.RequestException as e:
        raise TornAPIError(f"Failed to fetch item details: {str(e)}")



def get_travel_status() -> dict:
    """
    Get travel status.
    
    Returns:
        dict: {
            "destination": str,
            "time_left": int (seconds),
            "departed": int (timestamp),
            "timestamp": int (arrival timestamp)
        }
    """
    data = fetch_user_data("travel")
    travel = data.get("travel", {})
    return {
        "destination": travel.get("destination", "Torn"),
        "time_left": travel.get("time_left", 0),
        "departed": travel.get("departed", 0),
        "timestamp": travel.get("timestamp", 0)
    }


def get_market_prices(item_id: int) -> dict:
    """
    Get market prices for an item using API v2.
    
    API v2 Response format:
    - itemmarket: { item: {...}, listings: [{price, amount}, ...] }
    - bazaar: { listings: [{price, quantity}, ...] }
    
    Args:
        item_id: Torn item ID
    
    Returns:
        dict: {
            "bazaar_lowest": int or None,
            "bazaar_stock": int,
            "market_lowest": int or None,
            "market_stock": int
        }
    """
    import logging
    logger = logging.getLogger(__name__)
    
    bazaar_lowest = None
    bazaar_stock = 0
    market_lowest = None
    market_stock = 0
    
    # Fetch bazaar data (v1) - format: { bazaar: [ { cost, quantity }, ... ] }
    try:
        bazaar_data = fetch_bazaar_data_v1(item_id)
        bazaar_listings = bazaar_data.get("bazaar", [])
        
        # v1 format: bazaar is a list of { cost, quantity }
        if isinstance(bazaar_listings, list) and bazaar_listings:
            prices = []
            quantities = []
            for listing in bazaar_listings:
                if isinstance(listing, dict):
                    price = listing.get("cost")
                    qty = listing.get("quantity", 1)
                    if price:
                        prices.append(price)
                        quantities.append(qty)
            if prices:
                bazaar_lowest = min(prices)
                bazaar_stock = sum(quantities)
    except TornAPIError as e:
        logger.debug(f"Bazaar fetch failed: {e}")
    except Exception as e:
        logger.debug(f"Bazaar parse error: {e}")
    
    # Fetch item market data (v2) - format: { itemmarket: { item: {...}, listings: [...] } }
    try:
        market_data = fetch_market_data_v2(item_id)
        market_obj = market_data.get("itemmarket", {})
        
        # v2 format: itemmarket.listings
        if isinstance(market_obj, dict):
            market_listings = market_obj.get("listings", [])
        else:
            market_listings = []
        
        if isinstance(market_listings, list) and market_listings:
            prices = []
            quantities = []
            for listing in market_listings:
                if isinstance(listing, dict):
                    price = listing.get("price")
                    qty = listing.get("amount") or listing.get("quantity") or 1
                    if price:
                        prices.append(price)
                        quantities.append(qty)
            if prices:
                market_lowest = min(prices)
                market_stock = sum(quantities)
    except TornAPIError as e:
        logger.debug(f"Market fetch failed: {e}")
    except Exception as e:
        logger.debug(f"Market parse error: {e}")
    
    return {
        "bazaar_lowest": bazaar_lowest,
        "bazaar_stock": bazaar_stock,
        "market_lowest": market_lowest,
        "market_stock": market_stock
    }



def get_nerve_for_crime() -> dict:
    """
    Get nerve and level data for /crime command.
    
    Returns:
        dict: { "nerve_current", "nerve_max", "level" }
    """
    data = fetch_user_data("basic,bars")
    nerve = data.get("nerve", {})
    return {
        "nerve_current": nerve.get("current", 0),
        "nerve_max": nerve.get("maximum", 0),
        "level": data.get("level", 0)
    }


def get_education_status() -> dict:
    """
    Get current education status.
    
    Returns:
        dict: {
            "current_course": str,
            "seconds_remaining": int,
            "completed": int (number of courses completed)
        }
    """
    data = fetch_user_data("education")
    education = data.get("education", {})
    current = education.get("current", {})
    
    return {
        "current_course": current.get("name", ""),
        "seconds_remaining": current.get("timeleft", 0),
        "completed": len(education.get("completed", []))
    }


def get_extended_stats() -> dict:
    """
    Get extended stats including networth and perks for /stats command.
    
    Returns:
        dict: Combined basic, bars, cooldowns, networth, and perks data
    """
    data = fetch_user_data("basic,bars,cooldowns,money,networth,perks")
    
    # Extract networth
    networth = data.get("networth", {})
    total_networth = (
        networth.get("pending", 0) +
        networth.get("wallet", 0) +
        networth.get("bank", 0) +
        networth.get("points", 0) +
        networth.get("cayman", 0) +
        networth.get("vault", 0) +
        networth.get("piggybank", 0) +
        networth.get("items", 0) +
        networth.get("displaycase", 0) +
        networth.get("bazaar", 0) +
        networth.get("properties", 0) +
        networth.get("stockmarket", 0) +
        networth.get("auctionhouse", 0) +
        networth.get("company", 0) +
        networth.get("bookie", 0) +
        networth.get("loan", 0) +
        networth.get("unpaidfees", 0)
    )
    
    # Extract perks
    perks = []
    for perk_type in ["job_perks", "property_perks", "stock_perks", "merit_perks", 
                       "education_perks", "enhancer_perks", "company_perks", "faction_perks", "book_perks"]:
        perk_list = data.get(perk_type, [])
        if perk_list:
            perks.extend(perk_list[:3])  # Limit to 3 per category
    
    return {
        "name": data.get("name", "Unknown"),
        "level": data.get("level", 0),
        "status": data.get("status", {}).get("description", "Unknown"),
        "energy": data.get("energy", {}),
        "nerve": data.get("nerve", {}),
        "happy": data.get("happy", {}),
        "life": data.get("life", {}),
        "money_onhand": data.get("money_onhand", 0),
        "cooldowns": data.get("cooldowns", {}),
        "total_networth": total_networth,
        "networth_breakdown": networth,
        "perks": perks[:10]  # Limit total perks shown
    }


def get_monitor_data() -> dict:
    """
    Get all data needed for background monitoring in one API call (batching).
    
    Includes: basic, bars, cooldowns, travel, education, events, messages
    
    Returns:
        dict: Combined monitoring data
    """
    return fetch_user_data("basic,bars,cooldowns,travel,education,events,messages")


def get_messages() -> list:
    """
    Get user inbox messages for monitoring.
    
    Note: Requires FULL ACCESS API key.
    
    Returns:
        list: List of messages sorted by timestamp (newest first)
               Each message: { "id": str, "name": str, "title": str, "text": str, "timestamp": int }
    """
    data = fetch_user_data("messages")
    messages_raw = data.get("messages", {})
    
    # Messages come as dict with message_id as key
    if isinstance(messages_raw, dict):
        messages_list = []
        for msg_id, msg_data in messages_raw.items():
            if isinstance(msg_data, dict):
                messages_list.append({
                    "id": str(msg_id),
                    "name": msg_data.get("name", "Unknown"),
                    "title": msg_data.get("title", "No Title"),
                    "text": msg_data.get("text", ""),
                    "timestamp": msg_data.get("timestamp", 0),
                    "read": msg_data.get("read", 0),
                    "seen": msg_data.get("seen", 0)
                })
        # Sort by timestamp descending (newest first)
        messages_list.sort(key=lambda x: x["timestamp"], reverse=True)
        return messages_list
    
    return []



def get_events() -> list:
    """
    Get user events for monitoring.
    
    Returns:
        list: List of events sorted by timestamp (newest first)
               Each event: { "id": str, "event": str, "timestamp": int }
    """
    data = fetch_user_data("events")
    events_raw = data.get("events", {})
    
    # Events come as dict with event_id as key (can be string or int)
    if isinstance(events_raw, dict):
        events_list = []
        for event_id, event_data in events_raw.items():
            if isinstance(event_data, dict):
                events_list.append({
                    "id": str(event_id),  # Keep as string - can be hash or number
                    "event": event_data.get("event", ""),
                    "timestamp": event_data.get("timestamp", 0)
                })
        # Sort by timestamp descending (newest first)
        events_list.sort(key=lambda x: x["timestamp"], reverse=True)
        return events_list
    
    return []



def get_company_data() -> dict:
    """
    Get company data. tries 'company' endpoint first (Director), 
    then fallback to 'user' endpoint with 'job' selection (Employee).
    
    Returns:
        dict: {
            "name": str,
            "position": str,
            "days_in_company": int,
            "stock": list (Directory only),
            "employees": list (Director only),
            "daily_income": int (Employee only),
            "efficiency": int (Employee only),
            "is_director": bool
        }
    """
    # 1. Try Company Endpoint (Director View)
    try:
        url = f"{TORN_API_BASE_URL}/company/?selections=profile,stock,employees&key={TORN_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if "error" not in data:
            company = data.get("company", {})
            return {
                "name": company.get("name", "Unknown Company"),
                "position": "Director",
                "days_in_company": 0, # Not available in company endpoint
                "stock": data.get("company_stock", []),
                "employees": data.get("company_employees", {}),
                "daily_income": company.get("daily_income", 0),
                "efficiency": 100,
                "is_director": True
            }
            
    except Exception:
        pass # Fallback to user endpoint

    # 2. Fallback to User Endpoint (Employee View)
    try:
        # Use 'profile' which is available in v1 and contains job info
        url = f"{TORN_API_BASE_URL}/user/?selections=profile&key={TORN_API_KEY}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if "error" not in data:
            job = data.get("job", {})
            return {
                "name": job.get("company_name", "Unknown"),
                "position": job.get("position", "Employee"),
                "days_in_company": job.get("days_in_company", 0),
                "stock": [],
                "employees": {}, 
                "daily_income": job.get("company_type", {}).get("daily_income", 0) if isinstance(job.get("company_type"), dict) else 0, 
                "efficiency": job.get("efficiency", 0),
                "is_director": False
            }
            
    except Exception as e:
        logger.error(f"Failed to fetch job data from profile: {e}")

    return {"error": "Gagal mengambil data company. Pastikan API Key benar."}


def get_company_stock() -> list:
    """
    Get company stock items with low quantity.
    
    Returns:
        list: Items with quantity < 100
    """
    data = get_company_data()
    
    if data.get("error"):
        return []
    
    stock = data.get("stock", [])
    low_stock = []
    
    # Filter low stock items (< 100)
    for item in stock:
        if isinstance(item, dict):
            qty = item.get("in_stock", 0)
            if qty < 100:
                low_stock.append({
                    "name": item.get("name", "Unknown"),
                    "quantity": qty,
                    "sold": item.get("sold_amount", 0)
                })
    
    return low_stock


def get_inactive_employees(threshold_days: int = 3) -> list:
    """
    Get employees who haven't been active for X days.
    
    Args:
        threshold_days: Days of inactivity threshold (default 3)
    
    Returns:
        list: Inactive employees with name and last_action
    """
    import time
    
    data = get_company_data()
    
    if data.get("error"):
        return []
    
    employees_raw = data.get("employees", {})
    threshold_seconds = threshold_days * 24 * 60 * 60
    current_time = int(time.time())
    inactive = []
    
    if isinstance(employees_raw, dict):
        for emp_id, emp_data in employees_raw.items():
            if isinstance(emp_data, dict):
                last_action = emp_data.get("last_action", {})
                if isinstance(last_action, dict):
                    last_timestamp = last_action.get("timestamp", 0)
                else:
                    last_timestamp = 0
                
                if last_timestamp > 0:
                    days_inactive = (current_time - last_timestamp) / 86400
                    if days_inactive >= threshold_days:
                        inactive.append({
                            "name": emp_data.get("name", "Unknown"),
                            "days_inactive": int(days_inactive),
                            "position": emp_data.get("position", "Employee")
                        })
    
    return inactive


# =============================================================================
# MULTI-MENU NAVIGATION API FUNCTIONS (V2.0)
# =============================================================================

def get_menu_data() -> dict:
    """
    Get all data needed for multi-menu navigation in one API call (batching).
    This optimizes API usage by fetching all selections at once.
    
    Returns:
        dict: Comprehensive data for all menus including:
            - basic, bars, cooldowns (General Stats)
            - money, networth (Financial)
            - battlestats, gym (GYM Stats)
            - workstats, profile (Job & Work)
            - properties (Property)
            - crimes (Criminal)
            - events, notifications (Events)
    """
    selections = (
        "basic,bars,cooldowns,money,networth,icons,education,"
        "battlestats,workstats,profile,properties,"
        "criminalrecord,events,notifications,equipment,jobpoints,gym"
    )
    return fetch_user_data(selections)


def get_property_data() -> dict:
    """
    Get property data for Happy Jump planning.
    
    Returns:
        dict: {
            "properties": list of properties with name and happy bonus,
            "max_happy": int (maximum happy capacity from property)
        }
    """
    data = fetch_user_data("properties")
    properties_raw = data.get("properties", {})
    
    properties = []
    max_happy = 0
    
    if isinstance(properties_raw, dict):
        for prop_id, prop_data in properties_raw.items():
            if isinstance(prop_data, dict):
                name = prop_data.get("property_type", "Unknown")
                happy = prop_data.get("happy", 0)
                
                # Track max happy from property upgrades
                if happy > max_happy:
                    max_happy = happy
                
                properties.append({
                    "id": prop_id,
                    "name": name,
                    "happy": happy,
                    "upkeep": prop_data.get("upkeep", 0),
                    "staff": prop_data.get("staff", [])
                })
    
    return {
        "properties": properties,
        "max_happy": max_happy
    }


def get_equipment_data() -> dict:
    """
    Get equipped weapons and armor data.
    
    Note: Uses 'profile' selection which includes equipped items in v1 API.
    
    Returns:
        dict: {
            "primary_weapon": str,
            "secondary_weapon": str,
            "melee_weapon": str,
            "temp_weapon": str,
            "armor": dict with head, body, legs, feet, etc.
        }
    """
    data = fetch_user_data("profile")
    
    # Extract equipped items from profile data
    equipped = data.get("equipped", {})
    
    return {
        "primary_weapon": equipped.get("primary", "None"),
        "secondary_weapon": equipped.get("secondary", "None"),
        "melee_weapon": equipped.get("melee", "None"),
        "temp_weapon": equipped.get("temporary", "None"),
        "armor": {
            "helmet": equipped.get("helmet", "None"),
            "body": equipped.get("body_armor", "None"),
            "pants": equipped.get("pants", "None"),
            "boots": equipped.get("boots", "None"),
            "gloves": equipped.get("gloves", "None")
        }
    }


def get_criminal_data() -> dict:
    """
    Get criminal activity data for NNB optimization.
    
    Returns:
        dict: {
            "nerve_current": int,
            "nerve_max": int,
            "crimes": dict with crime statistics
        }
    """
    data = fetch_user_data("basic,bars,crimes")
    
    nerve = data.get("nerve", {})
    crimes = data.get("criminalrecord", {})
    
    return {
        "nerve_current": nerve.get("current", 0),
        "nerve_max": nerve.get("maximum", 0),
        "nerve_fulltime": nerve.get("fulltime", 0),
        "crimes": crimes
    }


def get_events_data(limit: int = 5) -> list:
    """
    Get recent events for Events menu.
    
    Args:
        limit: Maximum number of events to return (default 5)
    
    Returns:
        list: List of recent events sorted by timestamp (newest first)
    """
    data = fetch_user_data("events,notifications")
    events_raw = data.get("events", {})
    notifications_raw = data.get("notifications", {})
    
    events_list = []
    
    # Parse events
    if isinstance(events_raw, dict):
        for event_id, event_data in events_raw.items():
            if isinstance(event_data, dict):
                events_list.append({
                    "id": str(event_id),
                    "type": "event",
                    "text": event_data.get("event", ""),
                    "timestamp": event_data.get("timestamp", 0)
                })
    
    # Parse notifications
    if isinstance(notifications_raw, dict):
        for notif_id, notif_data in notifications_raw.items():
            if isinstance(notif_data, dict):
                events_list.append({
                    "id": str(notif_id),
                    "type": "notification",
                    "text": notif_data.get("text", ""),
                    "timestamp": notif_data.get("timestamp", 0)
                })
    
    # Sort by timestamp descending and limit
    events_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return events_list[:limit]

