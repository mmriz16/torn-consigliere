"""
Background Scheduler for monitoring Torn stats, events, and company.
Polls every 60 seconds (stats) and 30 minutes (company).
"""
import logging
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Bot

from config import MONITOR_INTERVAL_SECONDS, USER_ID
from torn_api import get_monitor_data, get_events, get_company_stock, get_inactive_employees, TornAPIError
from utils import clean_html, get_state_value, set_state_value

logger = logging.getLogger(__name__)

# Track previous state for change detection
previous_state = {
    "energy_was_full": False,
    "nerve_was_full": False,
    "was_in_hospital": False,
    "drug_cooldown_was_active": False,
    "booster_cooldown_was_active": False,
    "travel_notified": False,
    "was_traveling": False,
    "education_notified": False,
    "was_studying": False,
}


async def check_and_notify(bot: Bot):
    """
    Check Torn stats and send notifications if thresholds are met.
    Uses batched API call for efficiency.
    
    Alerts:
    1. Energy Full Alert
    2. Nerve Full Alert  
    3. Hospital Exit Alert
    4. Drug/Booster Cooldown End Alert
    5. Travel Landing Alert (2 min before)
    6. Education Alert (1 hour before completion)
    7. Event Watcher (Satpam System)
    """
    global previous_state
    
    try:
        # Single batched API call for all monitoring data (includes events)
        data = get_monitor_data()
    except TornAPIError as e:
        logger.error(f"Failed to fetch data: {e}")
        return
    
    messages = []
    
    # === Energy Full Alert ===
    energy = data.get("energy", {})
    energy_current = energy.get("current", 0)
    energy_max = energy.get("maximum", 0)
    energy_is_full = energy_current >= energy_max and energy_max > 0
    
    if energy_is_full and not previous_state["energy_was_full"]:
        messages.append(f"⚡ *ENERGY FULL!*\nBos, Energy sudah penuh ({energy_current}/{energy_max}). Saatnya beraksi!")
    previous_state["energy_was_full"] = energy_is_full
    
    # === Nerve Full Alert ===
    nerve = data.get("nerve", {})
    nerve_current = nerve.get("current", 0)
    nerve_max = nerve.get("maximum", 0)
    nerve_is_full = nerve_current >= nerve_max and nerve_max > 0
    
    if nerve_is_full and not previous_state["nerve_was_full"]:
        messages.append(f"🔥 *NERVE FULL!*\nBos, Nerve sudah penuh ({nerve_current}/{nerve_max}). Waktunya crime!")
    previous_state["nerve_was_full"] = nerve_is_full
    
    # === Hospital Exit Alert ===
    status = data.get("status", {})
    status_state = status.get("state", "").lower()
    is_in_hospital = status_state == "hospital"
    
    if previous_state["was_in_hospital"] and not is_in_hospital:
        messages.append("🏥 *KELUAR RUMAH SAKIT!*\nBos sudah sehat! Siap beraksi kembali.")
    previous_state["was_in_hospital"] = is_in_hospital
    
    # === Drug Cooldown End Alert ===
    cooldowns = data.get("cooldowns", {})
    drug_cooldown = cooldowns.get("drug", 0)
    drug_was_active = previous_state["drug_cooldown_was_active"]
    
    if drug_was_active and drug_cooldown == 0:
        messages.append("💊 *DRUG COOLDOWN SELESAI!*\nBos bisa minum Xanax lagi!")
    previous_state["drug_cooldown_was_active"] = drug_cooldown > 0
    
    # === Booster Cooldown End Alert ===
    booster_cooldown = cooldowns.get("booster", 0)
    booster_was_active = previous_state["booster_cooldown_was_active"]
    
    if booster_was_active and booster_cooldown == 0:
        messages.append("💉 *BOOSTER COOLDOWN SELESAI!*\nBos bisa pakai Booster lagi!")
    previous_state["booster_cooldown_was_active"] = booster_cooldown > 0
    
    # === Travel Landing Alert (2 min before) ===
    travel = data.get("travel", {})
    travel_time_left = travel.get("time_left", 0)
    destination = travel.get("destination", "")
    is_traveling = travel_time_left > 0 and destination != "Torn"
    
    if is_traveling and not previous_state["was_traveling"]:
        previous_state["travel_notified"] = False
    
    if is_traveling and travel_time_left <= 120 and not previous_state["travel_notified"]:
        messages.append(f"✈️ *MENDARAT SEGERA!*\nBos mendarat di *{destination}* dalam {travel_time_left // 60}m {travel_time_left % 60}s!\n\n_Awas begal, siapkan jari!_")
        previous_state["travel_notified"] = True
    
    previous_state["was_traveling"] = is_traveling
    
    # === Education Alert (1 hour before completion) ===
    education = data.get("education_current", data.get("education", {}))
    if isinstance(education, dict):
        edu_time_left = education.get("timeleft", 0)
    else:
        edu_time_left = 0
    
    is_studying = edu_time_left > 0
    
    if is_studying and not previous_state["was_studying"]:
        previous_state["education_notified"] = False
    
    if is_studying and edu_time_left <= 3600 and not previous_state["education_notified"]:
        hours = edu_time_left // 3600
        mins = (edu_time_left % 3600) // 60
        time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        messages.append(f"🎓 *STUDY ALERT!*\nKuliah selesai dalam {time_str}!\n\n_Siapkan buku baru, Bos!_")
        previous_state["education_notified"] = True
    
    previous_state["was_studying"] = is_studying
    
    # === Event Watcher (Satpam System) ===
    events_raw = data.get("events", {})
    if events_raw:
        event_messages = process_events(events_raw)
        messages.extend(event_messages)
    
    # === Inbox Spy (Message Forwarder) ===
    messages_raw = data.get("messages", {})
    if messages_raw:
        inbox_messages = process_inbox(messages_raw)
        messages.extend(inbox_messages)
    
    # Send all notifications
    for msg in messages:
        try:
            await bot.send_message(
                chat_id=USER_ID,
                text=msg,
                parse_mode="Markdown"
            )
            logger.info(f"Sent notification: {msg[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")


def process_events(events_raw: dict) -> list:
    """
    Process events and return notification messages for new events.
    Uses timestamp-based tracking since event IDs can be string hashes.
    
    Args:
        events_raw: Raw events dict from API
    
    Returns:
        list: Notification messages for new important events
    """
    messages = []
    
    # Get last processed event timestamp from persistent state
    last_event_ts = get_state_value("last_event_timestamp", 0)
    
    # Convert events dict to sorted list
    events_list = []
    if isinstance(events_raw, dict):
        for event_id, event_data in events_raw.items():
            if isinstance(event_data, dict):
                events_list.append({
                    "id": str(event_id),  # Keep as string
                    "event": event_data.get("event", ""),
                    "timestamp": event_data.get("timestamp", 0)
                })
    
    # Sort by timestamp ascending (oldest first for processing)
    events_list.sort(key=lambda x: x["timestamp"])
    
    # Find new events (timestamp > last processed)
    new_max_ts = last_event_ts
    for event in events_list:
        event_ts = event["timestamp"]
        
        if event_ts > last_event_ts:
            # This is a new event - report it!
            event_text = clean_html(event["event"])
            
            # Use icon based on keywords, but report EVERYTHING
            icon = "🔔"
            title = "EVENT BARU"
            
            event_lower = event_text.lower()
            if "bought" in event_lower or "purchased" in event_lower:
                icon = "💰"
                title = "Barang Laku"
            elif "mugged" in event_lower:
                icon = "💸"
                title = "RAMPOK!"
            elif "attacked" in event_lower and "you" in event_lower:
                icon = "⚔️"
                title = "SERANGAN!"
            elif "hospitalized" in event_lower:
                icon = "🏥"
                title = "Masuk RS"
            
            messages.append(f"{icon} *{title}*\n\n_{event_text}_")
            
            # Update max timestamp
            if event_ts > new_max_ts:
                new_max_ts = event_ts
    
    # Save new max event timestamp
    if new_max_ts > last_event_ts:
        set_state_value("last_event_timestamp", new_max_ts)
        logger.info(f"Updated last_event_timestamp to {new_max_ts}")
    
    return messages


def process_inbox(messages_raw: dict) -> list:
    """
    Process inbox messages and return notification for new messages.
    Uses timestamp-based tracking.
    
    Args:
        messages_raw: Raw messages dict from API
    
    Returns:
        list: Notification messages for new inbox messages
    """
    notifications = []
    
    # Get last processed message timestamp from persistent state
    last_msg_ts = get_state_value("last_message_timestamp", 0)
    
    # Convert messages dict to sorted list
    msg_list = []
    if isinstance(messages_raw, dict):
        for msg_id, msg_data in messages_raw.items():
            if isinstance(msg_data, dict):
                msg_list.append({
                    "id": str(msg_id),
                    "name": msg_data.get("name", "Unknown"),
                    "title": msg_data.get("title", "No Title"),
                    "text": msg_data.get("text", ""),
                    "timestamp": msg_data.get("timestamp", 0)
                })
    
    # Sort by timestamp ascending (oldest first for processing)
    msg_list.sort(key=lambda x: x["timestamp"])
    
    # Find new messages (timestamp > last processed)
    new_max_ts = last_msg_ts
    for msg in msg_list:
        msg_ts = msg["timestamp"]
        
        if msg_ts > last_msg_ts:
            # This is a new message - format and add
            sender = msg["name"]
            title = msg["title"]
            text = clean_html(msg["text"])
            
            # Truncate long messages
            if len(text) > 200:
                text = text[:200] + "..."
            
            notifications.append(
                f"📩 *Pesan Baru dari {sender}*\n\n"
                f"📌 *{title}*\n\n"
                f"_{text}_"
            )
            
            # Update max timestamp
            if msg_ts > new_max_ts:
                new_max_ts = msg_ts
    
    # Save new max message timestamp
    if new_max_ts > last_msg_ts:
        set_state_value("last_message_timestamp", new_max_ts)
        logger.info(f"Updated last_message_timestamp to {new_max_ts}")
    
    return notifications


async def check_company(bot: Bot):
    """
    Check company stock and employees (runs less frequently).
    """
    # Check if company feature is enabled
    if not get_state_value("company_enabled", True):
        return
    
    messages = []
    
    try:
        # === Stock Monitor ===
        low_stock = get_company_stock()
        for item in low_stock:
            if item["quantity"] == 0:
                messages.append(f"📦 *Gudang Kosong!*\nStok *{item['name']}* habis!\n\n_Lapor bos segera._")
            elif item["quantity"] < 50:
                messages.append(f"📦 *Stok Menipis!*\n*{item['name']}*: {item['quantity']} tersisa")
        
        # === Slacker Detector ===
        slackers = get_inactive_employees(threshold_days=3)
        for emp in slackers:
            messages.append(f"💤 *Slacker Alert!*\n*{emp['name']}* ({emp['position']}) sudah {emp['days_inactive']} hari tidak login.\n\n_Beban perusahaan!_")
        
    except TornAPIError as e:
        error_msg = str(e)
        if "permission" in error_msg.lower() or "error" in error_msg.lower():
            # Disable company feature
            set_state_value("company_enabled", False)
            messages.append("⚠️ *Company Feature Disabled*\nInsufficient API permission untuk akses data company.")
            logger.warning("Company feature disabled due to permission error")
    except Exception as e:
        logger.error(f"Company check error: {e}")
    
    # Send notifications
    for msg in messages:
        try:
            await bot.send_message(
                chat_id=USER_ID,
                text=msg,
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to send company notification: {e}")


def initialize_event_tracking():
    """
    Initialize event and message tracking on bot startup.
    Fetch latest timestamps without sending notifications.
    """
    from torn_api import get_messages
    
    # Initialize event tracking
    try:
        events = get_events()
        if events:
            newest_ts = events[0]["timestamp"]
            current_last_ts = get_state_value("last_event_timestamp", 0)
            
            if current_last_ts == 0:
                set_state_value("last_event_timestamp", newest_ts)
                logger.info(f"Initialized last_event_timestamp to {newest_ts}")
            else:
                logger.info(f"Resuming event tracking from timestamp {current_last_ts}")
    except Exception as e:
        logger.error(f"Failed to initialize event tracking: {e}")
    
    # Initialize message tracking
    try:
        messages = get_messages()
        if messages:
            newest_ts = messages[0]["timestamp"]
            current_last_ts = get_state_value("last_message_timestamp", 0)
            
            if current_last_ts == 0:
                set_state_value("last_message_timestamp", newest_ts)
                logger.info(f"Initialized last_message_timestamp to {newest_ts}")
            else:
                logger.info(f"Resuming message tracking from timestamp {current_last_ts}")
    except Exception as e:
        logger.error(f"Failed to initialize message tracking: {e}")


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """
    Create and configure the APScheduler.
    
    Args:
        bot: Telegram Bot instance for sending notifications
    
    Returns:
        AsyncIOScheduler: Configured scheduler
    """
    scheduler = AsyncIOScheduler()
    
    # Main monitor job (60 seconds)
    scheduler.add_job(
        check_and_notify,
        trigger=IntervalTrigger(seconds=MONITOR_INTERVAL_SECONDS),
        args=[bot],
        id="torn_monitor",
        name="Torn API Monitor",
        replace_existing=True
    )
    
    # Company monitor job (5 minutes for near real-time stock updates)
    scheduler.add_job(
        check_company,
        trigger=IntervalTrigger(minutes=5),
        args=[bot],
        id="company_monitor",
        name="Company Monitor",
        replace_existing=True
    )
    
    logger.info(f"Scheduler configured: stats={MONITOR_INTERVAL_SECONDS}s, company=5min")
    return scheduler
