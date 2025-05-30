import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import sqlite3
import json
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
                  x_username TEXT, 
                  balance INTEGER DEFAULT 0, 
                  referrals INTEGER DEFAULT 0, 
                  participated BOOLEAN DEFAULT 0, 
                  referrer_id INTEGER,
                  task1_completed BOOLEAN DEFAULT 0, 
                  task2_completed BOOLEAN DEFAULT 0, 
                  task3_completed BOOLEAN DEFAULT 0, 
                  task4_completed BOOLEAN DEFAULT 0, 
                  task5_completed BOOLEAN DEFAULT 0)''')
    conn.commit()
    conn.close()

# /start komutu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    referrer_id = None
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if args and args[0].startswith("ref"):
        try:
            referrer_id = int(args[0][3:])
            if referrer_id != user_id:
                c.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id, balance, referrals, participated, referrer_id) 
                    VALUES (?, 0, 0, 0, ?)
                """, (user_id, referrer_id))
                # Referans verenin referans sayısını artır
                c.execute("""
                    UPDATE users SET referrals = referrals + 1 
                    WHERE user_id = ?
                """, (referrer_id,))
            else:
                c.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id, balance, referrals, participated) 
                    VALUES (?, 0, 0, 0)
                """, (user_id,))
        except ValueError:
            c.execute("""
                INSERT OR IGNORE INTO users 
                (user_id, balance, referrals, participated) 
                VALUES (?, 0, 0, 0)
            """, (user_id,))
    else:
        c.execute("""
            INSERT OR IGNORE INTO users 
            (user_id, balance, referrals, participated) 
            VALUES (?, 0, 0, 0)
        """, (user_id,))
    
    conn.commit()
    conn.close()
    await show_main_menu(update, context)

# Ana menüyü göster
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Airdrop Şartları", callback_data='terms')],
        [InlineKeyboardButton("🎁 Airdrop Kazan", callback_data='airdrop')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text("🚀 Solium Airdrop Botuna Hoşgeldin! Menüden bir seçenek seç:", reply_markup=reply_markup)
    else:
        await update.callback_query.message.edit_text("🚀 Solium Airdrop Botu - Ana Menü:", reply_markup=reply_markup)

# Buton callback'leri
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    conn = get_db_connection()
    c = conn.cursor()

    if query.data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        balance = result['balance'] if result else 0
        await query.message.reply_text(f"💰 Toplam Bakiyen: {balance} Solium")
        
    elif query.data == 'referral':
        c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        referrals = result['referrals'] if result else 0
        await query.message.reply_text(
            f"📢 Referans Bilgileri:\n\n"
            f"🔗 Referans Linkin: https://t.me/{context.bot.username}?start=ref{user_id}\n"
            f"👥 Davet Ettiğin Kişi Sayısı: {referrals}\n\n"
            f"Her davet ettiğin kişi için 20 Solium kazanırsın!"
        )
        
    elif query.data == 'terms':
        terms = (
            "📋 Airdrop Şartları:\n\n"
            "1️⃣ Telegram grubuna katıl (@soliumcoinchat) - 20 Solium\n"
            "2️⃣ Telegram kanalını takip et (@soliumcoin) - 20 Solium\n"
            "3️⃣ X hesabını takip et (@soliumcoin) - 20 Solium\n"
            "4️⃣ X pinned postu RT yap - 20 Solium\n"
            "5️⃣ WhatsApp kanalına katıl - 20 Solium\n\n"
            "💎 Bonus: Her davet ettiğin arkadaşın için 20 Solium kazanırsın!\n"
            "Arkadaşın görevleri tamamlarsa ekstra 20 Solium daha kazanırsın!"
        )
        await query.message.reply_text(terms)
        
    elif query.data == 'airdrop':
        c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        participated = result['participated'] if result else False
        
        if participated:
            await query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        else:
            await show_tasks(update, context)
    
    conn.close()
    await show_main_menu(update, context)

# Görevleri göster
async def show_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed 
        FROM users WHERE user_id = ?
    """, (user_id,))
    tasks = c.fetchone()
    
    keyboard = [
        [
            InlineKeyboardButton(
                f"1. Telegram Grubu {'✅' if tasks['task1_completed'] else '❌'}",
                callback_data='task1'
            )
        ],
        [
            InlineKeyboardButton(
                f"2. Telegram Kanalı {'✅' if tasks['task2_completed'] else '❌'}",
                callback_data='task2'
            )
        ],
        [
            InlineKeyboardButton(
                f"3. X Hesabı Takip {'✅' if tasks['task3_completed'] else '❌'}",
                callback_data='task3'
            )
        ],
        [
            InlineKeyboardButton(
                f"4. X Post RT {'✅' if tasks['task4_completed'] else '❌'}",
                callback_data='task4'
            ) if tasks['task3_completed'] else None
        ],
        [
            InlineKeyboardButton(
                f"5. WhatsApp Kanalı {'✅' if tasks['task5_completed'] else '❌'}",
                callback_data='task5'
            )
        ],
        [InlineKeyboardButton("🔍 Görevleri Kontrol Et", callback_data='check_tasks')]
    ]
    
    # None olan butonları filtrele
    keyboard = [row for row in keyboard if row[0] is not None]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(
        "🎯 Airdrop Görevleri:\n\n"
        "Aşağıdaki görevleri tamamlayarak Solium kazanabilirsin!\n"
        "Görevleri tamamladıktan sonra 'Görevleri Kontrol Et' butonuna bas.",
        reply_markup=reply_markup
    )
    conn.close()

# Görev kontrol
async def check_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed, participated 
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = c.fetchone()
    
    if result['participated']:
        await query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        conn.close()
        return
    
    all_tasks_completed = all([
        result['task1_completed'],
        result['task2_completed'],
        result['task3_completed'],
        result['task4_completed'],
        result['task5_completed']
    ])
    
    if all_tasks_completed:
        # Referans bonusu ekle
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer_id = c.fetchone()['referrer_id'] if c.fetchone() else None
        
        if referrer_id:
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))
        
        # Kullanıcıya ödül ekle
        c.execute("""
            UPDATE users 
            SET balance = balance + 100, participated = 1 
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        
        await query.message.reply_text(
            "🎉 TEBRİKLER! Tüm görevleri tamamladın!\n\n"
            "Toplam kazandığın: 100 Solium\n"
            "BSC cüzdan adresini göndermek için /wallet yaz."
        )
    else:
        await query.message.reply_text(
            "❌ Henüz tüm görevleri tamamlamadın!\n\n"
            "Görevleri tamamladığından emin ol ve tekrar kontrol et."
        )
    
    conn.close()
    await show_main_menu(update, context)

# Görev işleme
async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    participated = c.fetchone()['participated']
    
    if participated:
        await query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        conn.close()
        return
    
    task_data = query.data
    
    if task_data == 'task1':
        try:
            member = await context.bot.get_chat_member(GROUP_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("""
                    UPDATE users 
                    SET task1_completed = 1, balance = balance + 20 
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                await query.message.reply_text(
                    "✅ Telegram grubu görevi tamamlandı!\n"
                    "+20 Solium kazandın!"
                )
            else:
                await query.message.reply_text(
                    f"❌ {GROUP_ID} grubuna katılmamışsın!\n\n"
                    f"Gruba katıldıktan sonra tekrar dene."
                )
        except Exception as e:
            logger.error(f"Telegram grup kontrol hatası: {e}")
            await query.message.reply_text(
                "❌ Grup kontrolü sırasında bir hata oluştu!\n"
                "Lütfen daha sonra tekrar dene."
            )
    
    elif task_data == 'task2':
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("""
                    UPDATE users 
                    SET task2_completed = 1, balance = balance + 20 
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                await query.message.reply_text(
                    "✅ Telegram kanalı görevi tamamlandı!\n"
                    "+20 Solium kazandın!"
                )
            else:
                await query.message.reply_text(
                    f"❌ {CHANNEL_ID} kanalına katılmamışsın!\n\n"
                    f"Kanala katıldıktan sonra tekrar dene."
                )
        except Exception as e:
            logger.error(f"Telegram kanal kontrol hatası: {e}")
            await query.message.reply_text(
                "❌ Kanal kontrolü sırasında bir hata oluştu!\n"
                "Lütfen daha sonra tekrar dene."
            )
    
    elif task_data == 'task3':
        await query.message.reply_text(
            "🔍 X (Twitter) hesabını takip ettiğini doğrulamak için\n\n"
            "Lütfen X kullanıcı adını (@ ile başlayarak) gönder:\n"
            "Örnek: @soliumcoin"
        )
        context.user_data['awaiting_x_username'] = True
    
    elif task_data == 'task4':
        c.execute("""
            UPDATE users 
            SET task4_completed = 1, balance = balance + 20 
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        await query.message.reply_text(
            "✅ X pinned post RT görevi kaydedildi!\n"
            "+20 Solium kazandın!\n\n"
            "Not: Adminler tarafından manuel olarak kontrol edilecektir."
        )
    
    elif task_data == 'task5':
        c.execute("""
            UPDATE users 
            SET task5_completed = 1, balance = balance + 20 
            WHERE user_id = ?
        """, (user_id,))
        conn.commit()
        await query.message.reply_text(
            "✅ WhatsApp kanalı görevi kaydedildi!\n"
            "+20 Solium kazandın!\n\n"
            "Not: Adminler tarafından manuel olarak kontrol edilecektir."
        )
    
    conn.close()
    await show_tasks(update, context)

# Cüzdan adresi alma
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT participated, bsc_address, 
               task1_completed, task2_completed, task3_completed, 
               task4_completed, task5_completed 
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = c.fetchone()
    
    if not result['participated']:
        all_tasks_completed = all([
            result['task1_completed'],
            result['task2_completed'],
            result['task3_completed'],
            result['task4_completed'],
            result['task5_completed']
        ])
        
        if not all_tasks_completed:
            await update.message.reply_text(
                "❌ Henüz tüm görevleri tamamlamadın!\n\n"
                "Önce tüm görevleri tamamla sonra cüzdan adresini gönder."
            )
            conn.close()
            return
    
    if result['bsc_address']:
        await update.message.reply_text(
            f"⚠️ Zaten bir cüzdan adresi kayıtlı:\n\n"
            f"{result['bsc_address']}\n\n"
            f"Değiştirmek için yeni adres gönder."
        )
    else:
        await update.message.reply_text(
            "💰 Lütfen BSC (Binance Smart Chain) cüzdan adresini gönder:\n\n"
            "Örnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        )
    
    context.user_data['awaiting_wallet'] = True
    conn.close()

# Mesaj işleme
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if context.user_data.get('awaiting_wallet'):
        if re.match(r'^0x[a-fA-F0-9]{40}$', text):
            c.execute("""
                UPDATE users 
                SET bsc_address = ? 
                WHERE user_id = ?
            """, (text, user_id))
            conn.commit()
            
            await update.message.reply_text(
                "✅ Cüzdan adresin başarıyla kaydedildi!\n\n"
                "Ödüllerin dağıtımı için admin onayı bekleniyor.\n"
                "Süreci /start komutu ile takip edebilirsin."
            )
            
            # Admin'e bildirim gönder
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔥 Yeni cüzdan adresi kaydedildi!\n\n"
                    f"👤 Kullanıcı ID: {user_id}\n"
                    f"💰 Cüzdan: {text}\n\n"
                    f"/export komutu ile listeyi alabilirsin."
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
        else:
            await update.message.reply_text(
                "❌ Geçersiz BSC cüzdan adresi!\n\n"
                "Lütfen doğru bir Binance Smart Chain (BSC) adresi gönder.\n"
                "Örnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
            )
        
        context.user_data['awaiting_wallet'] = False
    
    elif context.user_data.get('awaiting_x_username'):
        if re.match(r'^@[A-Za-z0-9_]+$', text):
            c.execute("""
                UPDATE users 
                SET x_username = ?, task3_completed = 1, balance = balance + 20 
                WHERE user_id = ?
            """, (text, user_id))
            conn.commit()
            
            await update.message.reply_text(
                f"✅ X kullanıcı adın ({text}) kaydedildi!\n"
                "+20 Solium kazandın!\n\n"
                "Not: Adminler tarafından manuel olarak kontrol edilecektir."
            )
            
            # Admin'e bildirim gönder
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔍 Yeni X kullanıcı kaydı!\n\n"
                    f"👤 Kullanıcı ID: {user_id}\n"
                    f"🐦 X Adresi: {text}\n\n"
                    f"Kontrol etmek için: https://twitter.com/{text[1:]}"
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
            
            context.user_data['awaiting_x_username'] = False
            await show_tasks(update, context)
        else:
            await update.message.reply_text(
                "❌ Geçersiz X kullanıcı adı formatı!\n\n"
                "Lütfen @ ile başlayan kullanıcı adını gönder.\n"
                "Örnek: @soliumcoin"
            )
    
    conn.close()

# Admin komutları
async def export_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Bu komutu sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    
    # Geçici dosya oluştur
    filename = "bsc_addresses.json"
    with open(filename, 'w') as f:
        json.dump(addresses, f, indent=2)
    
    # Dosyayı gönder
    try:
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption="📊 BSC Cüzdan Adresleri Listesi"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Dosya gönderilirken hata: {e}")
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
    application.add_handler(CommandHandler('wallet', wallet))
    application.add_handler(CommandHandler('check', check_tasks))
    application.add_handler(CommandHandler('export', export_addresses))
    
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^(balance|referral|terms|airdrop)$'))
    application.add_handler(CallbackQueryHandler(handle_task, pattern='^(task1|task2|task3|task4|task5)$'))
    application.add_handler(CallbackQueryHandler(check_tasks, pattern='^check_tasks$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Polling modunda başlat
    logger.info("🚀 Bot polling modunda başlatılıyor...")
    application.run_polling()

if __name__ == '__main__':
    main()
