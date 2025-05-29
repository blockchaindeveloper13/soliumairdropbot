import os
import logging
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
import asyncio

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)

logger.info("Loading BOT_TOKEN")
BOT_TOKEN = os.environ.get('BOT_TOKEN')
logger.info("Initializing bot")
bot = Bot(token=BOT_TOKEN)
logger.info("Bot initialized")

async def start(chat_id):
    logger.info(f"Sending message to chat_id={chat_id}")
    try:
        keyboard = [
            [InlineKeyboardButton("💰 Balance", callback_data='balance')],
            [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
            [InlineKeyboardButton("📋 Rules", callback_data='rules')],
            [InlineKeyboardButton("🎁 Claim", callback_data='claim')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot.send_message(
            chat_id=chat_id,
            text="🚀 Welcome to Solium Airdrop Bot!",
            reply_markup=reply_markup
        )
        logger.info("Message with menu sent")
    except Exception as e:
        logger.error(f"Message error: {e}")

async def handle_callback(chat_id, callback_data, message_id):
    logger.info(f"Handling callback: data={callback_data}, chat_id={chat_id}")
    try:
        if callback_data == 'balance':
            await bot.send_message(chat_id=chat_id, text="💰 Your balance: 0 SOLIUM")
        elif callback_data == 'referral':
            await bot.send_message(chat_id=chat_id, text="📢 Your referral link: Coming soon!")
        elif callback_data == 'rules':
            rules = (
                "📋 Airdrop Rules:\n\n"
                "1. Join our Telegram group\n"
                "2. Follow our Telegram channel\n"
                "3. Follow us on X\n"
                "4. Retweet pinned post\n"
                "5. Join WhatsApp channel\n\n"
                "💎 Bonus: 20 SOLIUM per referral!"
            )
            await bot.send_message(chat_id=chat_id, text=rules)
        elif callback_data == 'claim':
            await bot.send_message(chat_id=chat_id, text="🎯 Claim tasks coming soon!")
        logger.info("Callback handled")
    except Exception as e:
        logger.error(f"Callback error: {e}")

@flask_app.route('/webhook', methods=['POST'])
def webhook():
    logger.info("Webhook received")
    try:
        json_data = request.get_json()
        logger.info(f"Webhook data: {json_data}")
        update = Update.de_json(json_data, bot)
        if update.message and update.message.text == "/start":
            asyncio.run(start(update.message.chat_id))
        elif update.callback_query:
            asyncio.run(handle_callback(
                update.callback_query.message.chat_id,
                update.callback_query.data,
                update.callback_query.message.message_id
            ))
        logger.info("Webhook processed")
        return '', 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return '', 500

@flask_app.route('/')
def index():
    logger.info("Index accessed")
    return "🤖 Bot Running!"

if __name__ == '__main__':
    logger.info("Starting app")
    port = int(os.environ.get('PORT', 8443))
    flask_app.run(host='0.0.0.0', port=port)
