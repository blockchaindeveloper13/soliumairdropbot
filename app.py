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
    if query.data == 'balance':
        await query.message.reply_text("💰 Your balance: 0 SOLIUM")
    elif query.data == 'referral':
        await query.message.reply_text("📢 Your referral link: Coming soon!")
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
    elif query.data == 'claim':
        await query.message.reply_text("🎯 Claim tasks coming soon!")

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
