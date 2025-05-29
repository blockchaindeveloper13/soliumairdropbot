import asyncio
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import sqlite3
import json
import re
import os
import logging

# Log ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

flask_app = Flask(__name__)  # Flask nesnesi

# Ortam değişkenleri
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', '1616739367'))
CHANNEL_ID = '@soliumcoin'  # Sabit
GROUP_ID = '@soliumcoinchat'  # Sabit

# Veritabanı bağlantısı
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Veritabanı tablosu oluştur
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
async def start(update: Update, context):
    logger.info(f"Start komutu: user_id={update.message.from_user.id}")
    user_id = update.message.from_user.id
    args = context.args
    referrer_id = None
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if args and args[0].startswith("ref"):
        try:
            referrer_id = int(args[0][3:])
            if referrer_id != user_id:
                c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated, referrer_id) VALUES (?, 0, 0, 0, ?)", 
                         (user_id, referrer_id))
                c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
            else:
                c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated) VALUES (?, 0, 0, 0)", (user_id,))
        except ValueError:
            c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated) VALUES (?, 0, 0, 0)", (user_id,))
    else:
        c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated) VALUES (?, 0, 0, 0)", (user_id,))
    
    conn.commit()
    conn.close()
    await show_main_menu(update, context)

# Ana menü
async def show_main_menu(update: Update, context):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Airdrop Şartları", callback_data='terms')],
        [InlineKeyboardButton("🎁 Airdrop Kazan", callback_data='airdrop')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    logger.info(f"Main menu gönderiliyor: user_id={user_id}, keyboard={keyboard}")
    
    try:
        if update.message:
            await update.message.reply_text("🚀 Solium Airdrop Botuna Hoşgeldin! Menüden bir seçenek seç:", reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text("🚀 Solium Airdrop Botu - Ana Menü:", reply_markup=reply_markup)
        logger.info(f"Main menu gönderildi: user_id={user_id}")
    except Exception as e:
        logger.error(f"Main menu hatası: user_id={user_id}, hata={e}")
        raise

# Buton callback
async def button_callback(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    logger.info(f"Buton tıklandı: user_id={user_id}, data={query.data}")

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
        bot_username = (await context.bot.get_me()).username
        await query.message.reply_text(
            f"📢 Referans Bilgileri:\n\n"
            f"🔗 Referans Linkin: https://t.me/{bot_username}?start=ref{user_id}\n"
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

# Görevler
async def show_tasks(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed FROM users WHERE user_id = ?", (user_id,))
    tasks = c.fetchone()
    
    keyboard = [
        [InlineKeyboardButton(f"1. Telegram Grubu {'✅' if tasks['task1_completed'] else '❌'}", callback_data='task1')],
        [InlineKeyboardButton(f"2. Telegram Kanalı {'✅' if tasks['task2_completed'] else '❌'}", callback_data='task2')],
        [InlineKeyboardButton(f"3. X Hesabı Takip {'✅' if tasks['task3_completed'] else '❌'}", callback_data='task3')],
        [InlineKeyboardButton(f"4. X Post RT {'✅' if tasks['task4_completed'] else '❌'}", callback_data='task4') if tasks['task3_completed'] else None],
        [InlineKeyboardButton(f"5. WhatsApp Kanalı {'✅' if tasks['task5_completed'] else '❌'}", callback_data='task5')],
        [InlineKeyboardButton("🔍 Görevleri Kontrol Et", callback_data='check_tasks')]
    ]
    keyboard = [row for row in keyboard if row[0] is not None]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.edit_text(
        "🎯 Airdrop Görevleri:\n\nAşağıdaki görevleri tamamlayarak Solium kazanabilirsin!\nGörevleri tamamladıktan sonra 'Görevleri Kontrol Et' butonuna bas.",
        reply_markup=reply_markup
    )
    conn.close()

# Görev kontrol
async def check_tasks(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed, participated FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if result['participated']:
        await query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        conn.close()
        return
    
    all_tasks_completed = all([result[f'task{i}_completed'] for i in range(1, 6)])
    
    if all_tasks_completed:
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        referrer_id = result['referrer_id'] if result else None
        
        if referrer_id:
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))
        
        c.execute("UPDATE users SET balance = balance + 100, participated = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        
        await query.message.reply_text(
            "🎉 TEBRİKLER! Tüm görevleri tamamladın!\n\nToplam kazandığın: 100 Solium\nBSC cüzdan adresini göndermek için /wallet yaz."
        )
    else:
        await query.message.reply_text("❌ Henüz tüm görevleri tamamlamadın!\n\nGörevleri tamamladığından emin ol ve tekrar kontrol et.")
    
    conn.close()
    await show_main_menu(update, context)

# Görev işleme
async def handle_task(update: Update, context):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()
    logger.info(f"Görev işleniyor: user_id={user_id}, task={query.data}")
    
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
                c.execute("UPDATE users SET task1_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
                conn.commit()
                await query.message.reply_text("✅ Telegram grubu görevi tamamlandı!\n+20 Solium kazandın!")
            else:
                await query.message.reply_text(f"❌ {GROUP_ID} grubuna katılmamışsın!\n\nGruba katıldıktan sonra tekrar dene.")
        except Exception as e:
            logger.error(f"Telegram grup kontrol hatası: {e}")
            await query.message.reply_text("❌ Grup kontrolü sırasında hata! Daha sonra dene.")
    
    elif task_data == 'task2':
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("UPDATE users SET task2_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
                conn.commit()
                await query.message.reply_text("✅ Telegram kanalı görevi tamamlandı!\n+20 Solium kazandın!")
            else:
                await query.message.reply_text(f"❌ {CHANNEL_ID} kanalına katılmamışsın!\n\nKanala katıldıktan sonra dene.")
        except Exception as e:
            logger.error(f"Telegram kanal kontrol hatası: {e}")
            await query.message.reply_text("❌ Kanal kontrolü sırasında hata! Daha sonra dene.")
    
    elif task_data == 'task3':
        await query.message.reply_text("🔍 X hesabını takip ettiğini doğrulamak için\n\nLütfen X kullanıcı adını (@ ile) gönder:\nÖrnek: @soliumcoin")
        context.user_data['awaiting_x_username'] = True
    
    elif task_data == 'task4':
        c.execute("UPDATE users SET task4_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        await query.message.reply_text("✅ X pinned post RT kaydedildi!\n+20 Solium kazandın!\n\nNot: Adminler kontrol edecek.")
    
    elif task_data == 'task5':
        c.execute("UPDATE users SET task5_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        await query.message.reply_text("✅ WhatsApp kanalı kaydedildi!\n+20 Solium kazandın!\n\nNot: Adminler kontrol edecek.")
    
    conn.close()
    await show_tasks(update, context)

# Cüzdan adresi
async def wallet(update: Update, context):
    user_id = update.message.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT participated, bsc_address, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    
    if not result['participated']:
        all_tasks_completed = all([result[f'task{i}_completed'] for i in range(1, 6)])
        if not all_tasks_completed:
            await update.message.reply_text("❌ Tüm görevleri tamamlamadın!\n\nÖnce görevleri tamamla, sonra cüzdan adresini gönder.")
            conn.close()
            return
    
    if result['bsc_address']:
        await update.message.reply_text(f"⚠️ Kayıtlı cüzdan adresin:\n\n{result['bsc_address']}\n\nDeğiştirmek için yeni adres gönder.")
    else:
        await update.message.reply_text("💰 BSC cüzdan adresini gönder:\n\nÖrnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F")
    
    context.user_data['awaiting_wallet'] = True
    conn.close()

# Mesaj işleme
async def handle_message(update: Update, context):
    user_id = update.message.from_user.id
    text = update.message.text
    logger.info(f"Mesaj alındı: user_id={user_id}, text={text}")
    
    conn = get_db_connection()
    c = conn.cursor()
    
    if context.user_data.get('awaiting_wallet'):
        if re.match(r'^0x[a-fA-F0-9]{40}$', text):
            c.execute("UPDATE users SET bsc_address = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            await update.message.reply_text("✅ Cüzdan adresin kaydedildi!\n\nÖdüller için admin onayı bekleniyor.")
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔥 Yeni cüzdan adresi:\n\n👤 Kullanıcı ID: {user_id}\n💰 Cüzdan: {text}\n\n/export ile listeyi al."
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
        else:
            await update.message.reply_text("❌ Geçersiz BSC adresi!\n\nDoğru bir adres gönder.\nÖrnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F")
        context.user_data['awaiting_wallet'] = False
    
    elif context.user_data.get('awaiting_x_username'):
        if re.match(r'^@[A-Za-z0-9_]+$', text):
            c.execute("UPDATE users SET x_username = ?, task3_completed = 1, balance = balance + 20 WHERE user_id = ?", (text, user_id))
            conn.commit()
            await update.message.reply_text(f"✅ X kullanıcı adın ({text}) kaydedildi!\n+20 Solium kazandın!\n\nNot: Adminler kontrol edecek.")
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔍 Yeni X kaydı!\n\n👤 Kullanıcı ID: {user_id}\n🐦 X Adresi: {text}\n\nKontrol: https://twitter.com/{text[1:]}"
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
            context.user_data['awaiting_x_username'] = False
            await show_tasks(update, context)
        else:
            await update.message.reply_text("❌ Geçersiz X kullanıcı adı!\n\n@ ile başlayan ad gönder.\nÖrnek: @soliumcoin")
    
    conn.close()

# Admin komutları
async def export_json(update: Update, context):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    users = [dict(row) for row in c.fetchall()]
    
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    try:
        with open('users.json', 'rb') as f:
            await update.message.reply_document(document=f, caption="📊 Tüm kullanıcı verileri")
    except Exception as e:
        await update.message.reply_text(f"❌ Dosya gönderim hatası: {e}")
        logger.error(f"Export JSON hatası: {e}")
    
    conn.close()

async def export_addresses(update: Update, context):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f, indent=2)
    
    try:
        with open('addresses.json', 'rb') as f:
            await update.message.reply_document(document=f, caption="📊 Cüzdan adresleri")
    except Exception as e:
        await update.message.reply_text(f"❌ Dosya gönderim hatası: {e}")
        logger.error(f"Export addresses hatası: {e}")
    
    conn.close()

# Webhook endpoint
@flask_app.route('/webhook', methods=['POST'])
def webhook():
    try:
        logger.info("Webhook isteği alındı")
        json_data = request.get_json()
        logger.info(f"Gelen veri: {json_data}")
        update = Update.de_json(json_data, bot_application.bot)
        asyncio.run_coroutine_threadsafe(bot_application.process_update(update), bot_application.loop)
        logger.info("Update işlendi")
        return 'OK', 200
    except Exception as e:
        logger.error(f"Webhook hatası: {e}")
        return 'Error', 500

# Kök endpoint
@flask_app.route('/')
def index():
    webhook_url = "https://soliumairdropbot-ef7a2a4b1280.herokuapp.com/webhook"  # Sabit URL
    try:
        asyncio.run_coroutine_threadsafe(bot_application.bot.set_webhook(url=webhook_url), bot_application.loop).result()
        logger.info(f"Webhook ayarlandı: {webhook_url}")
        return f"""
        <h1>🤖 Solium Airdrop Bot</h1>
        <p>Webhook URL: <code>{webhook_url}</code></p>
        <p>Durum: <strong>AKTİF</strong></p>
        <p>Botu kullanmak için Telegram'da <a href="https://t.me/@soliumcoinairdrop_bot">@soliumcoinairdrop_bot</a> adresini ziyaret et</p>
        """
    except Exception as e:
        logger.error(f"Webhook ayarlama hatası: {e}")
        return f"Webhook ayarlama başarısız: {e}", 500

# Uygulama başlat
if __name__ == '__main__':
    logger.info("Uygulama başlatılıyor")
    init_db()
    
    # Telegram bot application
    bot_application = Application.builder().token(BOT_TOKEN).build()
    
    # Handler'lar
    bot_application.add_handler(CommandHandler('start', start))
    bot_application.add_handler(CommandHandler('wallet', wallet))
    bot_application.add_handler(CommandHandler('check', check_tasks))
    bot_application.add_handler(CommandHandler('export', export_json))
    bot_application.add_handler(CommandHandler('export2', export_addresses))
    bot_application.add_handler(CallbackQueryHandler(button_callback, pattern='^(balance|referral|terms|airdrop)$'))
    bot_application.add_handler(CallbackQueryHandler(handle_task, pattern='^(task1|task2|task3|task4|task5)$'))
    bot_application.add_handler(CallbackQueryHandler(check_tasks, pattern='^check_tasks$'))
    bot_application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Flask'ı başlat
    port = int(os.environ.get('PORT', 8443))
    flask_app.run(host='0.0.0.0', port=port, debug=False)
