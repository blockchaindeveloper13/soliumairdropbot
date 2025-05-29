from flask import Flask, request
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot, Update
import sqlite3
import json
import re
import os
import logging

# Log ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Ortam değişkenleri
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat')
APP_NAME = os.environ.get('APP_NAME')

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

# Bot ve Dispatcher
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=1)

# /start komutu
def start(update, context):
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
    show_main_menu(update, context)

# Ana menüyü göster
def show_main_menu(update, context):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("📋 Airdrop Şartları", callback_data='terms')],
        [InlineKeyboardButton("🎁 Airdrop Kazan", callback_data='airdrop')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        update.message.reply_text("🚀 Solium Airdrop Botuna Hoşgeldin! Menüden bir seçenek seç:", reply_markup=reply_markup)
    else:
        update.callback_query.message.edit_text("🚀 Solium Airdrop Botu - Ana Menü:", reply_markup=reply_markup)

# Buton callback'leri
def button_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    conn = get_db_connection()
    c = conn.cursor()

    if query.data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        balance = result['balance'] if result else 0
        query.message.reply_text(f"💰 Toplam Bakiyen: {balance} Solium")
        
    elif query.data == 'referral':
        c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        referrals = result['referrals'] if result else 0
        query.message.reply_text(
            f"📢 Referans Bilgileri:\n\n"
            f"🔗 Referans Linkin: https://t.me/{bot.username}?start=ref{user_id}\n"
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
        query.message.reply_text(terms)
        
    elif query.data == 'airdrop':
        c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        participated = result['participated'] if result else False
        
        if participated:
            query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        else:
            show_tasks(update, context)
    
    conn.close()
    show_main_menu(update, context)

# Görevleri göster
def show_tasks(update, context):
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
    query.message.edit_text(
        "🎯 Airdrop Görevleri:\n\n"
        "Aşağıdaki görevleri tamamlayarak Solium kazanabilirsin!\n"
        "Görevleri tamamladıktan sonra 'Görevleri Kontrol Et' butonuna bas.",
        reply_markup=reply_markup
    )
    conn.close()

# Görev kontrol
def check_tasks(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed, participated 
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = c.fetchone()
    
    if result['participated']:
        query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
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
        
        query.message.reply_text(
            "🎉 TEBRİKLER! Tüm görevleri tamamladın!\n\n"
            "Toplam kazandığın: 100 Solium\n"
            "BSC cüzdan adresini göndermek için /wallet yaz."
        )
    else:
        query.message.reply_text(
            "❌ Henüz tüm görevleri tamamlamadın!\n\n"
            "Görevleri tamamladığından emin ol ve tekrar kontrol et."
        )
    
    conn.close()
    show_main_menu(update, context)

# Görev işleme
def handle_task(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    participated = c.fetchone()['participated']
    
    if participated:
        query.message.reply_text("🎉 Zaten airdropa katıldın! Ödüllerin dağıtımı için bekliyoruz.")
        conn.close()
        return
    
    task_data = query.data
    
    if task_data == 'task1':
        try:
            member = bot.get_chat_member(GROUP_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("""
                    UPDATE users 
                    SET task1_completed = 1, balance = balance + 20 
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                query.message.reply_text(
                    "✅ Telegram grubu görevi tamamlandı!\n"
                    "+20 Solium kazandın!"
                )
            else:
                query.message.reply_text(
                    f"❌ {GROUP_ID} grubuna katılmamışsın!\n\n"
                    f"Gruba katıldıktan sonra tekrar dene."
                )
        except Exception as e:
            logger.error(f"Telegram grup kontrol hatası: {e}")
            query.message.reply_text(
                "❌ Grup kontrolü sırasında bir hata oluştu!\n"
                "Lütfen daha sonra tekrar dene."
            )
    
    elif task_data == 'task2':
        try:
            member = bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("""
                    UPDATE users 
                    SET task2_completed = 1, balance = balance + 20 
                    WHERE user_id = ?
                """, (user_id,))
                conn.commit()
                query.message.reply_text(
                    "✅ Telegram kanalı görevi tamamlandı!\n"
                    "+20 Solium kazandın!"
                )
            else:
                query.message.reply_text(
                    f"❌ {CHANNEL_ID} kanalına katılmamışsın!\n\n"
                    f"Kanala katıldıktan sonra tekrar dene."
                )
        except Exception as e:
            logger.error(f"Telegram kanal kontrol hatası: {e}")
            query.message.reply_text(
                "❌ Kanal kontrolü sırasında bir hata oluştu!\n"
                "Lütfen daha sonra tekrar dene."
            )
    
    elif task_data == 'task3':
        query.message.reply_text(
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
        query.message.reply_text(
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
        query.message.reply_text(
            "✅ WhatsApp kanalı görevi kaydedildi!\n"
            "+20 Solium kazandın!\n\n"
            "Not: Adminler tarafından manuel olarak kontrol edilecektir."
        )
    
    conn.close()
    show_tasks(update, context)

# Cüzdan adresi alma
def wallet(update, context):
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
            update.message.reply_text(
                "❌ Henüz tüm görevleri tamamlamadın!\n\n"
                "Önce tüm görevleri tamamla sonra cüzdan adresini gönder."
            )
            conn.close()
            return
    
    if result['bsc_address']:
        update.message.reply_text(
            f"⚠️ Zaten bir cüzdan adresi kayıtlı:\n\n"
            f"{result['bsc_address']}\n\n"
            f"Değiştirmek için yeni adres gönder."
        )
    else:
        update.message.reply_text(
            "💰 Lütfen BSC (Binance Smart Chain) cüzdan adresini gönder:\n\n"
            "Örnek: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        )
    
    context.user_data['awaiting_wallet'] = True
    conn.close()

# Mesaj işleme
def handle_message(update, context):
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
            
            update.message.reply_text(
                "✅ Cüzdan adresin başarıyla kaydedildi!\n\n"
                "Ödüllerin dağıtımı için admin onayı bekleniyor.\n"
                "Süreci /start komutu ile takip edebilirsin."
            )
            
            # Admin'e bildirim gönder
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🔥 Yeni cüzdan adresi kaydedildi!\n\n"
                    f"👤 Kullanıcı ID: {user_id}\n"
                    f"💰 Cüzdan: {text}\n\n"
                    f"/export komutu ile listeyi alabilirsin."
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
        else:
            update.message.reply_text(
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
            
            update.message.reply_text(
                f"✅ X kullanıcı adın ({text}) kaydedildi!\n"
                "+20 Solium kazandın!\n\n"
                "Not: Adminler tarafından manuel olarak kontrol edilecektir."
            )
            
            # Admin'e bildirim gönder
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🔍 Yeni X kullanıcı kaydı!\n\n"
                    f"👤 Kullanıcı ID: {user_id}\n"
                    f"🐦 X Adresi: {text}\n\n"
                    f"Kontrol etmek için: https://twitter.com/{text[1:]}"
                )
            except Exception as e:
                logger.error(f"Admin bildirim hatası: {e}")
            
            context.user_data['awaiting_x_username'] = False
            show_tasks(update, context)
        else:
            update.message.reply_text(
                "❌ Geçersiz X kullanıcı adı formatı!\n\n"
                "Lütfen @ ile başlayan kullanıcı adını gönder.\n"
                "Örnek: @soliumcoin"
            )
    
    conn.close()

# Admin komutları
def export_json(update, context):
    if update.message.from_user.id != ADMIN_ID:
        update.message.reply_text("❌ Bu komutu sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT * FROM users")
    users = [dict(row) for row in c.fetchall()]
    
    with open('users.json', 'w') as f:
        json.dump(users, f, indent=2)
    
    try:
        with open('users.json', 'rb') as f:
            update.message.reply_document(
                document=f,
                caption="📊 Tüm kullanıcı verileri"
            )
    except Exception as e:
        update.message.reply_text(f"❌ Dosya gönderilirken hata: {e}")
    
    conn.close()

def export_addresses(update, context):
    if update.message.from_user.id != ADMIN_ID:
        update.message.reply_text("❌ Bu komutu sadece admin kullanabilir!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    
    with open('addresses.json', 'w') as f:
        json.dump(addresses, f, indent=2)
    
    try:
        with open('addresses.json', 'rb') as f:
            update.message.reply_document(
                document=f,
                caption="📊 Cüzdan adresleri"
            )
    except Exception as e:
        update.message.reply_text(f"❌ Dosya gönderilirken hata: {e}")
    
    conn.close()

# Webhook endpointini bu şekilde güncelle
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    json_data = request.get_json()
    print("Gelen veri:", json_data)  # Log ekle
    update = Update.de_json(json_data, bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Yeni root endpoint
@app.route('/')
def index():
    webhook_url = f"https://soliumairdropbot-ef7a2a4b1280-0071788c2efa.herokuapp.com/{BOT_TOKEN}"
    return f"""
    <h1>🤖 Solium Airdrop Bot</h1>
    <p>Webhook URL: <code>{webhook_url}</code></p>
    <p>Durum: <strong>AKTİF</strong></p>
    <a href="https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo" target="_blank">Webhook Bilgilerini Kontrol Et</a>
    """
# Kök endpoint
@app.route('/')
def index():
    return "🤖 Solium Airdrop Botu Aktif! /setwebhook ile webhook'u ayarlayın."

# Handler'ları başlat
def setup_handlers():
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CommandHandler('wallet', wallet))
    dispatcher.add_handler(CommandHandler('check', check_tasks))
    dispatcher.add_handler(CommandHandler('export', export_json))
    dispatcher.add_handler(CommandHandler('export2', export_addresses))
    
    dispatcher.add_handler(CallbackQueryHandler(button_callback, pattern='^(balance|referral|terms|airdrop)$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_task, pattern='^(task1|task2|task3|task4|task5)$'))
    dispatcher.add_handler(CallbackQueryHandler(check_tasks, pattern='^check_tasks$'))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

# Uygulamayı başlat
if __name__ == '__main__':
    # Veritabanını başlat
    init_db()
    
    # Handler'ları ayarla
    setup_handlers()
    
    # Webhook'u ayarla (sadece production'da)
    if APP_NAME:
        webhook_url = f"https://{APP_NAME}.herokuapp.com/{BOT_TOKEN}"
        bot.set_webhook(webhook_url)
        logger.info(f"Webhook set to: {webhook_url}")
    
    # Flask uygulamasını başlat
    port = int(os.environ.get('PORT', 8443))
    app.run(host='0.0.0.0', port=port, debug=False)
