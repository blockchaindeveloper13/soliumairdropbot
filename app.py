import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from urllib.parse import urlparse
import psycopg2
from psycopg2 import pool
from aiohttp import web

# Log ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Config
BOT_TOKEN = os.environ['BOT_TOKEN']
DATABASE_URL = os.environ['DATABASE_URL']
BOT_USERNAME = os.environ['BOT_USERNAME']
APP_NAME = os.environ['APP_NAME']

# Veritabanı bağlantı havuzu
db_pool = None

def init_db_pool():
    global db_pool
    try:
        url = urlparse(DATABASE_URL)
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        logger.info("Veritabanı bağlantı havuzu oluşturuldu")
    except Exception as e:
        logger.error(f"Veritabanı havuz hatası: {e}")
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
        logger.info("Veritabanı tablosu oluşturuldu")
    except Exception as e:
        logger.error(f"Veritabanı başlatma hatası: {e}")
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            db_pool.putconn(conn)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or f"User_{user_id}"
    referans_id = context.args[0] if context.args else None
    
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        # Kullanıcıyı veritabanına ekle
        cursor.execute(
            'INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
            (user_id, username)
        )
        
        # Referans kontrolü
        if referans_id:
            try:
                referans_id = int(referans_id)
                cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (referans_id,))
                if cursor.fetchone():
                    cursor.execute('UPDATE users SET balance = balance + 20 WHERE user_id = %s', (referans_id,))
                    cursor.execute('UPDATE users SET referrer_id = %s WHERE user_id = %s', (referans_id, user_id))
                    logger.info(f"{user_id} ID'li kullanıcı {referans_id} referansıyla kaydoldu")
            except ValueError:
                logger.error(f"Geçersiz referans ID: {referans_id}")
        
        conn.commit()
    except Exception as e:
        logger.error(f"Başlangıç hatası: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            db_pool.putconn(conn)
    
    # Menüyü göster
    klavye = [
        [InlineKeyboardButton("💰 Bakiye", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referans", callback_data='referral')],
        [InlineKeyboardButton("📋 Kurallar", callback_data='rules')],
        [InlineKeyboardButton("🎁 Talep Et", callback_data='claim')]
    ]
    await update.message.reply_text(
        f"Merhaba {user.first_name}! 🚀\n\nSolium Airdrop Botuna hoş geldin!",
        reply_markup=InlineKeyboardMarkup(klavye)
    )

async def bakiye(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = %s', (user_id,))
        bakiye = cursor.fetchone()[0] or 0
        await update.message.reply_text(f"💰 Bakiyeniz: {bakiye} SOLIUM")
    except Exception as e:
        logger.error(f"Bakiye hatası: {e}")
        await update.message.reply_text("❌ Bakiye bilgisi alınamadı")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            db_pool.putconn(conn)

async def referans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    referans_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users WHERE referrer_id = %s', (user_id,))
        referans_sayisi = cursor.fetchone()[0]
        await update.message.reply_text(
            f"📢 Referans Linkiniz: {referans_link}\n"
            f"Davet ettiğiniz her kişi için 20 SOLIUM kazanırsınız!\n"
            f"Toplam referans sayınız: {referans_sayisi}"
        )
    except Exception as e:
        logger.error(f"Referans hatası: {e}")
        await update.message.reply_text(
            f"📢 Referans Linkiniz: {referans_link}\n"
            f"Davet ettiğiniz her kişi için 20 SOLIUM kazanırsınız!"
        )
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            db_pool.putconn(conn)

async def kurallar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kurallar_metni = (
        "📋 Airdrop Kuralları:\n\n"
        "1. Telegram grubumuza katılın\n"
        "2. Telegram kanalımızı takip edin\n"
        "3. X hesabımızı takip edin\n"
        "4. Sabitlenmiş postu retweetleyin\n"
        "5. WhatsApp kanalına katılın\n\n"
        "💎 Bonus: Her referans için 20 SOLIUM kazanın!"
    )
    await update.message.reply_text(kurallar_metni)

async def talep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Talep işlemleri yakında aktif olacak!")

async def buton_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sorgu = update.callback_query
    await sorgu.answer()
    
    if sorgu.data == 'balance':
        await bakiye(update, context)
    elif sorgu.data == 'referral':
        await referans(update, context)
    elif sorgu.data == 'rules':
        await kurallar(update, context)
    elif sorgu.data == 'claim':
        await talep(update, context)

async def webhook_handler(request):
    try:
        data = await request.json()
        update = Update.de_json(data, request.app['telegram_app'].bot)
        await request.app['telegram_app'].process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook hatası: {e}")
        return web.Response(status=500, text="Sunucu hatası")

async def ana_sayfa(request):
    return web.Response(text="🤖 Solium Airdrop Botu Aktif!")

def main():
    logger.info("Bot başlatılıyor...")
    init_db_pool()
    init_db()
    
    # Telegram uygulamasını oluştur
    telegram_app = Application.builder().token(BOT_TOKEN).build()
    
    # Handler'ları ekle
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CommandHandler("bakiye", bakiye))
    telegram_app.add_handler(CommandHandler("referans", referans))
    telegram_app.add_handler(CallbackQueryHandler(buton_handler))
    
    # aiohttp uygulamasını oluştur
    web_app = web.Application()
    web_app['telegram_app'] = telegram_app
    
    # Webhook endpointini ayarla (BOT_TOKEN ile)
    web_app.router.add_post(f'/{BOT_TOKEN}', webhook_handler)
    web_app.router.add_get('/', ana_sayfa)
    
    port = int(os.environ.get("PORT", 8443))
    webhook_url = f"https://{APP_NAME}.herokuapp.com/{BOT_TOKEN}"
    
    async def baslangic(app):
        await telegram_app.initialize()
        await telegram_app.bot.set_webhook(webhook_url)
        logger.info(f"Webhook başarıyla ayarlandı: {webhook_url}")
    
    web_app.on_startup.append(baslangic)
    
    logger.info(f"Sunucu {port} portunda başlatılıyor...")
    web.run_app(web_app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
