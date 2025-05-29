import os
import logging
import sqlite3
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

logger.info("Loading configuration")
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    ADMIN_ID = int(os.environ['ADMIN_ID'])
    CHANNEL_ID = '@soliumcoin'
    GROUP_ID = '@soliumcoinchat'
    logger.info("Configuration loaded")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    raise

def get_db():
    logger.info("Connecting to database")
    try:
        conn = sqlite3.connect('users.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        logger.info("Database connection successful")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

def init_db():
    logger.info("Initializing database")
    try:
        with get_db() as db:
            db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    bsc_address TEXT,
                    x_username TEXT,
                    balance INTEGER DEFAULT 0,
                    referrals INTEGER DEFAULT 0,
                    participated BOOLEAN DEFAULT FALSE,
                    referrer_id INTEGER,
                    task1_completed BOOLEAN DEFAULT FALSE,
                    task2_completed BOOLEAN DEFAULT FALSE,
                    task3_completed BOOLEAN DEFAULT FALSE,
                    task4_completed BOOLEAN DEFAULT FALSE,
                    task5_completed BOOLEAN DEFAULT FALSE
                )
            ''')
            db.commit()
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

logger.info("Initializing Telegram bot")
try:
    application = Bot(token=BOT_TOKEN)
    logger.info("Telegram bot initialized")
except Exception as e:
    logger.error(f"Telegram bot initialization error: {e}")
    raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Start command: user_id={user.id}")
    try:
        await context.bot.send_message(chat_id=user.id, text="🌟 Test Bot is alive!")
        logger.info(f"Test message sent: user_id={user.id}")
    except Exception as e:
        logger.error(f"Start command error: {e}")
        raise

@flask_app.route('/webhook', methods=['POST'])
async def webhook():
    logger.info("Webhook request received")
    try:
        json_data = request.get_json()
        logger.info(f"Webhook data: {json_data}")
        update = Update.de_json(json_data, application)
        await application.process_update(update)
        logger.info("Webhook processed")
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

@flask_app.route('/')
def index():
    logger.info("Index page accessed")
    try:
        return "🤖 Bot is running!"
    except Exception as e:
        logger.error(f"Index error: {e}")
        raise

def setup_handlers():
    logger.info("Setting up handlers")
    try:
        from telegram.ext import Dispatcher
        dispatcher = Dispatcher(bot=application, update_queue=None)
        dispatcher.add_handler(CommandHandler("start", start))
        logger.info("Handlers set up successfully")
    except Exception as e:
        logger.error(f"Handler setup error: {e}")
        raise

async def main():
    logger.info("Starting application")
    try:
        init_db()
        setup_handlers()
        
        port = int(os.environ.get('PORT', 8443))
        flask_app.run(host='0.0.0.0', port=port)
        logger.info("Application started")
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        raise

if __name__ == '__main__':
    logger.info("Running main")
    try:
        asyncio.run(main())
        logger.info("Main executed successfully")
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        raise
