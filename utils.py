"""
Utility functions for The Consigliere bot.
"""
import re
import json
import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

# State file path
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")


def clean_html(text: str) -> str:
    """
    Remove all HTML tags from text using regex.
    
    Torn API sends events with HTML like:
    '<a href="...">PlayerName</a> mugged you and stole $1,000'
    
    This function strips all HTML tags to get clean text.
    
    Args:
        text: Text containing HTML tags
    
    Returns:
        str: Clean text without HTML tags
    """
    if not text:
        return ""
    
    # Remove HTML tags using regex
    clean = re.sub(r'<[^>]+>', '', text)
    
    # Decode common HTML entities
    clean = clean.replace('&amp;', '&')
    clean = clean.replace('&lt;', '<')
    clean = clean.replace('&gt;', '>')
    clean = clean.replace('&quot;', '"')
    clean = clean.replace('&#39;', "'")
    clean = clean.replace('&nbsp;', ' ')
    
    # Remove extra whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    
    return clean


def load_state() -> dict:
    """
    Load state from JSON file.
    
    Returns:
        dict: State data with defaults if file doesn't exist
    """
    default_state = {
        "last_event_id": 0,
        "company_enabled": True,
        "last_company_check": 0
    }
    
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                # Merge with defaults for any missing keys
                return {**default_state, **state}
    except Exception as e:
        logger.error(f"Failed to load state: {e}")
    
    return default_state


def save_state(state: dict) -> bool:
    """
    Save state to JSON file.
    
    Args:
        state: State dictionary to save
    
    Returns:
        bool: True if successful
    """
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save state: {e}")
        return False


def get_state_value(key: str, default: Any = None) -> Any:
    """
    Get a specific value from state.
    
    Args:
        key: State key
        default: Default value if key not found
    
    Returns:
        Value from state or default
    """
    state = load_state()
    return state.get(key, default)


def set_state_value(key: str, value: Any) -> bool:
    """
    Set a specific value in state.
    
    Args:
        key: State key
        value: Value to set
    
    Returns:
        bool: True if successful
    """
    state = load_state()
    state[key] = value
    return save_state(state)
