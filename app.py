import os
import logging
import sqlite3
import asyncio
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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', '1616739367'))
CHANNEL_ID = '@soliumcoin'
GROUP_ID = '@soliumcoinchat'

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
            logger.info("Database initialized")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

logger.info("Initializing Telegram bot")
try:
    application = Application.builder().token(BOT_TOKEN).build()
    logger.info("Telegram bot initialized")
except Exception as e:
    logger.error(f"Telegram bot initialization error: {e}")
    raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    logger.info(f"Start command: user_id={user.id}, args={args}")
    try:
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
                        logger.info(f"Referral added: user_id={user.id}, referrer_id={referrer_id}")
                except ValueError as e:
                    logger.error(f"Referral parsing error: {e}")
            
            db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)",
                (user.id,)
            )
            db.commit()
            logger.info(f"User added to DB: user_id={user.id}")
        
        await show_menu(update, "🚀 Welcome to Solium Airdrop Bot!")
    except Exception as e:
        logger.error(f"Start command error: {e}")
        raise

async def show_menu(update: Update, text: str):
    logger.info(f"Preparing menu: text={text}")
    try:
        keyboard = [
            [InlineKeyboardButton("💰 Balance", callback_data='balance')],
            [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
            [InlineKeyboardButton("📋 Rules", callback_data='rules')],
            [InlineKeyboardButton("🎁 Claim", callback_data='claim')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        logger.info(f"Menu keyboard: {keyboard}")
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
            logger.info("Menu sent via reply_text")
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            logger.info("Menu sent via edit_message_text")
    except Exception as e:
        logger.error(f"Menu sending error: {e}")
        raise

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    logger.info(f"Button clicked: data={query.data}, user_id={query.from_user.id}")
    try:
        await query.answer()
        if query.data == 'balance':
            with get_db() as db:
                balance = db.execute(
                    "SELECT balance FROM users WHERE user_id = ?",
                    (query.from_user.id,)
                ).fetchone()['balance']
            await query.message.reply_text(f"💰 Your balance: {balance} SOLIUM")
            logger.info(f"Balance sent: user_id={query.from_user.id}, balance={balance}")
        elif query.data == 'referral':
            with get_db() as db:
                referrals = db.execute(
                    "SELECT referrals FROM users WHERE user_id = ?",
                    (query.from_user.id,)
                ).fetchone()['referrals']
            bot_username = (await context.bot.get_me()).username
            await query.message.reply_text(
                f"📢 Your referral link:\n"
                f"https://t.me/{bot_username}?start=ref{query.from_user.id}\n\n"
                f"👥 Total referrals: {referrals}"
            )
            logger.info(f"Referral info sent: user_id={query.from_user.id}, referrals={referrals}")
        elif query.data == 'rules':
            rules = (
                "📋 Airdrop Rules:\n\n"
                "1. Join our Telegram group\n"
                "2. Follow our Telegram channel\n"
                "3. Follow us on X\n"
                "4. Retweet pinned post\n"
                "5. Join WhatsApp channel\n\n"
                "💎 Bonus: 20 SOLIUM per referral!"
            )
            await query.message.reply_text(rules)
            logger.info(f"Rules sent: user_id={query.from_user.id}")
        elif query.data == 'claim':
            await handle_claim(update, context)
        await show_menu(update, "Main Menu:")
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        raise

async def handle_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    logger.info(f"Claim requested: user_id={user_id}")
    try:
        with get_db() as db:
            participated = db.execute(
                "SELECT participated FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()['participated']
            
            if participated:
                await update.callback_query.message.reply_text("🎉 You already claimed!")
                logger.info(f"Claim already done: user_id={user_id}")
            else:
                await show_tasks(update, context)
    except Exception as e:
        logger.error(f"Claim error: {e}")
        raise

async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id
    logger.info(f"Showing tasks: user_id={user_id}")
    try:
        with get_db() as db:
            tasks = db.execute(
                "SELECT task1_completed, task2_completed, task3_completed, "
                "task4_completed, task5_completed FROM users WHERE user_id = ?",
                (user_id,)
            ).fetchone()
        
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
        reply_markup = InlineKeyboardMarkup(keyboard)
        logger.info(f"Tasks keyboard: {keyboard}")
        
        await update.callback_query.edit_message_text(
            "🎯 Complete these tasks:",
            reply_markup=reply_markup
        )
        logger.info(f"Tasks sent: user_id={user_id}")
    except Exception as e:
        logger.error(f"Show tasks error: {e}")
        raise

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Webhook request received")
    try:
        json_data = request.get_json()
        logger.info(f"Webhook data: {json_data}")
        update = Update.de_json(json_data, application.bot)
        asyncio.run(application.process_update(update))
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
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
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
        logger.error(f"Main function error: {e}")
        raise

if __name__ == '__main__':
    logger.info("Running main")
    try:
        asyncio.run(main())
        logger.info("Main executed successfully")
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        raise
