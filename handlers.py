"""
Telegram Bot Handlers for The Consigliere v3.0.
Commands: /start, /stats, /help, /price, /stock, /crime
Features: Auth decorator, Battle log analysis
"""
import logging
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

from config import USER_ID
from torn_api import (
    get_extended_stats, 
    get_market_prices, 
    get_inventory, 
    get_nerve_for_crime,
    TornAPIError
)
from groq_client import chat_with_groq, get_crime_advice, analyze_battle_log, is_battle_log
from item_cache import get_item_id, get_item_name, MEDICAL_KEYWORDS, BOOSTER_KEYWORDS

logger = logging.getLogger(__name__)


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
    """Handle /start command with Reply Keyboard menu."""
    welcome_message = """🎩 *The Consigliere v3.0*
    
Selamat datang, Bos.

Saya adalah tangan kanan setia Anda di dunia kriminal Torn City.

*Fitur Dashboard v3.0:*
⚡ Energy/Nerve dengan estimasi waktu penuh
⚔️ Battle Stats & Work Stats lengkap
💡 Consigliere Advice untuk crime
🔔 Notifikasi event real-time

*Commands:*
• /stats - Live Dashboard Pro
• /price <item> - Cek harga market
• /stock - Inventory
• /crime - Saran AI
• /company - Status pekerjaan
• /help - Bantuan

_\"Seorang Bos tidak menunggu keberuntungan, dia menciptakannya.\"_"""
    
    await update.message.reply_text(
        welcome_message, 
        parse_mode="Markdown",
        reply_markup=MAIN_MENU_KB
    )


@auth_required
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handle /stats command - Live Dashboard with auto-refresh every 60 seconds.
    Uses edit_message_text to update the same message.
    """
    from datetime import datetime
    from telegram.error import BadRequest
    
    # === Stop Logic: Remove existing dashboard job if any ===
    if 'stats_job' in context.user_data:
        old_job = context.user_data['stats_job']
        old_job.schedule_removal()
        logger.info("Removed existing stats dashboard job")
    
    # === Initial Fetch ===
    try:
        dashboard_text = await format_dashboard_text()
    except TornAPIError as e:
        await update.message.reply_text(f"❌ Gagal mengambil data: {e}")
        return
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        await update.message.reply_text("❌ Terjadi kesalahan. Coba lagi nanti.")
        return
    
    # === Send Initial Message (HTML mode) ===
    sent_message = await update.message.reply_text(dashboard_text, parse_mode="HTML")
    
    # === Store Context for Job ===
    context.user_data['dashboard_message_id'] = sent_message.message_id
    context.user_data['dashboard_chat_id'] = sent_message.chat_id
    context.user_data['last_dashboard_text'] = dashboard_text
    
    # === Start Background Job (60 second interval) ===
    job = context.job_queue.run_repeating(
        callback=update_dashboard_job,
        interval=60,  # 60 seconds
        first=60,  # First run after 60 seconds
        chat_id=sent_message.chat_id,
        user_id=update.effective_user.id,
        data={
            'message_id': sent_message.message_id,
            'chat_id': sent_message.chat_id
        },
        name=f"dashboard_{update.effective_user.id}"
    )
    
    context.user_data['stats_job'] = job
    logger.info(f"Started live dashboard job for user {update.effective_user.id}")

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
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"{status_icon} <b>Status:</b> {state} {alert}\n"
        f"⏳ <i>{desc}</i>\n"
        f"🕐 <i>{time_text}</i>\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚡️ {format_bar_with_fulltime('Energy', e_cur, e_max, e_full)}\n"
        f"🔥 {format_bar_with_fulltime('Nerve ', n_cur, n_max, n_full)}\n"
        f"🙂 {format_bar_with_fulltime('Happy ', h_cur, h_max, h_full)}\n"
        f"❤️ {format_bar_with_fulltime('Life  ', l_cur, l_max, l_full)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"⚔️ <b>BATTLE STATS</b> (Total: {total_bs:,})\n"
        f"💪 Str: {strength:<6,} 🛡️ Def: {defense:,}\n"
        f"👟 Spd: {speed:<6,} 🎯 Dex: {dexterity:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💼 <b>WORK STATS</b> (Total: {manual+intel+endurance:,})\n"
        f"🧠 Int: {intel:<6,} 🏋️ End: {endurance:,}\n"
        f"🔨 Man: {manual:,}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💵 <code>Cash :</code> ${fmt_num(cash)}\n"
        f"💎 <code>Net  :</code> ${fmt_num(total_nw)}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 {format_cooldown_with_time('Drug   ', drug_cd)}\n"
        f"💉 {format_cooldown_with_time('Booster', booster_cd)}\n"
        f"🚑 {format_cooldown_with_time('Medical', medical_cd)}\n"
        f"🎓 <code>Edu    :</code> {edu_status}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"💡 <b>CONSIGLIERE ADVICE:</b>\n"
        f"\"{advice['text']}\"\n"
        f"👉 <b>Recommended Crime:</b> {advice['crime']}\n"
        f"📍 <b>Target:</b> {advice['target']}\n"
        f"➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n"
        f"🔄 <i>Auto-refresh 1 min</i>"
    )
    
    return msg



async def update_dashboard_job(context):
    """
    Background job to update the dashboard message every 60 seconds.
    
    Args:
        context: CallbackContext from python-telegram-bot
    """
    from telegram.error import BadRequest
    
    job_data = context.job.data
    message_id = job_data['message_id']
    chat_id = job_data['chat_id']
    
    try:
        # Fetch new dashboard text
        new_text = await format_dashboard_text()
        
        # Get last text to compare (avoid unnecessary edits)
        user_data = context.application.user_data.get(context.job.user_id, {})
        last_text = user_data.get('last_dashboard_text', '')
        
        # Only compare the stats part (exclude timestamp)
        # For simplicity, we always update since timestamp changes
        
        # Edit the message (HTML mode)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode="HTML"
        )
        
        # Update last text
        if context.job.user_id in context.application.user_data:
            context.application.user_data[context.job.user_id]['last_dashboard_text'] = new_text
        
        logger.debug(f"Dashboard updated for chat {chat_id}")
        
    except BadRequest as e:
        error_msg = str(e).lower()
        
        if "message is not modified" in error_msg:
            # Stats unchanged - this is normal, ignore
            logger.debug("Dashboard unchanged, skipping edit")
            
        elif "message to edit not found" in error_msg:
            # User deleted the message - stop the job
            logger.info(f"Dashboard message deleted, stopping job for chat {chat_id}")
            context.job.schedule_removal()
            
        else:
            logger.error(f"Dashboard update error: {e}")
            
    except TornAPIError as e:
        logger.error(f"API error during dashboard update: {e}")
        
    except Exception as e:
        logger.error(f"Unexpected error in dashboard update: {e}")




@auth_required
@auth_required
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message."""
    help_text = """
🆘 *THE CONSIGLIERE v3.0 - COMMANDS*

*Dashboard:*
/start - Menu utama
/stats - Live Dashboard Pro (auto-refresh)
/company - Status pekerjaan/perusahaan

*Market & Inventory:*
/price <item> - Cek harga termurah
/stock - Lihat inventory

*AI Advisor:*
/crime - Saran crime dari AI
💬 Tanya AI - Chat strategi langsung

*Fitur Pro v3.0:*
⚡ Estimasi waktu Full Energy/Nerve
⚔️ Battle Stats & Work Stats
� Consigliere Advice otomatis
🔔 Notifikasi semua event

_Gunakan tombol menu untuk navigasi cepat._
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")


@auth_required
async def company_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch and display company/job status."""
    from torn_api import get_company_data
    
    try:
        data = get_company_data()
        
        if data.get("error"):
            await update.message.reply_text(f"⚠️ {data['error']}")
            return

        name = data.get("name", "Unknown")
        position = data.get("position", "Employee")
        
        if data.get("is_director"):
            # Director View
            employees = data.get("employees", {})
            emp_count = len(employees) if isinstance(employees, dict) else 0
            
            message = (
                f"🏢 *PERUSAHAAN ANDA*\n\n"
                f"🏭 *{name}*\n"
                f"👨‍💼 Posisi: *Director*\n"
                f"👥 Karyawan: {emp_count} orang\n"
                f"💰 Daily Profit: ${data.get('daily_income', 0):,}\n\n"
                f"_Cek panel Torn untuk detail stok._"
            )
        else:
            # Employee View
            days = data.get("days_in_company", 0)
            eff = data.get("efficiency", 0)
            
            message = (
                f"🏢 *PEKERJAAN ANDA*\n\n"
                f"🏭 *{name}*\n"
                f"👷 Posisi: *{position}*\n"
                f"📅 Lama Kerja: {days} hari\n"
                f"📈 Efisiensi: {eff}%\n"
                f"💵 Gaji/Income: ${data.get('daily_income', 0):,}/hari"
            )
            
        await update.message.reply_text(message, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Error in company command: {e}")
        await update.message.reply_text("❌ Gagal mengambil data company.")


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
    
    # === Reply Keyboard Button Handlers ===
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
    [[KeyboardButton("🔙 Kembali ke Menu Utama")]],
    resize_keyboard=True
)

AI_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("🔙 Kembali ke Menu Utama")]],
    resize_keyboard=True
)

# Menu button texts for detection
MENU_BUTTONS = ["📊 Status", "💬 Tanya AI", "✈️ Travel", "💰 Market"]


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
    if user_text and "Kembali ke Menu Utama" in user_text:
        await update.message.reply_text(
            "👍 Oke Bos, kembali ke markas.",
            reply_markup=MAIN_MENU_KB  # Restore main menu keyboard
        )
        return -1  # ConversationHandler.END
    
    # Check if user clicked another menu button -> exit conversation
    if user_text in MENU_BUTTONS:
        if user_text == "📊 Status":
            await stats_command(update, context)
        elif user_text == "🎒 Inventory":
            await stock_command(update, context)
        elif user_text == "✈️ Travel":
            await travel_status(update, context)
        elif user_text == "💰 Market":
            # Re-enter market mode
            return await market_start(update, context)
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
    if user_text and "Kembali ke Menu Utama" in user_text:
        context.user_data.pop('ai_chat_history', None) # Clear memory
        await update.message.reply_text(
            "👍 Oke Bos, kembali ke markas.",
            reply_markup=MAIN_MENU_KB  # Restore main menu keyboard
        )
        return -1  # ConversationHandler.END
    
    # Switch to other menu modes if button clicked
    if user_text in MENU_BUTTONS:
        context.user_data.pop('ai_chat_history', None) # Clear memory
        if user_text == "📊 Status":
            await stats_command(update, context)
        elif user_text == "✈️ Travel":
            await travel_status(update, context)
        elif user_text == "💰 Market":
            # Just return END and let the entry point handle it if it matches the regex
            pass 
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

