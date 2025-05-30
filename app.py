import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler
from urllib.parse import urlparse
import psycopg2
from psycopg2 import pool
from aiohttp import web

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
DATABASE_URL = os.environ.get('DATABASE_URL')
BOT_USERNAME = os.environ['BOT_USERNAME']  # Zorunlu ortam değişkeni

# Veritabanı bağlantı havuzu
db_pool = None

def init_db_pool():
    global db_pool
    try:
        url = urlparse(DATABASE_URL)
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,  # Min 1, max 20 bağlantı
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Database pool initialization error: {e}")
        raise

def init_db():
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                referrer_id BIGINT,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        cursor.close()
        db_pool.putconn(conn)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        raise

async def start(update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    referral_id = context.args[0] if context.args else None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (user_id, balance, username) VALUES (%s, %s, %s) ON CONFLICT (user_id) DO NOTHING',
            (user_id, 0, username)
        )
        if referral_id:
            try:
                referral_id = int(referral_id)
                cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (referral_id,))
                if cursor.fetchone():
                    cursor.execute('UPDATE users SET balance = balance + 20 WHERE user_id = %s', (referral_id,))
                    cursor.execute('UPDATE users SET referrer_id = %s WHERE user_id = %s', (referral_id, user_id))
                    logger.info(f"User {user_id} ({username}) joined via referral {referral_id}")
                else:
                    logger.warning(f"Referral ID {referral_id} not found")
            except ValueError:
                logger.error(f"Invalid referral ID: {referral_id}")
        conn.commit()
    except Exception as e:
        logger.error(f"Database error in start: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            db_pool.putconn(conn)
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Rules", callback_data='rules')],
        [InlineKeyboardButton("🎁 Claim", callback_data='claim')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"🚀 Welcome to Solium Airdrop Bot, {username}!", reply_markup=reply_markup)

async def balance(update, context):
    user_id = update.effective_user.id
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = %s', (user_id,))
        result = cursor.fetchone()
        balance = result[0] if result else 0
        cursor.close()
        db_pool.putconn(conn)
        await update.message.reply_text(f"💰 Your balance: {balance} SOLIUM")
    except Exception as e:
        logger.error(f"Database error in balance: {e}")
        await update.message.reply_text("❌ Error fetching balance.")

async def referral(update, context):
    user_id = update.effective_user.id
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = %s', (user_id,))
        referral_count = cursor.fetchone()[0]
        cursor.close()
        db_pool.putconn(conn)
        await update.message.reply_text(
            f"📢 Your referral link: {referral_link}\n"
            f"Invite friends to earn 20 SOLIUM per referral!\n"
            f"You have {referral_count} referrals."
        )
    except Exception as e:
        logger.error(f"Database error in referral: {e}")
        await update.message.reply_text(
            f"📢 Your referral link: {referral_link}\n"
            f"Invite friends to earn 20 SOLIUM per referral!"
        )

async def callback_query(update, context):
    query = update.callback_query
    await query.answer()
    if query.data == 'balance':
        await balance(update, context)
    elif query.data == 'referral':
        await referral(update, context)
    elif query.data == 'rules':
        rules = (
            "📋 Airdrop Rules:\n\n"
            "1. Join our Telegram group: [your_group_link]\n"
            "2. Follow our Telegram channel: [your_channel_link]\n"
            "3. Follow us on X: [your_x_link]\n"
            "4. Retweet pinned post\n"
            "5. Join WhatsApp channel: [your_whatsapp_link]\n\n"
            "💎 Bonus: 20 SOLIUM per referral!"
        )
        await query.message.reply_text(rules)
    elif query.data == 'claim':
        await query.message.reply_text("🎯 Claim tasks coming soon! Check rules for tasks.")

async def handle_webhook(request):
    app = request.app['telegram_app']
    update = await request.json()
    await app.update_queue.put(update)
    return web.Response()

def main():
    logger.info("Starting bot")
    init_db_pool()
    init_db()
    app = Application.builder().token(BOT_TOKEN).connection_pool_size(20).concurrent_updates(True).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("referral", referral))
    app.add_handler(CallbackQueryHandler(callback_query))
    
    # aiohttp web uygulaması
    web_app = web.Application()
    web_app['telegram_app'] = app
    web_app.router.add_post('/webhook', handle_webhook)
    
    # Webhook ayarları
    port = int(os.environ.get("PORT", 8443))
    webhook_url = "https://soliumairdropbot-ef7a2a4b1280.herokuapp.com/webhook"
    
    # Web uygulamasını başlat
    web.run_app(web_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
