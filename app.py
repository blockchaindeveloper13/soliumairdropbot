import os
import logging
import sqlite3
import re
import json
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    Dispatcher
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
flask_app = Flask(__name__)

# Environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1616739367'))
CHANNEL_ID = '@soliumcoin'
GROUP_ID = '@soliumcoinchat'
APP_NAME = os.environ.get('APP_NAME')

# Database setup
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db_connection() as conn:
        conn.execute('''
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
        conn.commit()

# Initialize Telegram bot
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# ========== HANDLER FUNCTIONS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if args and args[0].startswith("ref"):
            try:
                referrer_id = int(args[0][3:])
                if referrer_id != user.id:
                    cursor.execute(
                        "INSERT OR IGNORE INTO users (user_id, referrer_id) VALUES (?, ?)",
                        (user.id, referrer_id)
                    )
                    cursor.execute(
                        "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
                        (referrer_id,)
                    )
            except ValueError:
                pass
        else:
            cursor.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user.id,)
            )
        conn.commit()
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Airdrop Rules", callback_data='terms')],
        [InlineKeyboardButton("🎁 Claim Airdrop", callback_data='airdrop')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(
            "🚀 Welcome to Solium Airdrop Bot! Choose an option:",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.edit_message_text(
            "Main Menu:",
            reply_markup=reply_markup
        )

# ========== CALLBACK HANDLERS ==========

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        if query.data == 'balance':
            cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
            balance = cursor.fetchone()['balance']
            await query.message.reply_text(f"💰 Your balance: {balance} SOLIUM")
            
        elif query.data == 'referral':
            cursor.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
            referrals = cursor.fetchone()['referrals']
            bot_username = (await context.bot.get_me()).username
            await query.message.reply_text(
                f"📢 Your referral link:\n"
                f"https://t.me/{bot_username}?start=ref{user_id}\n\n"
                f"👥 Total referrals: {referrals}"
            )
            
        elif query.data == 'terms':
            terms = (
                "📋 Airdrop Requirements:\n\n"
                "1. Join Telegram group (@soliumcoinchat)\n"
                "2. Follow Telegram channel (@soliumcoin)\n"
                "3. Follow X account (@soliumcoin)\n"
                "4. Retweet pinned post\n"
                "5. Join WhatsApp channel\n\n"
                "💎 Bonus: 20 SOLIUM per referral!"
            )
            await query.message.reply_text(terms)
            
        elif query.data == 'airdrop':
            cursor.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
            if cursor.fetchone()['participated']:
                await query.message.reply_text("🎉 You already participated!")
            else:
                await show_tasks(update, context)
    
    await show_main_menu(update, context)

# ========== TASK MANAGEMENT ==========

async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT task1_completed, task2_completed, task3_completed, "
            "task4_completed, task5_completed FROM users WHERE user_id = ?",
            (user_id,)
        )
        tasks = cursor.fetchone()
    
    keyboard = []
    for i in range(1, 6):
        completed = tasks[f'task{i}_completed']
        keyboard.append([
            InlineKeyboardButton(
                f"{i}. Task {i} {'✅' if completed else '❌'}",
                callback_data=f'task{i}'
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔍 Verify Tasks", callback_data='verify')])
    
    await update.callback_query.edit_message_text(
        "🎯 Complete these tasks:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ========== FLASK ROUTES ==========

@flask_app.route(f'/{BOT_TOKEN}', methods=['POST'])
async def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(), bot)
        await application.process_update(update)
    return "ok", 200

@flask_app.route('/')
def index():
    return "🤖 Bot is running! Set webhook at /setwebhook"

@flask_app.route('/setwebhook')
async def set_webhook():
    webhook_url = f"https://{APP_NAME}.herokuapp.com/{BOT_TOKEN}"
    await bot.set_webhook(webhook_url)
    return f"Webhook set to: {webhook_url}"

# ========== MAIN SETUP ==========

def main():
    # Initialize database
    init_db()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start Flask app
    port = int(os.environ.get('PORT', 8443))
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
