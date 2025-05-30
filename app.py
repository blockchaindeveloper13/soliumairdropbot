import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import re

# Log ayarları
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Ortam değişkenleri
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat')

# Veritabanı bağlantısı
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Veritabanı tablosunu oluştur
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, 
                  bsc_address TEXT, 
                  balance INTEGER DEFAULT 0, 
                  referrals INTEGER DEFAULT 0, 
                  participated BOOLEAN DEFAULT 0,
                  current_task INTEGER DEFAULT 1,
                  referrer_id INTEGER)''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    referrer_id = None
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kullanıcıyı veritabanına ekle veya güncelle
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user['participated']:
        await update.message.reply_text("🎉 Zaten airdropa katıldınız! Tekrar katılamazsınız.")
        conn.close()
        return
    
    if args and args[0].startswith("ref"):
        try:
            referrer_id = int(args[0][3:])
            if referrer_id != user_id:
                # Referans verenin referans sayısını artır
                c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
                c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))
                
                # Yeni kullanıcıya referans bonusu ekle
                c.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, balance, referrer_id) 
                    VALUES (?, 20, ?)
                """, (user_id, referrer_id))
                
                await update.message.reply_text(
                    "🎉 Referans bağlantısıyla giriş yaptınız! "
                    "Hem size hem de referans verene 20 Solium eklendi."
                )
            else:
                c.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id) 
                    VALUES (?)
                """, (user_id,))
        except ValueError:
            c.execute("""
                INSERT OR IGNORE INTO users 
                (user_id) 
                VALUES (?)
            """, (user_id,))
    else:
        c.execute("""
            INSERT OR IGNORE INTO users 
            (user_id) 
            VALUES (?)
        """, (user_id,))
    
    conn.commit()
    conn.close()
    await show_task(update, context, 1)  # İlk görevi göster

async def show_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_number: int):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    tasks = [
        {
            'title': "1️⃣ Telegram Grubuna Katıl",
            'description': f"Resmi Telegram grubumuza katılın: {GROUP_ID}",
            'button': "Katıldım ✅"
        },
        {
            'title': "2️⃣ Telegram Kanalını Takip Et",
            'description': f"Resmi Telegram kanalımızı takip edin: {CHANNEL_ID}",
            'button': "Takip Ediyorum ✅"
        },
        {
            'title': "3️⃣ X (Twitter) Hesabını Takip Et",
            'description': "Resmi X hesabımızı takip edin: @soliumcoin",
            'button': "Takip Ediyorum ✅"
        },
        {
            'title': "4️⃣ Sabitlenmiş Postu Retweet Yap",
            'description': "X'teki sabitlenmiş postumuzu retweet yapın",
            'button': "Retweet Yaptım ✅"
        },
        {
            'title': "5️⃣ BSC Cüzdan Adresinizi Girin",
            'description': "Ödüllerin gönderileceği BSC cüzdan adresinizi girin",
            'button': "Adresimi Giriyorum"
        }
    ]
    
    if task_number <= len(tasks):
        task = tasks[task_number-1]
        
        keyboard = [[InlineKeyboardButton(task['button'], callback_data=f'task_done_{task_number}')]]
        
        if task_number > 1:
            keyboard.append([InlineKeyboardButton("◀️ Önceki Görev", callback_data=f'task_{task_number-1}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"🎯 Görev {task_number}/{len(tasks)}\n\n{task['title']}\n\n{task['description']}"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        # Tüm görevler tamamlandı
        await complete_airdrop(update, context)

async def complete_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Bakiyeyi güncelle (100 Solium ödül)
    c.execute("UPDATE users SET balance = balance + 100, participated = 1 WHERE user_id = ?", (user_id,))
    
    # Referans varsa bonus ekle
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer = c.fetchone()
    if referrer and referrer['referrer_id']:
        c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer['referrer_id'],))
        await context.bot.send_message(
            referrer['referrer_id'],
            "🎉 Bir referansınız airdropu tamamladı! +20 Solium kazandınız."
        )
    
    conn.commit()
    
    # Kullanıcıya bilgi ver
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = c.fetchone()['balance']
    
    await (update.message or update.callback_query.message).reply_text(
        f"🎉 TEBRİKLER! Airdropu başarıyla tamamladınız!\n\n"
        f"💵 Toplam Kazanç: {balance} Solium\n\n"
        f"Ödüller dağıtım sırasında kayıtlı cüzdan adresinize gönderilecektir."
    )
    
    conn.close()

async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Kullanıcının durumunu kontrol et
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user['participated']:
        await query.message.reply_text("❌ Zaten airdropa katıldınız! Tekrar katılamazsınız.")
        conn.close()
        return
    
    if data.startswith('task_'):
        # Görev değiştirme butonu
        task_number = int(data.split('_')[1])
        await show_task(update, context, task_number)
    
    elif data.startswith('task_done_'):
        # Görev tamamlama butonu
        task_number = int(data.split('_')[2])
        
        if task_number == 5:  # Cüzdan adresi isteme
            await query.message.reply_text(
                "💰 Lütfen BSC (Binance Smart Chain) cüzdan adresinizi gönderin:\n\n"
                "Örnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F\n\n"
                "⚠️ Dikkat: Yanlış adres girerseniz ödüllerinizi alamazsınız!"
            )
            context.user_data['awaiting_wallet'] = True
        else:
            # Diğer görevler için onay mesajı
            await query.message.reply_text(
                "✅ Görev tamamlandı! Adminler tarafından kontrol edilecektir.\n\n"
                "Bir sonraki göreve geçebilirsiniz."
            )
        
        # Bir sonraki göreve geç
        next_task = task_number + 1
        c.execute("UPDATE users SET current_task = ? WHERE user_id = ?", (next_task, user_id))
        conn.commit()
        
        if task_number != 5:  # Cüzdan adresi istemiyorsak sonraki göster
            await show_task(update, context, next_task)
    
    conn.close()

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    if not context.user_data.get('awaiting_wallet'):
        return
    
    if re.match(r'^0x[a-fA-F0-9]{40}$', text):
        conn = get_db_connection()
        c = conn.cursor()
        
        # Cüzdan adresini kaydet
        c.execute("UPDATE users SET bsc_address = ? WHERE user_id = ?", (text, user_id))
        conn.commit()
        
        # Son görevi tamamla ve airdropu bitir
        c.execute("UPDATE users SET current_task = 6 WHERE user_id = ?", (user_id,))
        conn.commit()
        
        await update.message.reply_text(
            "✅ Cüzdan adresiniz başarıyla kaydedildi!\n\n"
            "Şimdi airdropu tamamlamak için son adıma geçiyoruz..."
        )
        
        await complete_airdrop(update, context)
        context.user_data['awaiting_wallet'] = False
        conn.close()
    else:
        await update.message.reply_text(
            "❌ Geçersiz BSC cüzdan adresi formatı!\n\n"
            "Lütfen şu formatta bir adres girin:\n"
            "0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        )

async def export_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    
    if not addresses:
        await update.message.reply_text("❌ Kayıtlı cüzdan adresi bulunamadı!")
        conn.close()
        return
    
    # Geçici dosya oluştur
    filename = "bsc_addresses.txt"
    with open(filename, 'w') as f:
        for addr in addresses:
            f.write(f"{addr['user_id']}: {addr['bsc_address']}\n")
    
    # Dosyayı gönder
    try:
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption=f"📋 Toplam {len(addresses)} adet BSC cüzdan adresi"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Dosya gönderilirken hata: {str(e)}")
    finally:
        # Geçici dosyayı sil
        try:
            os.remove(filename)
        except:
            pass
    
    conn.close()

def main():
    # Veritabanını başlat
    init_db()
    
    # Uygulamayı oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler'ları ekle
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('export', export_addresses))
    application.add_handler(CallbackQueryHandler(handle_task_button, pattern='^(task_|task_done_)'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    
    # Polling modunda başlat
    logger.info("🚀 Bot polling modunda başlatılıyor...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=['message', 'callback_query']
    )

if __name__ == '__main__':
    main()
