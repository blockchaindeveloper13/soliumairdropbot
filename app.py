import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']
PORT = int(os.environ.get('PORT', 8443))
WEBHOOK_URL = f"https://soliumairdropbot-ef7a2a4b1280.herokuapp.com/webhook"

async def start(update: Update, context):
    await update.message.reply_text("Bot çalışıyor! ✅")

async def webhook_handler(request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.update_queue.put(update)
        return web.Response(text="OK")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500)

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))

async def set_webhook():
    await app.bot.set_webhook(
        url=WEBHOOK_URL,
        drop_pending_updates=True
    )
    logger.info("Webhook başarıyla ayarlandı")

async def on_startup(app):
    await set_webhook()

if __name__ == '__main__':
    web_app = web.Application()
    web_app.router.add_post('/webhook', webhook_handler)
    web_app.on_startup.append(on_startup)
    
    runner = web.AppRunner(web_app)
    web.run_app(
        web_app,
        host='0.0.0.0',
        port=PORT,
        reuse_port=True
    )
