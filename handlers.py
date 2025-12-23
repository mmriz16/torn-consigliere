"""
Telegram Bot Handlers for The Consigliere v4.0.
Commands: /start, /stats, /help, /price, /stock, /crime
Features: Auth decorator, Battle log analysis, Multi-menu navigation
"""
import logging
import html
from functools import wraps
from datetime import datetime, timezone, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import USER_ID
from torn_api import (
    get_extended_stats, 
    get_market_prices, 
    get_inventory, 
    get_nerve_for_crime,
    get_menu_data,
    TornAPIError
)
from groq_client import chat_with_groq, get_crime_advice, analyze_battle_log, is_battle_log
from item_cache import get_item_id, get_item_name, MEDICAL_KEYWORDS, BOOSTER_KEYWORDS
from utils import clean_html

logger = logging.getLogger(__name__)

# =============================================================================
# BALDR'S LIST - LOCAL DATA FILE
# =============================================================================
import os
import json

BALDR_TARGETS_FILE = os.path.join(os.path.dirname(__file__), "baldr_targets.json")

def get_baldr_data() -> list:
    """
    Get Baldr's leveling targets from local static file.
    Edit baldr_targets.json to add/remove/update targets manually.
    """
    try:
        with open(BALDR_TARGETS_FILE, 'r', encoding='utf-8') as f:
            targets = json.load(f)
            logger.info(f"Loaded {len(targets)} targets from local file")
            return targets
    except FileNotFoundError:
        logger.error(f"Baldr targets file not found: {BALDR_TARGETS_FILE}")
        return []
    except Exception as e:
        logger.error(f"Failed to load Baldr targets: {e}")
        return []




def auth_required(func):
    """
    Decorator to require authorization for command handlers.
    Only allows USER_ID from .env to access the bot.
    """
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if user_id != USER_ID:
            # Reply once with access denied, then ignore
            await update.message.reply_text("⛔ Access Denied.")
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


@auth_required
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show Dashboard directly with menu."""
    from telegram.error import BadRequest
    
    # === Stop Logic: Remove existing dashboard job if any ===
    if 'stats_job' in context.user_data:
        old_job = context.user_data['stats_job']
        old_job.schedule_removal()
        logger.info("Removed existing stats dashboard job")
    
    # === Fetch ALL data in one API call ===
    try:
        data = get_menu_data()
        context.user_data['menu_data'] = data
        context.user_data['menu_data_timestamp'] = datetime.now(timezone.utc).timestamp()
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
        return
    except Exception as e:
        logger.error(f"Error fetching menu data: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")
        return
    
    # === Format General Stats (default view) ===
    dashboard_text = format_general_stats(data)
    
    # === Send Dashboard with Reply Keyboard Menu at Bottom ===
    sent_message = await update.message.reply_text(
        dashboard_text, 
        parse_mode="HTML",
        reply_markup=STATUS_MENU_KB
    )
    
    # === Store Context for Navigation ===
    context.user_data['dashboard_message_id'] = sent_message.message_id
    context.user_data['dashboard_chat_id'] = sent_message.chat_id
    context.user_data['current_menu'] = 'general'
    
    logger.info(f"Dashboard shown for user {update.effective_user.id}")


# =============================================================================
# MULTI-MENU REPLY KEYBOARD (V2.0) - Compact Emoji Layout
# =============================================================================
from telegram import ReplyKeyboardMarkup, KeyboardButton

STATUS_MENU_KB = ReplyKeyboardMarkup(
    [
        [
            KeyboardButton("📊"), KeyboardButton("🏠"), 
            KeyboardButton("🏋️"), KeyboardButton("💼"),
            KeyboardButton("🛡️")
        ],
        [
            KeyboardButton("🔫"), KeyboardButton("📅"),
            KeyboardButton("💰"), KeyboardButton("💬"),
            KeyboardButton("✈️")
        ]
    ],
    resize_keyboard=True
)

# Menu button texts for detection (emoji only)
STATUS_MENU_BUTTONS = ["📊", "🏠", "🏋️", "💼", "🛡️", "🔫", "📅", "💰", "💬", "✈️"]


@auth_required
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /stats command - Multi-Menu Dashboard V2.0.
    Shows General Stats by default with Reply Keyboard for navigation.
    """
    from telegram.error import BadRequest
    
    # === Stop Logic: Remove existing dashboard job if any ===
    if 'stats_job' in context.user_data:
        old_job = context.user_data['stats_job']
        old_job.schedule_removal()
        logger.info("Removed existing stats dashboard job")
    
    # === Fetch ALL data in one API call ===
    try:
        data = get_menu_data()
        context.user_data['menu_data'] = data
        context.user_data['menu_data_timestamp'] = datetime.now(timezone.utc).timestamp()
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
        return
    except Exception as e:
        logger.error(f"Error fetching menu data: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")
        return
    
    # === Format General Stats (default view) ===
    dashboard_text = format_general_stats(data)
    
    # === Send Dashboard with Reply Keyboard Menu at Bottom ===
    sent_message = await update.message.reply_text(
        dashboard_text, 
        parse_mode="HTML",
        reply_markup=STATUS_MENU_KB
    )
    
    # === Store Context for Navigation ===
    context.user_data['dashboard_message_id'] = sent_message.message_id
    context.user_data['dashboard_chat_id'] = sent_message.chat_id
    context.user_data['current_menu'] = 'general'
    
    logger.info(f"Dashboard shown for user {update.effective_user.id}")



def create_bar(current: int, maximum: int, length: int = 10) -> str:
    """Create a progress bar using block characters (▓ and ░)."""
    if maximum <= 0:
        pct = 0
    else:
        pct = min(1.0, max(0.0, current / maximum))
    
    filled = int(length * pct)
    empty = length - filled
    
    return "▓" * filled + "░" * empty


def fmt_num(num) -> str:
    """Format number with commas (1000000 -> 1,000,000)."""
    return "{:,}".format(int(num))


def format_time(seconds: int) -> str:
    """
    Format seconds to readable time string.
    Supports days, hours, minutes. No seconds (refresh every minute).
    """
    if seconds <= 0:
        return "0m"
    
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if mins > 0 or not parts:  # Show at least 1m if no days/hours
        parts.append(f"{mins}m")
    
    return " ".join(parts)


def format_cooldown(seconds: int) -> str:
    """Format cooldown seconds to readable string with icon."""
    if seconds <= 0:
        return "✅ Ready"
    
    return f"🔴 {format_time(seconds)}"


def get_wib_now():
    """Get current time in WIB (UTC+7)."""
    from datetime import datetime, timezone, timedelta
    wib = timezone(timedelta(hours=7))
    return datetime.now(wib)


def format_exact_time(seconds: int, show_date: bool = False) -> str:
    """
    Format seconds into exact WIB time.
    If show_date=True or >24h, shows date like 'Des 28, 18:25'.
    Otherwise shows just time like '18:25'.
    """
    from datetime import timedelta
    if seconds <= 0:
        return ""
    
    target = get_wib_now() + timedelta(seconds=seconds)
    
    # If more than 24 hours, show date
    if seconds > 86400 or show_date:
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 
                  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des']
        return f"{months[target.month-1]} {target.day}, {target.strftime('%H:%M')}"
    else:
        return target.strftime("%H:%M")


def format_bar_with_fulltime(label: str, current: int, maximum: int, fulltime: int) -> str:
    """
    Format bar line with full time from API's fulltime field.
    fulltime: seconds until bar is full (from API).
    """
    bar = create_bar(current, maximum)
    base = f"<code>{label} [{bar}]</code> {current}/{maximum}"
    
    if fulltime > 0 and current < maximum:
        time_str = format_exact_time(fulltime)
        return f"{base} ({time_str})"
    return base


def format_cooldown_with_time(label: str, seconds: int) -> str:
    """Format cooldown line with exact ready time in WIB."""
    if seconds <= 0:
        return f"<code>{label}:</code> ✅ Ready"
    
    time_str = format_exact_time(seconds)
    return f"<code>{label}:</code> 🔴 {format_time(seconds)} ({time_str})"


def format_education_status(timeleft: int) -> str:
    """Format education status with exact completion date."""
    if timeleft <= 0:
        return "✅ Selesai"
    
    time_str = format_exact_time(timeleft, show_date=True)
    return f"📚 {format_time(timeleft)} ({time_str})"


def get_crime_advice(nerve_max: int) -> dict:
    """Get dynamic crime advice based on max nerve."""
    if nerve_max < 20:
        return {
            "text": "Nerve Bos masih kecil. Fokus bangun NNB dengan kejahatan aman.",
            "crime": "Search for Cash",
            "target": "Subway / Beach"
        }
    elif 20 <= nerve_max < 30:
        return {
            "text": "NNB mulai stabil. Bisa coba jual bajakan atau ngutil permen.",
            "crime": "Sell Copied Media / Shoplifting",
            "target": "Sweet Shop"
        }
    elif 30 <= nerve_max < 40:
        return {
            "text": "Coba crime menengah untuk XP lebih besar.",
            "crime": "Shoplifting (Clothes)",
            "target": "Clothes Shop"
        }
    else: # 40+
        return {
            "text": "Saatnya bakar-bakar gudang!",
            "crime": "Arson",
            "target": "Warehouse"
        }


async def format_dashboard_text() -> str:
    """
    Format the live dashboard text with current stats (Bot v3.0).
    Includes Battle Stats, Work Stats, and Dynamic Advice.
    """
    import html
    from datetime import datetime
    from torn_api import fetch_user_data
    
    # Fetch comprehensive data including battlestats and workstats
    # Using 'profile' selection instead of 'job' for company info in v1
    selections = "basic,bars,cooldowns,education,money,networth,icons,travel,battlestats,workstats,profile"
    data = fetch_user_data(selections)
    
    # Get basic info
    name = html.escape(data.get("name", "Unknown"))
    level = data.get("level", 0)
    
    # Get status info
    status = data.get("status", {})
    state = status.get("state", "Okay")
    desc = status.get("description", "Okay")
    until = status.get("until", 0)
    
    # Calculate time remaining
    current_time = int(datetime.now().timestamp())
    time_remaining = max(0, until - current_time) if until > 0 else 0
    
    # Format status icons
    status_icon = "🟢"
    alert = ""
    time_text = "Ready for Action"
    
    if state == "Hospital":
        status_icon = "🏥"
        alert = "🚨"
        time_text = f"{format_time(time_remaining)} left"
    elif state == "Jail":
        status_icon = "🚔"
        alert = "⛓️"
        time_text = f"{format_time(time_remaining)} left"
    elif state == "Traveling":
        status_icon = "✈️"
        alert = "🛬"
        travel = data.get("travel", {})
        time_text = f"{format_time(travel.get('time_left', 0))} to land"
    
    # Get bars (including fulltime from API)
    energy = data.get("energy", {})
    nerve = data.get("nerve", {})
    happy = data.get("happy", {})
    life = data.get("life", {})
    
    e_cur, e_max = energy.get("current", 0), energy.get("maximum", 0)
    e_full = energy.get("fulltime", 0)
    n_cur, n_max = nerve.get("current", 0), nerve.get("maximum", 0)
    n_full = nerve.get("fulltime", 0)
    h_cur, h_max = happy.get("current", 0), happy.get("maximum", 0)
    h_full = happy.get("fulltime", 0)
    l_cur, l_max = life.get("current", 0), life.get("maximum", 0)
    l_full = life.get("fulltime", 0)
    
    
    # Get Battle Stats (API returns flat structure, not nested)
    strength = data.get("strength", 0)
    defense = data.get("defense", 0)
    speed = data.get("speed", 0)
    dexterity = data.get("dexterity", 0)
    total_bs = data.get("total", 0) or sum([strength, defense, speed, dexterity])
    
    # Get Work Stats (API returns flat structure)
    manual = data.get("manual_labor", 0)
    intel = data.get("intelligence", 0)
    endurance = data.get("endurance", 0)
    
    # Get Cooldowns
    cd = data.get("cooldowns", {})
    drug_cd = cd.get("drug", 0)
    booster_cd = cd.get("booster", 0)
    medical_cd = cd.get("medical", 0)
    
    # Get Money
    cash = data.get("money_onhand", 0)
    networth = data.get("networth", {})
    total_nw = networth.get("total", 0) if isinstance(networth, dict) else 0
    # Calculate simple total if 'total' field missing
    if total_nw == 0 and isinstance(networth, dict):
        total_nw = sum(v for k,v in networth.items() if isinstance(v, (int, float)))
        
    # Education
    edu_time = data.get("education_timeleft", 0)
    edu_status = format_education_status(edu_time)
    
    # Consigliere Advice
    advice = get_crime_advice(n_max)
    
    # Time (WIB)
    now_str = get_wib_now().strftime("%H:%M")
    
    # Construct Message
    msg = (
        f"🕵️‍♂️ <b>THE CONSIGLIERE DASHBOARD</b>\n"
        f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"{status_icon} <b>Status:</b> {state} {alert}\n"
        f"⏳ <i>{desc}</i>\n"
        f"🕐 <i>{time_text}</i>\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚡️ {format_bar_with_fulltime('Energy', e_cur, e_max, e_full)}\n"
        f"🔥 {format_bar_with_fulltime('Nerve ', n_cur, n_max, n_full)}\n"
        f"🙂 {format_bar_with_fulltime('Happy ', h_cur, h_max, h_full)}\n"
        f"❤️ {format_bar_with_fulltime('Life  ', l_cur, l_max, l_full)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚔️ <b>BATTLE STATS</b> (Total: {total_bs:,})\n"
        f"💪 Str: {strength:<6,} 🛡️ Def: {defense:,}\n"
        f"👟 Spd: {speed:<6,} 🎯 Dex: {dexterity:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💼 <b>WORK STATS</b> (Total: {manual+intel+endurance:,})\n"
        f"🧠 Int: {intel:<6,} 🏋️ End: {endurance:,}\n"
        f"🔨 Man: {manual:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💵 <code>Cash :</code> ${fmt_num(cash)}\n"
        f"💎 <code>Net  :</code> ${fmt_num(total_nw)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 {format_cooldown_with_time('Drug   ', drug_cd)}\n"
        f"💉 {format_cooldown_with_time('Booster', booster_cd)}\n"
        f"🚑 {format_cooldown_with_time('Medical', medical_cd)}\n"
        f"🎓 <code>Edu    :</code> {edu_status}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <b>CONSIGLIERE ADVICE:</b>\n"
        f"\"{advice['text']}\"\n"
        f"👉 <b>Recommended Crime:</b> {advice['crime']}\n"
        f"📍 <b>Target:</b> {advice['target']}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🔄 <i>Auto-refresh 1 min</i>"
    )
    
    return msg


# =============================================================================
# MULTI-MENU FORMAT FUNCTIONS (V2.0)
# =============================================================================

def format_general_stats(data: dict) -> str:
    """Format General Stats menu - Status, Bars, Finance, Cooldowns."""
    
    # Get basic info
    name = html.escape(data.get("name", "Unknown"))
    level = data.get("level", 0)
    
    # Get status info
    status = data.get("status", {})
    state = status.get("state", "Okay")
    desc = status.get("description", "Okay")
    until = status.get("until", 0)
    
    # Calculate time remaining
    current_time = int(datetime.now().timestamp())
    time_remaining = max(0, until - current_time) if until > 0 else 0
    
    # Format status icons
    status_icon = "🟢"
    alert = ""
    time_text = "Ready for Action"
    
    if state == "Hospital":
        status_icon = "🏥"
        alert = "🚨"
        time_text = f"{format_time(time_remaining)} left"
    elif state == "Jail":
        status_icon = "🚔"
        alert = "⛓️"
        time_text = f"{format_time(time_remaining)} left"
    elif state == "Traveling":
        status_icon = "✈️"
        alert = "🛬"
        travel = data.get("travel", {})
        time_text = f"{format_time(travel.get('time_left', 0))} to land"
    
    # Get bars (including fulltime from API)
    energy = data.get("energy", {})
    nerve = data.get("nerve", {})
    happy = data.get("happy", {})
    life = data.get("life", {})
    
    e_cur, e_max = energy.get("current", 0), energy.get("maximum", 0)
    e_full = energy.get("fulltime", 0)
    n_cur, n_max = nerve.get("current", 0), nerve.get("maximum", 0)
    n_full = nerve.get("fulltime", 0)
    h_cur, h_max = happy.get("current", 0), happy.get("maximum", 0)
    h_full = happy.get("fulltime", 0)
    l_cur, l_max = life.get("current", 0), life.get("maximum", 0)
    l_full = life.get("fulltime", 0)
    
    # Get Cooldowns
    cd = data.get("cooldowns", {})
    drug_cd = cd.get("drug", 0)
    booster_cd = cd.get("booster", 0)
    medical_cd = cd.get("medical", 0)
    
    # Get Money
    cash = data.get("money_onhand", 0)
    networth = data.get("networth", {})
    total_nw = networth.get("total", 0) if isinstance(networth, dict) else 0
    if total_nw == 0 and isinstance(networth, dict):
        total_nw = sum(v for k,v in networth.items() if isinstance(v, (int, float)))
    
    # Time (WIB)
    now_str = get_wib_now().strftime("%H:%M")
    
    msg = (
        f"📊 <b>GENERAL STATS</b>\n"
        f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"{status_icon} <b>Status:</b> {state} {alert}\n"
        f"⏳ <i>{desc}</i>\n"
        f"🕐 <i>{time_text}</i>\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚡️ {format_bar_with_fulltime('Energy', e_cur, e_max, e_full)}\n"
        f"🔥 {format_bar_with_fulltime('Nerve ', n_cur, n_max, n_full)}\n"
        f"🙂 {format_bar_with_fulltime('Happy ', h_cur, h_max, h_full)}\n"
        f"❤️ {format_bar_with_fulltime('Life  ', l_cur, l_max, l_full)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💵 <code>Cash :</code> ${fmt_num(cash)}\n"
        f"💎 <code>Net  :</code> ${fmt_num(total_nw)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 {format_cooldown_with_time('Drug   ', drug_cd)}\n"
        f"💉 {format_cooldown_with_time('Booster', booster_cd)}\n"
        f"🚑 {format_cooldown_with_time('Medical', medical_cd)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🔄 <i>Auto-refresh 1 min | Pilih menu ⬇️</i>"
    )
    
    return msg


def format_property_stats(data: dict) -> str:
    """Format Property menu - Property info for Happy Jump planning."""
    
    name = html.escape(data.get("name", "Unknown"))
    now_str = get_wib_now().strftime("%H:%M")
    
    # Get happy bar for reference
    happy = data.get("happy", {})
    h_cur, h_max = happy.get("current", 0), happy.get("maximum", 0)
    
    # Get properties
    properties_raw = data.get("properties", {})
    
    prop_lines = []
    max_happy_bonus = 0
    
    if isinstance(properties_raw, dict):
        for prop_id, prop_data in properties_raw.items():
            if isinstance(prop_data, dict):
                # Get actual property name from 'property' field
                prop_name = prop_data.get("property", "Unknown")
                happy_bonus = prop_data.get("happy", 0)
                upkeep = prop_data.get("upkeep", 0)
                staff_cost = prop_data.get("staff_cost", 0)
                total_upkeep = upkeep + staff_cost
                status = prop_data.get("status", "")
                rented = prop_data.get("rented")
                
                if happy_bonus > max_happy_bonus:
                    max_happy_bonus = happy_bonus
                
                # Determine ownership status
                if rented and isinstance(rented, dict):
                    # This is a rented property
                    days_left = rented.get("days_left", 0)
                    cost_per_day = rented.get("cost_per_day", 0)
                    status_icon = "🏷️"
                    status_text = f"Rent ({days_left}d left, ${total_upkeep:,}/d)"
                elif "Owned" in status:
                    status_icon = "🔑"
                    status_text = "Owned"
                else:
                    status_icon = "🏠"
                    status_text = status[:20] if status else "Unknown"
                
                prop_lines.append(
                    f"{status_icon} <b>{prop_name}</b> [{status_text}]\n"
                    f"<code>   😊 Happy :</code> +{happy_bonus:,}\n"
                    f"<code>   💰 Upkeep:</code> <b>${total_upkeep:,}/day</b>\n\n"
                )
    
    if not prop_lines:
        prop_lines.append("❌ Tidak ada property yang dimiliki.")
    
    # Happy Jump check (target: >2950 for xanax)
    happy_jump_ready = h_max >= 2950
    jump_status = "✅ Ready for Happy Jump!" if happy_jump_ready else f"⚠️ Need {2950 - h_max:,} more max happy"
    
    msg = (
        f"🏠 <b>PROPERTY</b>\n"
        f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"😊 <code>Current Happy     :</code> {h_cur:,}/{h_max:,}\n"
        f"🎯 <code>Max Happy Capacity:</code> {h_max:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"{''.join(prop_lines)}"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🚀 <b>Happy Jump Status:</b>\n"
        f"{jump_status}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <i>Target: 2,950+ max happy untuk Xanax optimal</i>"
    )
    
    return msg


def format_gym_stats(data: dict) -> str:
    """Format GYM menu - Gym info, Battle Stats, and Predictive Gains."""
    
    name = html.escape(data.get("name", "Unknown"))
    level = data.get("level", 0)
    now_str = get_wib_now().strftime("%H:%M")
    
    # Get Gym Info from API
    gym_data = data.get("gym", {})
    gym_name = gym_data.get("name", "Unknown Gym") if isinstance(gym_data, dict) else "Unknown Gym"
    
    # Get Battle Stats
    strength = data.get("strength", 0)
    defense = data.get("defense", 0)
    speed = data.get("speed", 0)
    dexterity = data.get("dexterity", 0)
    total_bs = data.get("total", 0) or sum([strength, defense, speed, dexterity])
    
    # Get Energy and Happy for prediction
    energy = data.get("energy", {})
    happy = data.get("happy", {})
    e_cur = energy.get("current", 0) if isinstance(energy, dict) else 0
    h_cur = happy.get("current", 0) if isinstance(happy, dict) else 0
    h_max = happy.get("maximum", 2950) if isinstance(happy, dict) else 2950
    
    # Predictive Gains Calculator (simplified formula)
    # Base gain per energy is approximately 0.05-0.10 depending on gym
    # Happy bonus caps around 1.5x at max happy
    base_gain_per_e = 0.07
    happy_bonus = 1 + (h_cur / (h_max * 2))  # Roughly 1.0 - 1.5x based on happy
    estimated_gain = e_cur * base_gain_per_e * happy_bonus
    
    # Calculate percentages
    stats_list = [
        ("💪 Strength", strength),
        ("🛡️ Defense", defense),
        ("👟 Speed", speed),
        ("🎯 Dexterity", dexterity)
    ]
    
    # Find weakest stat for advice
    min_stat = min(stats_list, key=lambda x: x[1])
    max_stat = max(stats_list, key=lambda x: x[1])
    
    # Balance advice
    if min_stat[1] > 0:
        balance_ratio = max_stat[1] / min_stat[1]
        if balance_ratio > 2:
            advice = f"⚠️ {min_stat[0].split()[1]} terlalu rendah! Fokus latihan di area ini."
        elif balance_ratio > 1.5:
            advice = f"💡 {min_stat[0].split()[1]} perlu ditingkatkan untuk balance yang lebih baik."
        else:
            advice = "✅ Stats cukup seimbang! Lanjutkan latihan normal."
    else:
        advice = "🆕 Baru mulai? Fokus ke Gym!"
    
    msg = (
        f"🏋️ <b>GYM INTELLIGENCE</b>\n"
        f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🏠 <code>Active Gym :</code> <b>{gym_name}</b>\n"
        f"🏆 <code>Total Stats :</code> {total_bs:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💪 <code>Strength :</code> {strength:,}\n"
        f"🛡️ <code>Defense  :</code> {defense:,}\n"
        f"👟 <code>Speed    :</code> {speed:,}\n"
        f"🎯 <code>Dexterity:</code> {dexterity:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📈 <b>PREDICTIVE GAINS:</b>\n"
        f"⚡ Energy: {e_cur} | 🙂 Happy: {h_cur:,}/{h_max:,}\n"
        f"🎯 <i>Estimasi gain: +{estimated_gain:.2f} stats</i>\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📊 <b>ANALYSIS:</b>\n"
        f"🔝 <code>Tertinggi :</code> {max_stat[0]} ({max_stat[1]:,})\n"
        f"🔻 <code>Terendah  :</code> {min_stat[0]} ({min_stat[1]:,})\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <code>Saran:</code> {advice}"
    )
    
    return msg


def format_job_stats(data: dict) -> str:
    """Format Job menu - Complete Job Information."""
    
    name = html.escape(data.get("name", "Unknown"))
    now_str = get_wib_now().strftime("%H:%M")
    
    job = data.get("job", {})
    
    # Company type ID to name mapping
    COMPANY_TYPES = {
        1: "Hair Salon", 2: "Law Firm", 3: "Flower Shop", 4: "Car Dealership",
        5: "Clothing Store", 6: "Gun Shop", 7: "Game Shop", 8: "Candle Shop",
        9: "Toy Shop", 10: "Adult Novelties", 11: "Cyber Cafe", 12: "Grocery Store",
        13: "Theater", 14: "Sweet Shop", 15: "Cruise Line", 16: "Television Network",
        18: "Zoo", 19: "Firework Stand", 20: "Property Broker", 21: "Furniture Store",
        22: "Gas Station", 23: "Music Store", 24: "Nightclub", 25: "Pub",
        26: "Restaurant", 27: "Oil Rig", 28: "Fitness Center", 29: "Mechanic Shop",
        30: "Amusement Park", 31: "Lingerie Store", 32: "Meat Warehouse",
        33: "Farm", 34: "Software Corporation", 35: "Ladies Strip Club",
        36: "Mens Strip Club", 37: "Private Security Firm", 38: "Mining Corporation",
        39: "Detective Agency", 40: "Logistics Management"
    }
    
    job_type = job.get("job", "Employee")
    company_name = job.get("company_name", "Unemployed")
    company_type_id = job.get("company_type", 0)
    
    # Get company type name from ID
    if isinstance(company_type_id, int):
        company_type = COMPANY_TYPES.get(company_type_id, f"Type {company_type_id}")
    else:
        company_type = str(company_type_id)
    
    position = job.get("position", "N/A")
    
    # Job points - structure: jobpoints.companies.{company_type_id}.jobpoints
    job_points = 0
    jobpoints = data.get("jobpoints", {})
    if isinstance(jobpoints, dict):
        # For company jobs, job points are at: jobpoints['companies'][company_type_id]['jobpoints']
        companies_jp = jobpoints.get("companies", {})
        if isinstance(companies_jp, dict) and company_type_id:
            company_jp_data = companies_jp.get(str(company_type_id), {})
            if isinstance(company_jp_data, dict):
                job_points = company_jp_data.get("jobpoints", 0)
        
        # Fallback: for city jobs, points might be at jobpoints['jobs']
        if job_points == 0:
            jobs_jp = jobpoints.get("jobs", {})
            if isinstance(jobs_jp, dict):
                # Sum all city job points if available
                for job_type_key, points in jobs_jp.items():
                    if isinstance(points, (int, float)):
                        job_points += int(points)
    
    # Days in company
    days_in_company = job.get("days_in_company", 0)
    
    # Company rating - need to fetch from Company API
    company_id = job.get("company_id", 0)
    rating = "☆☆☆☆☆"  # Default
    if company_id:
        try:
            import requests
            from torn_api import TORN_API_BASE_URL, TORN_API_KEY
            url = f"{TORN_API_BASE_URL}/company/{company_id}?selections=profile&key={TORN_API_KEY}"
            response = requests.get(url, timeout=5)
            company_data = response.json()
            if "company" in company_data:
                company_rating_10 = company_data["company"].get("rating", 0)
                if isinstance(company_rating_10, (int, float)):
                    # Convert 10-star to 5-star: divide by 2 and round
                    rating_5 = round(company_rating_10 / 2)
                    rating = "⭐" * rating_5 + "☆" * (5 - rating_5) if rating_5 > 0 else "☆☆☆☆☆"
        except Exception:
            pass  # Keep default rating on error
    
    # Get Work Stats
    manual = data.get("manual_labor", 0)
    intel = data.get("intelligence", 0)
    endurance = data.get("endurance", 0)
    total_ws = manual + intel + endurance
    
    msg = (
        f"💼 <b>JOB INFORMATION</b>\n"
        f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"👔 <code>Job          :</code> {job_type}\n"
        f"🏭 <code>Company      :</code> {company_name}\n"
        f"📅 <code>Days         :</code> {days_in_company}\n"
        f"🏢 <code>Type         :</code> {company_type}\n"
        f"👷 <code>Position     :</code> {position}\n"
        f"📊 <code>Job points   :</code> {job_points:,}\n"
        f"⭐ <code>Rating       :</code> {rating}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📈 <b>WORK STATS</b> (Total: {total_ws:,})\n"
        f"🧠 <code>Intelligence :</code> {intel:,}\n"
        f"🏋️ <code>Endurance    :</code> {endurance:,}\n"
        f"🔨 <code>Manual Labor :</code> {manual:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <i>Work hard to become the best employee!</i>"
    )
    
    return msg


def format_gear_stats(data: dict) -> str:
    """Format Gear menu - Equipped weapons and armor with stats from itemstats API."""
    import requests
    from torn_api import TORN_API_BASE_URL, TORN_API_KEY
    
    name = html.escape(data.get("name", "Unknown"))
    now_str = get_wib_now().strftime("%H:%M")
    
    # Get equipment data from API
    equipment = data.get("equipment", [])
    
    # Equipped slot mapping:
    # 1 = Primary, 2 = Secondary, 3 = Melee
    # 4 = Body Armor, 6 = Helmet, 7 = Pants, 8 = Boots, 9 = Gloves
    
    WEAPON_SLOTS = {1: "Primary", 2: "Secondary", 3: "Melee"}
    ARMOR_SLOTS = {4: "Body", 6: "Helmet", 7: "Pants", 8: "Boots", 9: "Gloves"}
    
    weapons = []
    armor_items = []
    total_damage = 0
    total_accuracy = 0
    total_armor = 0
    
    # Helper function to get itemstats from torn API
    def get_itemstats(uid):
        try:
            url = f"{TORN_API_BASE_URL}/torn/{uid}?selections=itemstats&key={TORN_API_KEY}"
            response = requests.get(url, timeout=5)
            return response.json().get("itemstats", {})
        except Exception:
            return {}
    
    # Parse equipment list and fetch itemstats
    if isinstance(equipment, list):
        for item in equipment:
            if isinstance(item, dict):
                item_name = item.get("name", "Unknown")
                equipped_slot = item.get("equipped", 0)
                uid = item.get("UID", 0)
                
                if equipped_slot in WEAPON_SLOTS:
                    # Get itemstats for weapon
                    stats = get_itemstats(uid) if uid else {}
                    damage = stats.get("damage", 0)
                    accuracy = stats.get("acc", 0)
                    
                    slot_name = WEAPON_SLOTS[equipped_slot]
                    weapons.append({
                        "name": item_name,
                        "slot": slot_name,
                        "damage": damage,
                        "accuracy": accuracy
                    })
                    total_damage += damage
                    total_accuracy += accuracy
                    
                elif equipped_slot in ARMOR_SLOTS:
                    # Get itemstats for armor
                    stats = get_itemstats(uid) if uid else {}
                    armor_val = stats.get("arm", 0)
                    
                    slot_name = ARMOR_SLOTS[equipped_slot]
                    armor_items.append({
                        "name": item_name,
                        "slot": slot_name,
                        "armor": armor_val
                    })
                    total_armor += armor_val
    
    # Sort weapons: Primary, Secondary, Melee
    WEAPON_ORDER = {"Primary": 1, "Secondary": 2, "Melee": 3}
    weapons.sort(key=lambda x: WEAPON_ORDER.get(x['slot'], 99))
    
    # Format weapons - two lines per weapon
    weapons_lines = []
    for w in weapons:
        icon = "🔫" if w['slot'] in ["Primary", "Secondary"] else "🗡️"
        slot_padded = f"{w['slot']:<9}"  # Pad slot name
        weapons_lines.append(
            f"       {icon} {slot_padded} : <b>{w['name']}</b>\n"
            f"              | ⚔️ {w['damage']} | 🎯 {w['accuracy']} |"
        )
    
    if not weapons_lines:
        weapons_text = "      ❌ No weapons equipped"
    else:
        weapons_text = "\n".join(weapons_lines)
    
    # Sort armor: Helmet, Body, Gloves, Pants, Boots
    ARMOR_ORDER = {"Helmet": 1, "Body": 2, "Gloves": 3, "Pants": 4, "Boots": 5}
    armor_items.sort(key=lambda x: ARMOR_ORDER.get(x['slot'], 99))
    
    # Format armor - two lines per armor
    armor_lines = []
    for a in armor_items:
        slot_padded = f"{a['slot']:<6}"  # Pad slot name
        armor_lines.append(
            f"      🛡️ {slot_padded} : <b>{a['name']}</b>\n"
            f"             | 🛡️ {a['armor']} |"
        )
    
    if not armor_lines:
        armor_text = "     ❌ No armor equipped"
    else:
        armor_text = "\n".join(armor_lines)
    
    msg = (
        f"🛡️ <b>GEAR & EQUIPMENT</b>\n"
        f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📊 <b>TOTAL STATS:</b>\n"
        f"<code>⚔️ Damage   :</code> {total_damage}\n"
        f"<code>🎯 Accuracy :</code> {total_accuracy}\n"
        f"<code>🛡️ Armor    :</code> {total_armor}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🔫 <b>WEAPONS:</b> ({len(weapons)} equipped)\n"
        f"{weapons_text}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🛡️ <b>ARMOR:</b> ({len(armor_items)} equipped)\n"
        f"{armor_text}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <i>Higher stats = better combat!</i>"
    )
    
    return msg


def format_criminal_stats(data: dict) -> str:
    """Format Criminal menu - Criminal Record with XP Tracker for Quick Leveling."""
    
    name = html.escape(data.get("name", "Unknown"))
    level = data.get("level", 1)
    now_str = get_wib_now().strftime("%H:%M")
    
    # XP Progress Tracker
    # Torn XP requirements per level (approximate)
    XP_PER_LEVEL = {
        1: 0, 2: 250, 3: 500, 4: 1000, 5: 2000,
        6: 4000, 7: 8000, 8: 16000, 9: 32000, 10: 50000,
        11: 75000, 12: 100000, 13: 150000, 14: 200000, 15: 300000,
        16: 400000, 17: 500000, 18: 625000, 19: 750000, 20: 1000000
    }
    
    current_xp = XP_PER_LEVEL.get(level, 0)
    next_level_xp = XP_PER_LEVEL.get(level + 1, current_xp + 50000)
    level_15_xp = XP_PER_LEVEL.get(15, 300000)
    
    # Calculate progress (using crimes as proxy since we don't have exact XP)
    if level < 15:
        levels_to_15 = 15 - level
        xp_status = f"🎯 Target: <b>Level 15</b> ({levels_to_15} level lagi untuk Travel!)"
    else:
        xp_status = "✅ <b>Travel sudah terbuka!</b> Bos sudah Level 15+"
    
    # Get criminal record from API
    criminalrecord = data.get("criminalrecord", {})
    
    # Crime categories with their counts
    selling_illegal = criminalrecord.get("selling_illegal_products", 0)
    theft = criminalrecord.get("theft", 0)
    auto_theft = criminalrecord.get("auto_theft", 0)
    drug_deals = criminalrecord.get("drug_deals", 0)
    computer_crimes = criminalrecord.get("computer_crimes", 0)
    murder = criminalrecord.get("murder", 0)
    fraud_crimes = criminalrecord.get("fraud_crimes", 0)
    other = criminalrecord.get("other", 0)
    total = criminalrecord.get("total", 0)
    
    # If total is 0, calculate it
    if total == 0:
        total = selling_illegal + theft + auto_theft + drug_deals + computer_crimes + murder + fraud_crimes + other
    
    msg = (
        f"🔫 <b>QUICK LEVELING HUB</b>\n"
        f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📈 <b>XP PROGRESS:</b>\n"
        f"{xp_status}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📋 <b>CRIMINAL RECORD:</b>\n"
        f"💊 <code>Illegal products :</code> {selling_illegal:,}\n"
        f"🔓 <code>Theft            :</code> {theft:,}\n"
        f"🚗 <code>Auto theft       :</code> {auto_theft:,}\n"
        f"💉 <code>Drug deals       :</code> {drug_deals:,}\n"
        f"💻 <code>Computer crimes  :</code> {computer_crimes:,}\n"
        f"🔪 <code>Murder           :</code> {murder:,}\n"
        f"💳 <code>Fraud crimes     :</code> {fraud_crimes:,}\n"
        f"📦 <code>Other            :</code> {other:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📊 <b>TOTAL CRIMES:</b> {total:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <i>Serang target lemah untuk naik level cepat!</i>"
    )
    
    return msg


def format_events_stats(data: dict) -> str:
    """Format Events menu - Recent events and notifications."""
    
    name = html.escape(data.get("name", "Unknown"))
    now_str = get_wib_now().strftime("%H:%M")
    
    # Get events
    events_raw = data.get("events", {})
    
    event_lines = []
    event_count = 0
    
    if isinstance(events_raw, dict):
        # Sort by timestamp
        sorted_events = sorted(
            events_raw.items(),
            key=lambda x: x[1].get("timestamp", 0) if isinstance(x[1], dict) else 0,
            reverse=True
        )
        
        for event_id, event_data in sorted_events[:5]:
            if isinstance(event_data, dict):
                event_text = event_data.get("event", "")
                timestamp = event_data.get("timestamp", 0)
                
                # Clean HTML from event text
                clean_event = clean_html(event_text)
                
                # Format timestamp
                if timestamp > 0:
                    event_time = datetime.fromtimestamp(timestamp, tz=timezone(timedelta(hours=7)))
                    time_str = event_time.strftime("%H:%M")
                else:
                    time_str = "??:??"
                
                # Truncate long events
                if len(clean_event) > 60:
                    clean_event = clean_event[:57] + "..."
                
                event_lines.append(f"🔸 [{time_str}] {clean_event}")
                event_count += 1
    
    if not event_lines:
        event_lines.append("❌ Tidak ada event terbaru.")
    
    msg = (
        f"📅 <b>EVENTS</b>\n"
        f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"📬 <b>Recent Events:</b> ({event_count} shown)\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        + "\n".join(event_lines) +
        f"\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <i>Check Torn for full event details</i>"
    )
    
    return msg


# =============================================================================
# MENU CALLBACK HANDLER (V2.0)
# =============================================================================

async def handle_status_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button clicks for status menu navigation."""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback
    
    # Check authorization
    if query.from_user.id != USER_ID:
        return
    
    callback_data = query.data
    
    # Get cached data or fetch new
    data = context.user_data.get('menu_data', {})
    timestamp = context.user_data.get('menu_data_timestamp', 0)
    
    # If data is older than 5 minutes, refresh
    current_time = datetime.now(timezone.utc).timestamp()
    if not data or (current_time - timestamp) > 300:
        try:
            data = get_menu_data()
            context.user_data['menu_data'] = data
            context.user_data['menu_data_timestamp'] = current_time
        except TornAPIError as e:
            await query.edit_message_text(f"❌ Gagal refresh data: {e}")
            return
    
    # Format based on selected menu
    menu_formatters = {
        "menu_general": format_general_stats,
        "menu_property": format_property_stats,
        "menu_battle": format_battle_stats,
        "menu_job": format_job_stats,
        "menu_gear": format_gear_stats,
        "menu_criminal": format_criminal_stats,
        "menu_events": format_events_stats,
        "menu_refresh": format_general_stats,  # Refresh shows general stats
    }
    
    formatter = menu_formatters.get(callback_data, format_general_stats)
    
    # Special handling for refresh: force new data fetch
    if callback_data == "menu_refresh":
        try:
            data = get_menu_data()
            context.user_data['menu_data'] = data
            context.user_data['menu_data_timestamp'] = current_time
        except TornAPIError as e:
            await query.answer(f"❌ Refresh failed: {e}", show_alert=True)
            return
    
    # Format and edit message
    new_text = formatter(data)
    context.user_data['current_menu'] = callback_data.replace("menu_", "")
    
    try:
        await query.edit_message_text(
            text=new_text,
            parse_mode="HTML",
            reply_markup=STATUS_MENU_KB
        )
    except Exception as e:
        if "message is not modified" not in str(e).lower():
            logger.error(f"Error editing message: {e}")


async def baldr_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Refresh Targets button click - fetches new Baldr's targets."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    import requests
    import random
    from torn_api import TORN_API_KEY
    
    query = update.callback_query
    await query.answer("🔄 Refreshing targets...")
    
    # Check authorization
    if query.from_user.id != USER_ID:
        return
    
    try:
        # Get cached Baldr's list (or fetch fresh if cache expired)
        all_targets = get_baldr_data()
        
        if all_targets:
            # Parse comma-formatted numbers
            def parse_int(val):
                try:
                    return int(str(val).replace(',', ''))
                except:
                    return 0
            
            # Sort all targets by total stats (ascending)
            sorted_targets = sorted(all_targets, key=lambda x: parse_int(x.get('total', 0)))
            
            # Filter out hospitalized/jailed players
            available_targets = []
            for target in sorted_targets:
                t_id = target.get('id', '')
                if t_id:
                    try:
                        check_url = f"https://api.torn.com/user/{t_id}?selections=profile&key={TORN_API_KEY}"
                        status_resp = requests.get(check_url, timeout=5)
                        status_data = status_resp.json()
                        state = status_data.get('status', {}).get('state', 'Unknown')
                        
                        if state == 'Okay':
                            available_targets.append(target)
                            if len(available_targets) >= 5:
                                break
                    except:
                        continue
            
            # Select targets: highest level first, then 2 random
            if available_targets:
                # Sort by level descending to get highest level first
                sorted_by_level = sorted(available_targets, key=lambda x: parse_int(x.get('lvl', 0)), reverse=True)
                highest_level = sorted_by_level[0]
                
                # Get 2 more random targets (excluding highest level)
                remaining = [t for t in available_targets if t != highest_level]
                random_picks = random.sample(remaining, min(2, len(remaining))) if remaining else []
                
                selected = [highest_level] + random_picks
            else:
                selected = []
            
            if selected:
                # Create inline buttons
                buttons = []
                for target in selected:
                    t_name = target.get('name', 'Unknown')[:10]
                    t_lvl = target.get('lvl', '?')
                    t_id = target.get('id', '')
                    attack_url = f"https://www.torn.com/loader2.php?sid=getInAttack&user2ID={t_id}"
                    buttons.append([InlineKeyboardButton(
                        f"⚔️ {t_name} [Lvl {t_lvl}]", 
                        url=attack_url
                    )])
                
                buttons.append([InlineKeyboardButton("🔄 Refresh Targets", callback_data="baldr_refresh")])
                inline_kb = InlineKeyboardMarkup(buttons)
                
                # Update message with new targets
                await query.edit_message_reply_markup(reply_markup=inline_kb)
                return
        
        await query.answer("❌ No available targets found", show_alert=True)
        
    except Exception as e:
        logger.error(f"Baldr refresh error: {e}")
        await query.answer(f"❌ Error: {str(e)[:50]}", show_alert=True)


async def property_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle property market inline button callbacks (prop_*)."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from property_data import PROPERTY_TYPES, get_property_type_buttons, format_rental_listings
    from torn_api import get_menu_data
    
    query = update.callback_query
    await query.answer()
    
    # Check authorization
    if query.from_user.id != USER_ID:
        return
    
    callback_data = query.data
    now_str = get_wib_now().strftime("%H:%M")
    
    # Get user data for cash/property info
    data = context.user_data.get('menu_data', {})
    if not data:
        try:
            data = get_menu_data()
            context.user_data['menu_data'] = data
        except:
            pass
    
    user_cash = data.get('money_onhand', 0)
    name = html.escape(data.get('name', 'Bos'))
    
    # === LEVEL 1: MAIN MENU ===
    if callback_data == "prop_main":
        buttons = [
            [InlineKeyboardButton("🏠 My Property", callback_data="prop_my")],
            [InlineKeyboardButton("📈 Rental Market", callback_data="prop_rent")],
            [InlineKeyboardButton("💰 Selling Market", callback_data="prop_sell")],
        ]
        
        msg = (
            f"🏠 <b>PROPERTY MARKET</b>\n"
            f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>Cash:</b> <code>${user_cash:,}</code>\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Pilih menu properti:"
        )
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    # === MY PROPERTY ===
    if callback_data == "prop_my":
        # Reuse existing format_property_stats function
        msg = format_property_stats(data)
        
        buttons = [[InlineKeyboardButton("🔙 Kembali", callback_data="prop_main")]]
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    # === LEVEL 2: RENTAL MARKET - PROPERTY TYPE GRID ===
    if callback_data == "prop_rent":
        # Generate property type grid
        prop_buttons = get_property_type_buttons("rent")
        buttons = []
        for row in prop_buttons:
            btn_row = [InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row]
            buttons.append(btn_row)
        buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="prop_main")])
        
        msg = (
            f"📈 <b>RENTAL MARKET</b>\n"
            f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>Budget:</b> <code>${user_cash:,}</code>\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Pilih tipe properti:"
        )
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    # === LEVEL 2: SELLING MARKET - PROPERTY TYPE GRID ===
    if callback_data == "prop_sell":
        prop_buttons = get_property_type_buttons("sell")
        buttons = []
        for row in prop_buttons:
            btn_row = [InlineKeyboardButton(b["text"], callback_data=b["callback_data"]) for b in row]
            buttons.append(btn_row)
        buttons.append([InlineKeyboardButton("🔙 Kembali", callback_data="prop_main")])
        
        msg = (
            f"💰 <b>SELLING MARKET</b>\n"
            f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>Budget:</b> <code>${user_cash:,}</code>\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Pilih tipe properti:"
        )
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    # === LEVEL 3: RENTAL LISTINGS FOR SPECIFIC TYPE ===
    if callback_data.startswith("prop_rent_"):
        import requests
        from torn_api import TORN_API_KEY
        
        type_id = int(callback_data.split("_")[2])
        prop_info = PROPERTY_TYPES.get(type_id, {})
        
        # Fetch real listings from Torn API v2
        try:
            api_url = f"https://api.torn.com/v2/market/{type_id}/rentals?key={TORN_API_KEY}"
            resp = requests.get(api_url, timeout=10)
            rent_data = resp.json()
            listings = rent_data.get("rentals", {}).get("listings", [])
            
            # Holy Trinity keywords
            HOLY_TRINITY = ["Airstrip", "Vault", "Medical"]
            
            # Calculate value ratio and check Holy Trinity for each listing
            for listing in listings:
                mods = listing.get("modifications", [])
                mods_lower = [m.lower() for m in mods]
                
                # Check Holy Trinity (A/V/M)
                has_airstrip = any("airstrip" in m for m in mods_lower)
                has_vault = any("vault" in m for m in mods_lower)
                has_medical = any("medical" in m for m in mods_lower)
                listing["has_trinity"] = has_airstrip and has_vault and has_medical
                listing["trinity_flags"] = f"{'A' if has_airstrip else '-'}{'V' if has_vault else '-'}{'M' if has_medical else '-'}"
                
                # Calculate value ratio (cost per happiness)
                happy = listing.get("happy", 1)
                cost = listing.get("cost", 0)
                listing["value_ratio"] = cost / happy if happy > 0 else float('inf')
            
            # Sort by total cost ascending (primary sort)
            listings = sorted(listings, key=lambda x: x.get("cost", 0))
            
            # Find best value ratio among all listings
            best_value_ratio = min((l["value_ratio"] for l in listings), default=float('inf'))
            
            # Build listings text (top 5)
            listing_text = ""
            for i, listing in enumerate(listings[:5], 1):
                cost = listing.get("cost", 0)
                cost_per_day = listing.get("cost_per_day", 0)
                days = listing.get("rental_period", 0)
                happy = listing.get("happy", 0)
                trinity = listing.get("trinity_flags", "---")
                has_trinity = listing.get("has_trinity", False)
                value_ratio = listing.get("value_ratio", float('inf'))
                mods = listing.get("modifications", [])
                
                # Indicators
                best_value = "🔥" if value_ratio <= best_value_ratio * 1.05 else ""
                trinity_badge = "⭐" if has_trinity else ""
                budget_ok = "✅" if user_cash >= cost else "⚠️"
                
                # Shorten mod names for display (first 3 mods)
                short_mods = []
                for m in mods[:3]:
                    # Abbreviate long names
                    abbr = m.replace("Advanced ", "").replace("Superior ", "").replace(" Modification", "").replace(" Facility", "")
                    abbr = abbr[:8] if len(abbr) > 8 else abbr
                    short_mods.append(abbr)
                mods_str = ", ".join(short_mods) if short_mods else "none"
                if len(mods) > 3:
                    mods_str += f"+{len(mods)-3}"
                
                listing_text += (
                    f"{i}. {best_value}{trinity_badge}<code>${cost:>12,}</code> {budget_ok}\n"
                    f"   📅{days}d | 💰${cost_per_day:,}/d | 😊+{happy:,}\n"
                    f"   🔧[{trinity}] {mods_str}\n"
                )
            
            if not listing_text:
                listing_text = "📭 Tidak ada listing tersedia.\n"
            
            msg = (
                f"📈 <b>RENTAL: {prop_info.get('emoji', '🏠')} {prop_info.get('name', 'Unknown')}</b>\n"
                f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"💰 <b>Budget:</b> <code>${user_cash:,}</code>\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🏢 <b>TOP 5 TERMURAH:</b>\n"
                f"<i>🔥=Best Value ⭐=Holy Trinity [AVM]</i>\n\n"
                f"{listing_text}"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🔗 <a href='https://www.torn.com/properties.php#/p=rentals&type={type_id}'>Check on Torn Rental Market</a>"
            )
        except Exception as e:
            logger.error(f"Rental API error: {e}")
            msg = (
                f"📈 <b>RENTAL: {prop_info.get('emoji', '🏠')} {prop_info.get('name', 'Unknown')}</b>\n"
                f"❌ Gagal mengambil data. Coba lagi nanti."
            )
        
        buttons = [
            [InlineKeyboardButton("🔄 Refresh", callback_data=callback_data)],
            [InlineKeyboardButton("🔙 Kembali", callback_data="prop_rent")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        return
    
    # === LEVEL 3: SELLING LISTINGS FOR SPECIFIC TYPE ===
    if callback_data.startswith("prop_sell_"):
        import requests
        from torn_api import TORN_API_KEY
        
        type_id = int(callback_data.split("_")[2])
        prop_info = PROPERTY_TYPES.get(type_id, {})
        
        # Fetch real listings from Torn API v2
        try:
            api_url = f"https://api.torn.com/v2/market/{type_id}/properties?key={TORN_API_KEY}"
            resp = requests.get(api_url, timeout=10)
            sell_data = resp.json()
            listings = sell_data.get("properties", {}).get("listings", [])
            
            # Holy Trinity keywords
            HOLY_TRINITY = ["Airstrip", "Vault", "Medical"]
            
            # Calculate value ratio and check Holy Trinity for each listing
            for listing in listings:
                mods = listing.get("modifications", [])
                mods_lower = [m.lower() for m in mods]
                
                # Check Holy Trinity (A/V/M)
                has_airstrip = any("airstrip" in m for m in mods_lower)
                has_vault = any("vault" in m for m in mods_lower)
                has_medical = any("medical" in m for m in mods_lower)
                listing["has_trinity"] = has_airstrip and has_vault and has_medical
                listing["trinity_flags"] = f"{'A' if has_airstrip else '-'}{'V' if has_vault else '-'}{'M' if has_medical else '-'}"
                
                # Calculate value ratio (cost per happiness)
                happy = listing.get("happy", 1)
                cost = listing.get("cost", 0)
                listing["value_ratio"] = cost / happy if happy > 0 else float('inf')

            # Sort by cost ascending
            listings = sorted(listings, key=lambda x: x.get("cost", 0))
            
            # Find best value ratio among all listings
            best_value_ratio = min((l["value_ratio"] for l in listings), default=float('inf'))
            
            # Build listings text (top 5)
            listing_text = ""
            for i, listing in enumerate(listings[:5], 1):
                cost = listing.get("cost", 0)
                happy = listing.get("happy", 0)
                upkeep = listing.get("upkeep", 0)
                mods = listing.get("modifications", [])
                trinity = listing.get("trinity_flags", "---")
                has_trinity = listing.get("has_trinity", False)
                value_ratio = listing.get("value_ratio", float('inf'))
                
                # Indicators
                best_value = "🔥" if value_ratio <= best_value_ratio * 1.05 else ""
                trinity_badge = "⭐" if has_trinity else ""
                budget_ok = "✅" if user_cash >= cost else "⚠️"

                # Shorten mod names for display (first 3 mods)
                short_mods = []
                for m in mods[:3]:
                    # Abbreviate long names
                    abbr = m.replace("Advanced ", "").replace("Superior ", "").replace(" Modification", "").replace(" Facility", "")
                    abbr = abbr[:8] if len(abbr) > 8 else abbr
                    short_mods.append(abbr)
                mods_str = ", ".join(short_mods) if short_mods else "none"
                if len(mods) > 3:
                    mods_str += f"+{len(mods)-3}"
                
                listing_text += (
                    f"{i}. {best_value}{trinity_badge}<code>${cost:>13,}</code> {budget_ok}\n"
                    f"   😊+{happy:,} | 💰${upkeep:,}/d\n"
                    f"   🔧[{trinity}] {mods_str}\n"
                )
            
            if not listing_text:
                listing_text = "📭 Tidak ada listing tersedia.\n"
            
            msg = (
                f"💰 <b>FOR SALE: {prop_info.get('emoji', '🏠')} {prop_info.get('name', 'Unknown')}</b>\n"
                f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"💰 <b>Budget:</b> <code>${user_cash:,}</code>\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🏪 <b>TOP 5 TERMURAH:</b>\n"
                f"<i>🔥=Best Value ⭐=Holy Trinity [AVM]</i>\n\n"
                f"{listing_text}"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🔗 <a href='https://www.torn.com/properties.php#/p=market&type={type_id}'>Check on Torn Selling Market</a>"
            )
        except Exception as e:
            logger.error(f"Selling API error: {e}")
            msg = (
                f"💰 <b>FOR SALE: {prop_info.get('emoji', '🏠')} {prop_info.get('name', 'Unknown')}</b>\n"
                f"❌ Gagal mengambil data. Coba lagi nanti."
            )
        
        buttons = [
            [InlineKeyboardButton("🔄 Refresh", callback_data=callback_data)],
            [InlineKeyboardButton("🔙 Kembali", callback_data="prop_sell")]
        ]
        
        await query.edit_message_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
        return


async def handle_status_menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE, button_text: str):
    """
    Handle Reply Keyboard button clicks for status menu navigation.
    Sends a new message with the selected menu content.
    """
    # Get cached data or fetch new
    data = context.user_data.get('menu_data', {})
    timestamp = context.user_data.get('menu_data_timestamp', 0)
    
    # If data is older than 30 seconds or empty, refresh
    current_time = datetime.now(timezone.utc).timestamp()
    if not data or (current_time - timestamp) > 30:
        try:
            data = get_menu_data()
            context.user_data['menu_data'] = data
            context.user_data['menu_data_timestamp'] = current_time
        except TornAPIError as e:
            await update.message.reply_text(f"❌ Gagal refresh data: {e}")
            return
    
    # Special handlers for non-stats menu buttons
    # Note: 💰 and 💬 are now handled by ConversationHandler in main.py
    
    if button_text == "🏠":  # Property - Show inline menu for property market
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        
        name = html.escape(data.get("name", "Bos"))
        user_cash = data.get("money_onhand", 0)
        now_str = get_wib_now().strftime("%H:%M")
        
        buttons = [
            [InlineKeyboardButton("🏠 My Property", callback_data="prop_my")],
            [InlineKeyboardButton("📈 Rental Market", callback_data="prop_rent")],
            [InlineKeyboardButton("💰 Selling Market", callback_data="prop_sell")],
        ]
        
        msg = (
            f"🏠 <b>PROPERTY MARKET</b>\n"
            f"👤 <b>{name}</b> | 🕒 {now_str} WIB\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"💰 <b>Cash:</b> <code>${user_cash:,}</code>\n"
            f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
            f"Pilih menu properti:"
        )
        
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return
    
    if button_text == "✈️":  # Travel - Level 15 gatekeeper + profit calculator
        from travel_data import COUNTRIES, get_top_profitable_items, get_carry_capacity
        import random
        
        level = data.get("level", 1)
        name = html.escape(data.get("name", "Bos"))
        now_str = get_wib_now().strftime("%H:%M")
        
        if level < 15:
            # === LEVEL 15 GATEKEEPER ===
            # Get random Baldr target for motivation
            all_targets = get_baldr_data()
            target_text = ""
            if all_targets:
                # Get highest level available target
                def parse_int(val):
                    try:
                        return int(str(val).replace(',', ''))
                    except:
                        return 0
                sorted_by_level = sorted(all_targets, key=lambda x: parse_int(x.get('lvl', 0)), reverse=True)
                top_target = sorted_by_level[0]
                target_text = f"\n\n🎯 <b>TARGET REKOMENDASI:</b>\n⚔️ <a href='https://www.torn.com/loader2.php?sid=getInAttack&user2ID={top_target.get('id')}'>{top_target.get('name')}</a> [Lvl {top_target.get('lvl')}]"
            
            msg = (
                f"✈️ <b>TRAVEL INTELLIGENCE</b>\n"
                f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🚫 <b>AKSES DITOLAK!</b>\n\n"
                f"Otoritas penerbangan menolak Bos!\n"
                f"Level minimum untuk travel: <b>Level 15</b>\n"
                f"Level Bos saat ini: <b>Level {level}</b>\n\n"
                f"📈 Butuh <b>{15 - level} level lagi</b> untuk unlock!\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"💡 <i>Hajar target dari Baldr's List untuk naik level cepat!</i>"
                f"{target_text}"
            )
        else:
            # === LEVEL 15+ - SHOW TRAVEL INFO ===
            carry_cap = get_carry_capacity(level)
            top_items = get_top_profitable_items(top_n=5)
            
            # Group by country for top 3 destinations
            seen_countries = set()
            top_destinations = []
            for item in top_items:
                if item["country_key"] not in seen_countries:
                    seen_countries.add(item["country_key"])
                    potential_profit = item["profit"] * carry_cap
                    top_destinations.append({
                        **item,
                        "potential_profit": potential_profit
                    })
                if len(top_destinations) >= 3:
                    break
            
            dest_text = ""
            for i, dest in enumerate(top_destinations, 1):
                dest_text += (
                    f"{i}. {dest['flag']} <b>{dest['country_name']}</b>\n"
                    f"   📦 {dest['name']}\n"
                    f"   💰 Profit: <code>${dest['potential_profit']:,}</code> ({carry_cap} items)\n"
                    f"   ⏱️ Flight: {dest['flight_min']} min\n\n"
                )
            
            msg = (
                f"✈️ <b>TRAVEL INTELLIGENCE</b>\n"
                f"👤 <b>{name}</b> [Lvl {level}] | 🕒 {now_str} WIB\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"📦 <b>CARRY CAPACITY:</b> {carry_cap} items\n"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"🏆 <b>TOP 3 DESTINATIONS:</b>\n\n"
                f"{dest_text}"
                f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
                f"💡 <i>Profit = (Market - Buy) × Capacity</i>"
            )
        
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            reply_markup=STATUS_MENU_KB,
            disable_web_page_preview=True
        )
        return
    
    if button_text == "🔫":  # Criminal - Special handler with Baldr's inline buttons
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        import requests
        import random
        
        logger.info("🔫 Criminal handler triggered")
        
        # Format criminal stats text
        msg = format_criminal_stats(data)
        
        # Fetch Baldr's Leveling Targets (cached)
        try:
            all_targets = get_baldr_data()
            logger.info(f"Got {len(all_targets)} Baldr's targets")
            
            # Pick 3 random targets with low stats
            if all_targets:
                # Helper to parse comma-formatted numbers
                def parse_int(val):
                    try:
                        return int(str(val).replace(',', ''))
                    except:
                        return 0
                
                # Sort all targets by total stats (ascending)
                sorted_targets = sorted(all_targets, key=lambda x: parse_int(x.get('total', 0)))
                
                # Filter out hospitalized/jailed players using Torn API
                from torn_api import fetch_user_data, TORN_API_KEY
                
                available_targets = []
                for target in sorted_targets:
                    t_id = target.get('id', '')
                    if t_id:
                        try:
                            # Quick status check
                            check_url = f"https://api.torn.com/user/{t_id}?selections=profile&key={TORN_API_KEY}"
                            status_resp = requests.get(check_url, timeout=5)
                            status_data = status_resp.json()
                            state = status_data.get('status', {}).get('state', 'Unknown')
                            
                            if state == 'Okay':
                                available_targets.append(target)
                                if len(available_targets) >= 5:  # Get up to 5 available targets
                                    break
                        except:
                            continue
                
                # Select targets: highest level first, then 2 random
                if available_targets:
                    # Sort by level descending to get highest level first
                    sorted_by_level = sorted(available_targets, key=lambda x: parse_int(x.get('lvl', 0)), reverse=True)
                    highest_level = sorted_by_level[0]
                    
                    # Get 2 more random targets (excluding highest level)
                    remaining = [t for t in available_targets if t != highest_level]
                    random_picks = random.sample(remaining, min(2, len(remaining))) if remaining else []
                    
                    selected = [highest_level] + random_picks
                else:
                    selected = []
                
                # Create inline buttons for attack
                buttons = []
                for target in selected:
                    t_name = target.get('name', 'Unknown')[:10]
                    t_lvl = target.get('lvl', '?')
                    t_id = target.get('id', '')
                    attack_url = f"https://www.torn.com/loader2.php?sid=getInAttack&user2ID={t_id}"
                    buttons.append([InlineKeyboardButton(
                        f"⚔️ {t_name} [Lvl {t_lvl}]", 
                        url=attack_url
                    )])
                
                # Add refresh button
                buttons.append([InlineKeyboardButton("🔄 Refresh Targets", callback_data="baldr_refresh")])
                
                inline_kb = InlineKeyboardMarkup(buttons)
                
                # Add Baldr's section to message
                msg += "\n\n🎯 <b>BALDR'S TARGETS:</b> (Klik untuk serang)"
                
                await update.message.reply_text(
                    msg,
                    parse_mode="HTML",
                    reply_markup=inline_kb
                )
                return
        except Exception as e:
            logger.warning(f"Failed to fetch Baldr's list: {e}")
        
        # Fallback if Baldr's fetch fails
        await update.message.reply_text(
            msg,
            parse_mode="HTML",
            reply_markup=STATUS_MENU_KB
        )
        return
    
    if button_text == "✈️":  # Travel
        await update.message.reply_text(
            "✈️ <b>TRAVEL INFO</b>\n\n"
            "🏝️ Fitur travel akan segera hadir!\n\n"
            "💡 <i>Klik tombol lain untuk navigasi menu</i>",
            parse_mode="HTML",
            reply_markup=STATUS_MENU_KB
        )
        return
    
    # Map button text to formatter (emoji-only)
    # Note: 🔫 is handled by special handler above with Baldr's inline buttons
    menu_formatters = {
        "📊": format_general_stats,
        "🏠": format_property_stats,
        "🏋️": format_gym_stats,
        "💼": format_job_stats,
        "🛡️": format_gear_stats,
        "📅": format_events_stats,
    }
    
    formatter = menu_formatters.get(button_text, format_general_stats)
    
    # Special handling for refresh: force new data fetch
    if button_text == "🔄":
        try:
            data = get_menu_data()
            context.user_data['menu_data'] = data
            context.user_data['menu_data_timestamp'] = current_time
        except TornAPIError as e:
            await update.message.reply_text(f"❌ Refresh failed: {e}")
            return
    
    # Format and send message
    new_text = formatter(data)
    context.user_data['current_menu'] = button_text
    
    await update.message.reply_text(
        new_text,
        parse_mode="HTML",
        reply_markup=STATUS_MENU_KB
    )


async def update_menu_dashboard_job(context):
    """
    Background job to update the multi-menu dashboard every 60 seconds.
    Updates the current menu view with fresh data.
    """
    from telegram.error import BadRequest
    
    job_data = context.job.data
    message_id = job_data['message_id']
    chat_id = job_data['chat_id']
    
    try:
        # Fetch fresh data
        data = get_menu_data()
        
        # Get current menu from user_data
        user_data = context.application.user_data.get(context.job.user_id, {})
        current_menu = user_data.get('current_menu', 'general')
        
        # Update cached data
        if context.job.user_id in context.application.user_data:
            context.application.user_data[context.job.user_id]['menu_data'] = data
            context.application.user_data[context.job.user_id]['menu_data_timestamp'] = datetime.now(timezone.utc).timestamp()
        
        # Format based on current menu
        menu_formatters = {
            "general": format_general_stats,
            "property": format_property_stats,
            "battle": format_battle_stats,
            "job": format_job_stats,
            "gear": format_gear_stats,
            "criminal": format_criminal_stats,
            "events": format_events_stats,
        }
        
        formatter = menu_formatters.get(current_menu, format_general_stats)
        new_text = formatter(data)
        
        # Edit the message
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="HTML",
            reply_markup=STATUS_MENU_KB
        )
        
        logger.debug(f"Menu dashboard updated for chat {chat_id} (menu: {current_menu})")
        
    except BadRequest as e:
        error_msg = str(e).lower()
        
        if "message is not modified" in error_msg:
            logger.debug("Dashboard unchanged, skipping edit")
        elif "message to edit not found" in error_msg:
            logger.info(f"Dashboard message deleted, stopping job for chat {chat_id}")
            context.job.schedule_removal()
        else:
            logger.error(f"Dashboard update error: {e}")
            
    except TornAPIError as e:
        logger.error(f"API error during dashboard update: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error in dashboard update: {e}")


# Keep old dashboard job for backward compatibility (legacy)
async def update_dashboard_job(context):
    """
    Legacy background job for old dashboard format.
    Kept for backward compatibility.
    """
    from telegram.error import BadRequest
    
    job_data = context.job.data
    message_id = job_data['message_id']
    chat_id = job_data['chat_id']
    
    try:
        # Fetch new dashboard text using legacy function
        new_text = await format_dashboard_text()
        
        # Edit the message (HTML mode)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="HTML"
        )
        
        logger.debug(f"Legacy dashboard updated for chat {chat_id}")
        
    except BadRequest as e:
        error_msg = str(e).lower()
        
        if "message is not modified" in error_msg:
            logger.debug("Dashboard unchanged, skipping edit")
        elif "message to edit not found" in error_msg:
            logger.info(f"Dashboard message deleted, stopping job for chat {chat_id}")
            context.job.schedule_removal()
        else:
            logger.error(f"Dashboard update error: {e}")
            
    except TornAPIError as e:
        logger.error(f"API error during dashboard update: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error in dashboard update: {e}")


@auth_required
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    help_text = """
🆘 *THE CONSIGLIERE v4.0 - COMMANDS*

*Dashboard Multi-Menu:*
/start - Menu utama
/stats - Multi-Menu Dashboard (NEW!)
/company - Status pekerjaan/perusahaan

*Market:*
/price <item> - Cek harga termurah

*AI Advisor:*
/crime - Saran crime dari AI
💬 Tanya AI - Chat strategi langsung

*Fitur v4.0 (NEW!):*
📊 8 Menu Navigasi dengan Inline Keyboard
🏠 Property Info untuk Happy Jump
⚔️ Battle Stats dengan Analysis
💼 Job & Work Stats
🛡️ Gear & Equipment
🔫 Criminal dengan NNB Status
📅 Events Log
🔄 Auto-refresh 60 detik

_Klik tombol di bawah dashboard untuk navigasi._
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


@auth_required
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ultimate /price command with image, AI summary, and market data."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from torn_api import get_item_details
    from groq_client import summarize_item_desc
    import html
    
    if not context.args:
        await update.message.reply_text(
            "❌ Gunakan: `/price <nama_item>`\nContoh: `/price xanax`", 
            parse_mode="Markdown"
        )
        return
    
    item_name = " ".join(context.args)
    item_id = get_item_id(item_name)
    
    if not item_id:
        await update.message.reply_text(
            f"❌ Item '{item_name}' tidak ditemukan.\n\n_Coba nama lengkap atau sebagian seperti: xanax, first aid, e-dvd_", 
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text(f"⏳ Mengambil data {item_name}...")
    
    try:
        # Fetch item details and prices
        item_details = get_item_details(item_id)
        prices = get_market_prices(item_id)
        
        # Get AI summary of description
        ai_summary = summarize_item_desc(
            item_id, 
            item_details.get("description", ""),
            item_details.get("name", item_name)
        )
        
        # Format data
        name = html.escape(item_details.get("name", item_name))
        item_type = item_details.get("type", "Unknown")
        effect = item_details.get("effect", "")
        image_url = item_details.get("image_url")
        
        # Market prices
        bazaar_price = f"${prices['bazaar_lowest']:,}" if prices.get('bazaar_lowest') else "N/A"
        bazaar_qty = f"{prices.get('bazaar_stock', 0):,}"
        market_price = f"${prices['market_lowest']:,}" if prices.get('market_lowest') else "N/A"
        market_qty = f"{prices.get('market_stock', 0):,}"
        
        # Build caption (HTML mode)
        caption = (
            f"💊 <b>{name}</b> (ID: {item_id})\n"
            f"📂 <i>Type: {item_type}</i>\n\n"
            
            f"📝 <b>Deskripsi:</b>\n"
            f"{ai_summary}\n\n"
            
            f"⚡ <b>Efek/Fungsi:</b>\n"
            f"{effect if effect else 'Tidak ada efek khusus.'}\n\n"
            
            f"💰 <b>MARKET DATA:</b>\n"
            f"🏪 Bazaar: {bazaar_price} (Stok: {bazaar_qty})\n"
            f"🛒 Market: {market_price} (Stok: {market_qty})"
        )
        
        # Inline keyboard with refresh button
        keyboard = [[InlineKeyboardButton("🔄 Cek Lagi", callback_data=f"refresh_price_{item_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Try sending with photo
        try:
            await update.message.reply_photo(
                photo=image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        except Exception:
            # Fallback to text if image fails
            await update.message.reply_text(
                caption,
                parse_mode="HTML",
                reply_markup=reply_markup
            )
        
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
    except Exception as e:
        logger.error(f"Error in price_command: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")


async def refresh_price_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refresh price button callback."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from torn_api import get_item_details
    from groq_client import summarize_item_desc
    from item_cache import get_item_name
    import html
    
    query = update.callback_query
    await query.answer()  # Acknowledge the callback
    
    # Parse item_id from callback_data (format: refresh_price_{item_id})
    try:
        item_id = int(query.data.split("_")[-1])
    except ValueError:
        await query.edit_message_caption(caption="❌ Invalid item ID")
        return
    
    # Check authorization
    if query.from_user.id != USER_ID:
        return
    
    try:
        # Fetch updated data
        item_details = get_item_details(item_id)
        prices = get_market_prices(item_id)
        
        # Get AI summary (cached)
        ai_summary = summarize_item_desc(
            item_id,
            item_details.get("description", ""),
            item_details.get("name", "Item")
        )
        
        # Format data
        name = html.escape(item_details.get("name", "Unknown"))
        item_type = item_details.get("type", "Unknown")
        effect = item_details.get("effect", "")
        
        # Market prices
        bazaar_price = f"${prices['bazaar_lowest']:,}" if prices.get('bazaar_lowest') else "N/A"
        bazaar_qty = f"{prices.get('bazaar_stock', 0):,}"
        market_price = f"${prices['market_lowest']:,}" if prices.get('market_lowest') else "N/A"
        market_qty = f"{prices.get('market_stock', 0):,}"
        
        from datetime import datetime
        now = datetime.now().strftime("%H:%M")
        
        # Build updated caption
        caption = (
            f"💊 <b>{name}</b> (ID: {item_id})\n"
            f"📂 <i>Type: {item_type}</i>\n\n"
            
            f"📝 <b>Deskripsi:</b>\n"
            f"{ai_summary}\n\n"
            
            f"⚡ <b>Efek/Fungsi:</b>\n"
            f"{effect if effect else 'Tidak ada efek khusus.'}\n\n"
            
            f"💰 <b>MARKET DATA:</b>\n"
            f"🏪 Bazaar: {bazaar_price} (Stok: {bazaar_qty})\n"
            f"🛒 Market: {market_price} (Stok: {market_qty})\n\n"
            f"<i>🔄 Updated: {now}</i>"
        )
        
        # Inline keyboard with refresh button
        keyboard = [[InlineKeyboardButton("🔄 Cek Lagi", callback_data=f"refresh_price_{item_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_caption(
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in refresh_price_callback: {e}")
        await query.answer("❌ Gagal refresh data", show_alert=True)


@auth_required
async def stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stock command - show inventory status."""
    # Note: Torn API v2 removed inventory selection
    # This is a known API limitation until Torn completes item migration
    message = """📦 *Inventory Status*

⚠️ *Torn API Limitation*

Fitur inventory sementara tidak tersedia.

Torn telah menonaktifkan akses inventory di API v2 untuk proses migrasi sistem item.

*Alternatif:*
• Cek inventory langsung di game
• Gunakan /price <item> untuk cek harga

_Fitur akan aktif kembali setelah Torn menyelesaikan migrasi._"""
    
    await update.message.reply_text(message, parse_mode="Markdown")


@auth_required
async def crime_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /crime command - AI crime advisor."""
    await update.message.reply_text("⏳ Menganalisa nerve Bos...")
    
    try:
        nerve_data = get_nerve_for_crime()
        
        # Get AI advice
        advice = get_crime_advice(
            nerve_data["nerve_current"],
            nerve_data["nerve_max"],
            nerve_data["level"]
        )
        
        message = f"""🔥 *Crime Advisor*

📊 *Nerve:* {nerve_data['nerve_current']}/{nerve_data['nerve_max']}
👤 *Level:* {nerve_data['level']}

💡 *Saran:*
{advice}"""
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
    except Exception as e:
        logger.error(f"Error in crime_command: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")


@auth_required
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command messages - Button menu, Battle log analysis, or AI Chat."""
    user_text = update.message.text
    
    if not user_text:
        return
    
    # Strip whitespace
    user_text = user_text.strip()
    
    # === Status Menu Reply Keyboard Button Handlers (V2.0) ===
    # Check for exact emoji match or emoji at start
    for menu_emoji in STATUS_MENU_BUTTONS:
        if user_text == menu_emoji or user_text.startswith(menu_emoji):
            logger.info(f"Menu button detected: {repr(user_text)} matched {repr(menu_emoji)}")
            await handle_status_menu_button(update, context, menu_emoji)
            return
    
    # === Old Reply Keyboard Button Handlers ===
    if user_text == "📊 Status":
        await stats_command(update, context)
        return
    
    elif user_text == "✈️ Travel":
        await travel_status(update, context)
        return
    
    # Note: "💰 Market" and "💬 Tanya AI" are handled by ConversationHandlers separately
    
    # === Battle Log Detection ===
    if is_battle_log(user_text):
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id,
            action="typing"
        )
        
        await update.message.reply_text("⚔️ Menganalisa log pertarungan...")
        
        analysis = analyze_battle_log(user_text)
        
        message = f"""⚔️ *Battle Analysis*

{analysis}"""
        
        await update.message.reply_text(message, parse_mode="Markdown")
        return
    
    # === Regular AI Chat ===
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )
    
    response = chat_with_groq(user_text)
    await update.message.reply_text(response)


async def travel_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Travel button - show travel status."""
    from torn_api import fetch_user_data
    
    try:
        data = fetch_user_data("travel")
        travel = data.get("travel", {})
        
        destination = travel.get("destination", "Unknown")
        time_left = travel.get("time_left", 0)
        departed = travel.get("departed", 0)
        timestamp = travel.get("timestamp", 0)
        
        if time_left > 0:
            message = f"""✈️ *Status Perjalanan*

🌍 *Tujuan:* {destination}
⏱️ *Sisa Waktu:* {format_time(time_left)}

_Kamu sedang dalam perjalanan!_"""
        elif destination and destination != "Torn":
            message = f"""✈️ *Status Perjalanan*

📍 *Lokasi:* {destination}
🟢 *Status:* Sudah mendarat

_Siap beraksi di {destination}!_"""
        else:
            message = """✈️ *Status Perjalanan*

📍 *Lokasi:* Torn City
🏠 *Status:* Di rumah

_Tidak ada perjalanan aktif._"""
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal cek travel: {e}")
    except Exception as e:
        logger.error(f"Error in travel_status: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan.")


async def market_quick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Market button - show popular item prices."""
    from item_cache import find_item_id
    from torn_api import get_market_prices
    
    popular_items = ["Xanax", "FHC", "SED", "Morphine"]
    
    await update.message.reply_text("💰 Mengambil harga market...")
    
    try:
        lines = []
        for item_name in popular_items:
            item_id, actual_name = find_item_id(item_name)
            if item_id:
                prices = get_market_prices(item_id)
                market_price = prices.get("market_lowest", 0)
                if market_price:
                    lines.append(f"• *{actual_name}:* ${market_price:,}")
                else:
                    lines.append(f"• *{actual_name}:* _N/A_")
        
        if lines:
            message = "💰 *Harga Market Populer*\n\n" + "\n".join(lines)
            message += "\n\n_Ketik /price <item> untuk item lain_"
        else:
            message = "❌ Gagal mengambil harga."
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in market_quick: {e}")
        await update.message.reply_text("❌ Gagal mengambil harga market.")


@auth_required
async def company_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /company command - manual company status check."""
    from torn_api import get_company_data, get_inactive_employees
    from utils import get_state_value
    import time
    
    # Check if company feature is disabled
    if not get_state_value("company_enabled", True):
        await update.message.reply_text(
            "⚠️ *Company Feature Disabled*\n\n"
            "API key tidak punya permission untuk akses company data.\n"
            "Pastikan API key memiliki *Company* permission.",
            parse_mode="Markdown"
        )
        return
    
    await update.message.reply_text("⏳ Mengecek data company...")
    
    try:
        company_data = get_company_data()
        
        # Check for error with informative messages
        if company_data.get("error"):
            error_msg = company_data['error']
            
            if "Incorrect ID" in error_msg:
                await update.message.reply_text(
                    "❌ *Tidak Tergabung dalam Company*\n\n"
                    "Kamu belum bergabung dengan company manapun.\n"
                    "Untuk menggunakan fitur ini, bergabunglah dengan company terlebih dahulu.",
                    parse_mode="Markdown"
                )
            elif "permission" in error_msg.lower():
                await update.message.reply_text(
                    "❌ *Permission Denied*\n\n"
                    f"_{error_msg}_\n\n"
                    "Pastikan API key memiliki permission *Company*.",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(f"❌ {error_msg}")
            return
        
        # === Stock Status ===
        stock = company_data.get("stock", [])
        stock_lines = []
        
        for item in stock:
            if isinstance(item, dict):
                name = item.get("name", "Unknown")
                qty = item.get("in_stock", 0)
                sold = item.get("sold_amount", 0)
                
                # Add warning emoji for low stock
                warning = ""
                if qty == 0:
                    warning = "🔴 "
                elif qty < 100:
                    warning = "🟡 "
                
                stock_lines.append(f"{warning}• {name}: {qty:,} (sold: {sold:,})")
        
        stock_text = "\n".join(stock_lines[:10]) if stock_lines else "_Tidak ada data stok_"
        
        # === Employee Status ===
        employees_raw = company_data.get("employees", {})
        employee_lines = []
        current_time = int(time.time())
        
        if isinstance(employees_raw, dict):
            for emp_id, emp_data in list(employees_raw.items())[:10]:
                if isinstance(emp_data, dict):
                    name = emp_data.get("name", "Unknown")
                    position = emp_data.get("position", "Employee")
                    last_action = emp_data.get("last_action", {})
                    
                    if isinstance(last_action, dict):
                        last_ts = last_action.get("timestamp", 0)
                        relative = last_action.get("relative", "Unknown")
                    else:
                        last_ts = 0
                        relative = "Unknown"
                    
                    # Calculate days inactive
                    if last_ts > 0:
                        days_inactive = (current_time - last_ts) / 86400
                        if days_inactive >= 3:
                            employee_lines.append(f"💤 *{name}* ({position}): {relative}")
                        else:
                            employee_lines.append(f"✅ *{name}* ({position}): {relative}")
        
        employees_text = "\n".join(employee_lines) if employee_lines else "_Tidak ada data karyawan_"
        
        message = f"""🏢 *Company Status*

📦 *Stok Gudang:*
{stock_text}

👥 *Karyawan:*
{employees_text}

_🔴 Habis | 🟡 < 100 | 💤 Inactive 3+ hari_"""
        
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
    except Exception as e:
        logger.error(f"Error in company_command: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")


# =============================================================================
# MARKET CONVERSATION HANDLER
# =============================================================================
from telegram import ReplyKeyboardMarkup, KeyboardButton

# State constants
MARKET_SEARCH = 1
AI_ADVISOR = 2

# Keyboard Layouts
MAIN_MENU_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("📊 Status"), KeyboardButton("💬 Tanya AI")],
        [KeyboardButton("✈️ Travel"), KeyboardButton("💰 Market")]
    ],
    resize_keyboard=True
)

MARKET_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("🔙 Kembali")]],
    resize_keyboard=True
)

AI_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("🔙 Kembali")]],
    resize_keyboard=True
)

# Menu button texts for detection (old format, now using emoji-only)


async def market_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for Market conversation - triggered by 💰 Market button."""
    user_id = update.effective_user.id
    
    if user_id != USER_ID:
        await update.message.reply_text("⛔ Access Denied.")
        return -1  # ConversationHandler.END
    
    message = """💰 *MODE MARKET AKTIF*

Siap Bos. Mau cek harga barang apa?

Ketik nama barang langsung _(misal: Xanax, FHC, Morphine)_

Klik tombol 🔙 jika sudah selesai."""
    
    await update.message.reply_text(
        message, 
        parse_mode="Markdown",
        reply_markup=MARKET_KB  # Switch to Market keyboard
    )
    return MARKET_SEARCH


async def market_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle item search in Market conversation mode."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from torn_api import get_item_details
    from groq_client import summarize_item_desc
    import html as html_lib
    
    user_text = update.message.text
    
    if not user_text:
        return MARKET_SEARCH
    
    # Check authorization
    if update.effective_user.id != USER_ID:
        return MARKET_SEARCH
    
    # Check if user clicked "Back" button -> exit and restore main menu
    if user_text and "Kembali" in user_text:
        await update.message.reply_text(
            "👍 Oke Bos, kembali ke markas.",
            reply_markup=STATUS_MENU_KB  # Restore main menu keyboard
        )
        return -1  # ConversationHandler.END
    
    # Check if user clicked another menu emoji button -> exit conversation
    if user_text in STATUS_MENU_BUTTONS:
        await handle_status_menu_button(update, context, user_text)
        return -1  # ConversationHandler.END
    
    # Treat input as item name
    item_name = user_text.strip()
    item_id = get_item_id(item_name)
    
    if not item_id:
        await update.message.reply_text(
            f"❌ Barang '{item_name}' gak ketemu Bos.\n\nCoba nama lain.",
            parse_mode="Markdown",
            reply_markup=MARKET_KB  # Keep market keyboard
        )
        return MARKET_SEARCH  # Stay in search mode
    
    # Fetch item data and show price (same as /price)
    try:
        item_details = get_item_details(item_id)
        prices = get_market_prices(item_id)
        
        # Get AI summary (cached)
        ai_summary = summarize_item_desc(
            item_id,
            item_details.get("description", ""),
            item_details.get("name", item_name)
        )
        
        # Format data
        name = html_lib.escape(item_details.get("name", item_name))
        item_type = item_details.get("type", "Unknown")
        effect = item_details.get("effect", "")
        image_url = item_details.get("image_url")
        
        # Market prices
        bazaar_price = f"${prices['bazaar_lowest']:,}" if prices.get('bazaar_lowest') else "N/A"
        bazaar_qty = f"{prices.get('bazaar_stock', 0):,}"
        market_price = f"${prices['market_lowest']:,}" if prices.get('market_lowest') else "N/A"
        market_qty = f"{prices.get('market_stock', 0):,}"
        
        # Build caption (HTML mode)
        caption = (
            f"💊 <b>{name}</b> (ID: {item_id})\n"
            f"📂 <i>Type: {item_type}</i>\n\n"
            
            f"📝 <b>Deskripsi:</b>\n"
            f"{ai_summary}\n\n"
            
            f"⚡ <b>Efek/Fungsi:</b>\n"
            f"{effect if effect else 'Tidak ada efek khusus.'}\n\n"
            
            f"💰 <b>MARKET DATA:</b>\n"
            f"🏪 Bazaar: {bazaar_price} (Stok: {bazaar_qty})\n"
            f"🛒 Market: {market_price} (Stok: {market_qty})"
        )
        
        # Inline keyboard with refresh button
        keyboard = [[InlineKeyboardButton("🔄 Cek Lagi", callback_data=f"refresh_price_{item_id}")]]
        inline_markup = InlineKeyboardMarkup(keyboard)
        
        # Try sending with photo
        try:
            await update.message.reply_photo(
                photo=image_url,
                caption=caption,
                parse_mode="HTML",
                reply_markup=inline_markup
            )
        except Exception:
            await update.message.reply_text(
                caption,
                parse_mode="HTML",
                reply_markup=inline_markup
            )
        
        # Follow-up message with Market keyboard
        await update.message.reply_text(
            "✅ Ada lagi? Ketik nama barang.\n_Atau klik 🔙 untuk keluar._",
            parse_mode="Markdown",
            reply_markup=MARKET_KB  # Keep market keyboard visible
        )
        
    except TornAPIError as e:
        await update.message.reply_text(
            f"❌ Gagal mengambil data: {e}",
            reply_markup=MARKET_KB
        )
    except Exception as e:
        logger.error(f"Error in market_search: {e}")
        await update.message.reply_text(
            "❌ Terjadi kesalahan. Coba lagi.",
            reply_markup=MARKET_KB
        )
    
    return MARKET_SEARCH  # Stay in search mode


async def market_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exit Market conversation mode via /cancel command."""
    await update.message.reply_text(
        "👍 Oke Bos, mode pasar ditutup.",
        reply_markup=MAIN_MENU_KB  # Restore main menu keyboard
    )
    return -1  # ConversationHandler.END


# =============================================================================
# AI ADVISOR CONVERSATION HANDLER
# =============================================================================

async def ai_advisor_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Entry point for AI Advisor conversation - triggered by 💬 Tanya AI button."""
    user_id = update.effective_user.id
    
    if user_id != USER_ID:
        await update.message.reply_text("⛔ Access Denied.")
        return -1  # ConversationHandler.END
    
    message = """🕶️ *AI ADVISOR MODE*

Silakan duduk, Bos. Ada masalah apa? 
_(Saya tahu status keuangan & level Bos saat ini)._

Ketik apa saja untuk bertanya seputar Torn City. 
Klik tombol 🔙 jika sudah selesai."""
    
    # Initialize chat history for this session
    context.user_data['ai_chat_history'] = []
    
    await update.message.reply_text(
        message, 
        parse_mode="Markdown",
        reply_markup=AI_KB  # Switch to AI keyboard
    )
    return AI_ADVISOR


async def ai_advisor_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user questions in AI Advisor mode with context injection."""
    from groq_client import chat_with_context, build_user_context
    
    user_text = update.message.text
    if not user_text:
        return AI_ADVISOR
    
    if update.effective_user.id != USER_ID:
        return AI_ADVISOR
    
    # Check if user clicked "Back" button -> exit and restore main menu
    if user_text and "Kembali" in user_text:
        context.user_data.pop('ai_chat_history', None) # Clear memory
        await update.message.reply_text(
            "👍 Oke Bos, kembali ke markas.",
            reply_markup=STATUS_MENU_KB  # Restore main menu keyboard
        )
        return -1  # ConversationHandler.END
    
    # Switch to other menu modes if button clicked
    if user_text in STATUS_MENU_BUTTONS:
        context.user_data.pop('ai_chat_history', None) # Clear memory
        await handle_status_menu_button(update, context, user_text)
        return -1 # Exit conversation to handle outside
    
    # Show typing action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    # Fetch real-time user context
    user_context = build_user_context()
    
    # Retrieve history from user_data
    history = context.user_data.get('ai_chat_history', [])
    
    # Get context-aware response from Groq (inject history)
    response = chat_with_context(user_text, user_context, history=history)
    
    # Update history: append user message and AI response
    history.append({"role": "user", "content": user_text})
    history.append({"role": "assistant", "content": response})
    
    # Keep only last 10 messages (5 user/assistant pairs) to save tokens
    context.user_data['ai_chat_history'] = history[-10:]
    
    # Reply to user
    await update.message.reply_text(
        response,
        reply_markup=AI_KB
    )
    
    return AI_ADVISOR


async def ai_advisor_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Exit AI Advisor conversation mode."""
    context.user_data.pop('ai_chat_history', None) # Clear memory
    await update.message.reply_text(
        "👍 Oke Bos, kembali ke markas.",
        reply_markup=MAIN_MENU_KB
    )
    return -1  # ConversationHandler.END

