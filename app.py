import os
from aiohttp import web
from telegram import Update
from telegram.ext import Application, CommandHandler

BOT_TOKEN = os.environ['BOT_TOKEN']
WEBHOOK_URL = "https://soliumairdropbot-ef7a2a4b1280.herokuapp.com/webhook"

async def start(update: Update, context):
    await update.message.reply_text("BOT ÇALIŞIYOR! ✅")

app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))

async def webhook_handler(request):
    try:
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")
    except Exception as e:
        print(f"HATA: {e}")
        return web.Response(status=500)

async def init_app():
    # Webhooku ayarla
    await app.bot.set_webhook(WEBHOOK_URL)
    print(f"Webhook ayarlandı: {WEBHOOK_URL}")
    
    # aiohttp uygulaması
    server = web.Application()
    server.router.add_post('/webhook', webhook_handler)
    return server

if __name__ == '__main__':
    web.run_app(init_app(), host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))
