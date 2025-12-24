"""
The Consigliere v4.0 - Torn City Telegram Bot
Entry point for the application.
"""
import logging

# --- SISIPKAN INI DI PALING ATAS SETELAH IMPORT ---
from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Consigliere Bot is Alive!"

def run_http():
    # Render memberikan port lewat environment variable, default ke 8080 kalau tidak ada
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_http)
    t.start()
# --------------------------------------------------

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from handlers import (
    start_command, 
    handle_message
)
from scheduler import create_scheduler, initialize_event_tracking
from item_cache import fetch_all_items

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global scheduler reference
scheduler = None


async def post_init(application: Application):
    """Called after Application is initialized and event loop is running."""
    global scheduler
    
    # Initialize item cache from Torn API
    logger.info("Loading item database...")
    if fetch_all_items():
        logger.info("Item database loaded successfully")
    else:
        logger.warning("Failed to load item database, using fallback")
    
    # Initialize event tracking (set last_event_id on first run)
    logger.info("Initializing event tracking...")
    initialize_event_tracking()
    
    # Start scheduler
    scheduler = create_scheduler(application.bot)
    scheduler.start()
    logger.info("Scheduler started (stats=60s, company=30min)")


async def post_shutdown(application: Application):
    """Called when Application is shutting down."""
    global scheduler
    if scheduler:
        scheduler.shutdown()
        logger.info("Scheduler stopped")


def main():
    """Start the bot."""
    logger.info("Starting The Consigliere v3.5...")
    
    # Create Application with post_init hook
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    
    # Callback query handler for inline keyboard buttons
    from telegram.ext import CallbackQueryHandler, ConversationHandler
    from handlers import (
        refresh_price_callback, 
        handle_status_menu_callback,
        baldr_refresh_callback,
        property_callback,
        stats_hub_callback,
        market_start, market_search, market_cancel, MARKET_SEARCH,
        ai_advisor_start, ai_advisor_chat, ai_advisor_cancel, AI_ADVISOR
    )
    
    # Price refresh callback
    application.add_handler(CallbackQueryHandler(refresh_price_callback, pattern=r"^refresh_price_\d+$"))
    
    # Baldr's targets refresh callback
    application.add_handler(CallbackQueryHandler(baldr_refresh_callback, pattern=r"^baldr_refresh$"))
    
    # Property market callback (prop_*)
    application.add_handler(CallbackQueryHandler(property_callback, pattern=r"^prop_"))
    
    # Status menu navigation callback (V2.0 multi-menu)
    application.add_handler(CallbackQueryHandler(handle_status_menu_callback, pattern=r"^menu_"))
    
    # Stats Hub callback (📩 Inbox, 🔔 Events, 🏅 Awards)
    application.add_handler(CallbackQueryHandler(stats_hub_callback, pattern=r"^stats_"))
    
    # Market Conversation Handler (continuous item search)
    market_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💰$"), market_start)
        ],
        states={
            MARKET_SEARCH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, market_search)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", market_cancel),
            CommandHandler("stop", market_cancel)
        ],
        allow_reentry=True
    )
    application.add_handler(market_conv_handler)

    # AI Advisor Conversation Handler (context-aware chat)
    ai_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^💬$"), ai_advisor_start)
        ],
        states={
            AI_ADVISOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, ai_advisor_chat)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", ai_advisor_cancel),
            CommandHandler("stop", ai_advisor_cancel)
        ],
        allow_reentry=True
    )
    application.add_handler(ai_conv_handler)
    
    # Message handler for Battle Log Analysis and other messages
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_message
    ))
    
    # Start polling
    logger.info("Bot is running. Press Ctrl+C to stop.")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    keep_alive()
    main()


