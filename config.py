"""
Configuration loader for The Consigliere Bot.
Loads environment variables from .env file.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_env(key: str, required: bool = True) -> str:
    """Get environment variable with validation."""
    value = os.getenv(key)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value or ""


# Telegram Configuration
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
USER_ID = int(get_env("USER_ID"))

# Groq Configuration
GROQ_API_KEY = get_env("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # atau "llama-3.1-8b-instant" untuk kecepatan

# Torn API Configuration
TORN_API_KEY = get_env("TORN_API_KEY")
TORN_API_BASE_URL = "https://api.torn.com"

# Scheduler Configuration
MONITOR_INTERVAL_SECONDS = 60
