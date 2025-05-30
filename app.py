import os
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')

async def start(update, context):
    logger.info(f"Sending message to chat_id={update.message.chat_id}")
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Rules", callback_data='rules')],
        [InlineKeyboardButton("🎁 Claim", callback_data='claim')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🚀 Welcome to Solium Airdrop Bot!", reply_markup=reply_markup)

async def callback_query(update, context):
    query = update.callback_query
    await query.answer()
    chat_id = query.message.chat_id
    callback_data = query.data
    logger.info(f"Handling callback: data={callback_data}, chat_id={chat_id}")
    try:
        if callback_data == 'balance':
            await query.message.reply_text("💰 Your balance: 0 SOLIUM")
        elif callback_data == 'referral':
            await query.message.reply_text("📢 Your referral link: Coming soon!")
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
            await query.message.reply_text(rules)
        elif callback_data == 'claim':
            await query.message.reply_text("🎯 Claim tasks coming soon!")
    except Exception as e:
        logger.error(f"Callback error: {e}")

def main():
    logger.info("Starting bot")
    app = Application.builder().token(BOT_TOKEN).connection_pool_size(20).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_query))
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path="/webhook",
        webhook_url="https://soliumairdropbot-ef7a2a4b1280-0071788c2efa.herokuapp.com/webhook"
    )

if __name__ == "__main__":
    main()
