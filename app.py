import os
import logging
import sqlite3
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
flask_app = Flask(__name__)

# Configuration
BOT_TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = int(os.environ['ADMIN_ID'])
CHANNEL_ID = '@soliumcoin'
GROUP_ID = '@soliumcoinchat'

# Database setup
def get_db():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                bsc_address TEXT,
                x_username TEXT,
                balance INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                participated BOOLEAN DEFAULT 0,
                referrer_id INTEGER,
                task1_completed BOOLEAN DEFAULT 0,
                task2_completed BOOLEAN DEFAULT 0,
                task3_completed BOOLEAN DEFAULT 0,
                task4_completed BOOLEAN DEFAULT 0,
                task5_completed BOOLEAN DEFAULT 0
            )
        ''')
        db.commit()

# Initialize Telegram bot
application = Application.builder().token(BOT_TOKEN).build()

# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    with get_db() as db:
        if args and args[0].startswith("ref"):
            try:
                referrer_id = int(args[0][3:])
                if referrer_id != user.id:
                    db.execute(
                        "INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)",
                        (user.id, referrer_id)
                    )
                    db.execute(
                        "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
                        (referrer_id,)
                    )
            except ValueError:
                pass
        db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
            (user.id,)
        )
        db.commit()
    
    await show_menu(update, "🚀 Welcome to Solium Airdrop Bot!")

async def show_menu(update: Update, text: str):
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Rules", callback_data='rules')],
        [InlineKeyboardButton("🎁 Claim", callback_data='claim')]
    ]
    
    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
    else:
        await update.callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard))

# ===== FLASK ROUTES =====
@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
    json_data = request.get_json()
    update = Update.de_json(json_data, application.bot)
    await application.process_update(update)
    return '', 200

@flask_app.route('/')
def index():
    return "Bot is running!"

# ===== MAIN SETUP =====
def setup_handlers():
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

def main():
    init_db()
    setup_handlers()
    
    # Set webhook on startup
    webhook_url = f"https://{os.environ['APP_NAME']}.herokuapp.com/{BOT_TOKEN}"
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get('PORT', 8443)),
        webhook_url=webhook_url
    )

if __name__ == '__main__':
    main()
