"""
Awards Analyzer for Merit Hunter v4.9
Calculates progress towards Torn medals/awards using scraped TornStats data.
Uses awards_reference.json database for accurate thresholds.
"""
import json
import os

# Load awards reference database
def load_awards_database():
    """Load awards reference data from JSON file."""
    db_path = os.path.join(os.path.dirname(__file__), "awards_reference.json")
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: awards_reference.json not found at {db_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing awards_reference.json: {e}")
        return {}

# Global database loaded once
AWARDS_DATABASE = load_awards_database()


def get_all_trackable_awards() -> list:
    """
    Get all awards from database that can be tracked via personalstats.
    
    Returns:
        list: All trackable awards with category, name, target, api_key
    """
    all_awards = []
    for category, awards in AWARDS_DATABASE.items():
        for award in awards:
            all_awards.append({
                "category": category,
                "name": award.get("name", "Unknown"),
                "target": award.get("target", 0),
                "api_key": award.get("api_key", ""),
                "description": award.get("description", "")
            })
    return all_awards


def calculate_progress(current_value: int, target: int) -> dict:
    """
    Calculate progress towards an award.
    
    Returns:
        dict: {
            "current": int,
            "target": int,
            "remaining": int,
            "progress_pct": float (0-100),
            "completed": bool
        }
    """
    if current_value >= target:
        return {
            "current": current_value,
            "target": target,
            "remaining": 0,
            "progress_pct": 100.0,
            "completed": True
        }
    
    progress_pct = (current_value / target) * 100 if target > 0 else 0
    
    return {
        "current": current_value,
        "target": target,
        "remaining": target - current_value,
        "progress_pct": min(progress_pct, 100.0),
        "completed": False
    }


def analyze_awards(personal_stats: dict, profile_data: dict = None) -> list:
    """
    Analyze all trackable awards and return sorted by progress.
    
    Args:
        personal_stats: Dict from Torn API personalstats selection
        profile_data: Optional dict with level, networth, etc.
        
    Returns:
        list: Sorted list of award progress dicts (closest to complete first)
    """
    if profile_data is None:
        profile_data = {}
    
    # Get all awards and sort by target ascending (lowest first)
    all_awards = get_all_trackable_awards()
    all_awards.sort(key=lambda x: x.get("target", 0))
    
    results = []
    seen_api_keys = set()  # Track which api_keys we've already added
    
    for award in all_awards:
        api_key = award.get("api_key", "")
        target = award.get("target", 0)
        
        if not api_key or target <= 0:
            continue
        
        # Skip if we already have an uncompleted award for this stat
        if api_key in seen_api_keys:
            continue
        
        # Get current value from personalstats or profile
        if api_key == "level":
            current_value = profile_data.get("level", 0)
        elif api_key == "daysold":
            current_value = profile_data.get("age", 0)
        elif api_key == "networth":
            current_value = profile_data.get("networth", 0) or personal_stats.get("networth", 0)
        elif api_key == "totalstats":
            # Sum of all battle stats
            current_value = (
                personal_stats.get("strength", 0) +
                personal_stats.get("defense", 0) +
                personal_stats.get("speed", 0) +
                personal_stats.get("dexterity", 0)
            )
        else:
            current_value = personal_stats.get(api_key, 0)
        
        if current_value is None:
            current_value = 0
            
        progress = calculate_progress(current_value, target)
        
        # Skip completed awards - but move to next target for same stat
        if progress["completed"]:
            continue
        
        # Mark this api_key as seen (we found its lowest uncompleted target)
        seen_api_keys.add(api_key)
        
        results.append({
            "category": award.get("category", "Unknown"),
            "name": award.get("name", "Unknown"),
            "description": award.get("description", ""),
            "api_key": api_key,
            **progress
        })
    
    # Sort by progress_pct descending (closest to complete first)
    results.sort(key=lambda x: x["progress_pct"], reverse=True)
    
    return results


def format_progress_bar(pct: float, width: int = 10) -> str:
    """Create visual progress bar."""
    filled = int(pct / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def get_top_targets(personal_stats: dict, profile_data: dict = None, limit: int = 5) -> list:
    """Get top N closest-to-complete award targets."""
    all_awards = analyze_awards(personal_stats, profile_data)
    return all_awards[:limit]


def get_awards_by_category(personal_stats: dict, category: str) -> list:
    """Get all awards for a specific category."""
    all_awards = analyze_awards(personal_stats)
    return [a for a in all_awards if a["category"].lower() == category.lower()]
