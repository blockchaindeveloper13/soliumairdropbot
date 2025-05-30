import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Log ayarı
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ['BOT_TOKEN']

async def start(update: Update, context):
    """Basit bir start handler"""
    await update.message.reply_text('🚀 Bot aktif!')

def main():
    # Uygulamayı oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler'ları ekle
    application.add_handler(CommandHandler("start", start))
    
    # Polling modunda başlat
    application.run_polling()

if __name__ == '__main__':
    main()
