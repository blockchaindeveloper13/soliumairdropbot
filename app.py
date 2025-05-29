import os
import logging
from flask import Flask, request
from telegram import Update, Bot
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)

async def start(chat_id):
    logger.info(f"Sending test message to chat_id={chat_id}")
    try:
        await bot.send_message(chat_id=chat_id, text="Merhaba, test botu çalışıyor!")
        logger.info("Test message sent")
    except Exception as e:
        logger.error(f"Send message error: {e}")

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Webhook request received")
    try:
        json_data = request.get_json()
        logger.info(f"Webhook data: {json_data}")
        update = Update.de_json(json_data, bot)
        if update.message and update.message.text == "/start":
            asyncio.run(start(update.message.chat_id))
        logger.info("Webhook processed")
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

@flask_app.route('/')
def index():
    logger.info("Index page accessed")
    return "🤖 Test Bot Running!"

if __name__ == '__main__':
    logger.info("Starting application")
    port = int(os.environ.get('PORT', 8443))
    flask_app.run(host='0.0.0.0', port=port)
