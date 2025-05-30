import os
import logging
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler

# Log ayarı
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']
WEBHOOK_URL = "https://soliumairdropbot-ef7a2a4b1280.herokuapp.com/webhook"
PORT = int(os.environ.get('PORT', 8443))

# Telegram uygulaması
app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context):
    await update.message.reply_text("BOT AKTİF! ✅")

# Handler'lar
app.add_handler(CommandHandler("start", start))

async def webhook_handler(request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook hatası: {e}")
        return web.Response(status=500)

async def init_webhook():
    await app.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    logger.info(f"Webhook ayarlandı: {WEBHOOK_URL}")

if __name__ == '__main__':
    # aiohttp sunucusu
    server = web.Application()
    server.router.add_post('/webhook', webhook_handler)
    
    # Başlangıç işlemleri
    app.run_polling()  # Bu satırı geçici olarak ekliyoruz
    
    # Webhook moduna geçiş
    web.run_app(
        server,
        host='0.0.0.0',
        port=PORT,
        print=lambda _: logger.info(f"Sunucu {PORT} portunda başlatıldı")
    )
