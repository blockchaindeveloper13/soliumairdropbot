from flask import Flask, request
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Bot, Update
import sqlite3
import json
import re
import os

app = Flask(__name__)

# Ortam değişkenleri
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat')
APP_NAME = os.environ.get('APP_NAME')

# Veritabanı
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users 
             (user_id INTEGER PRIMARY KEY, bsc_address TEXT, x_username TEXT, balance INTEGER, referrals INTEGER, 
              participated BOOLEAN, referrer_id INTEGER, 
              task1_completed BOOLEAN, task2_completed BOOLEAN, task3_completed BOOLEAN, 
              task4_completed BOOLEAN, task5_completed BOOLEAN)''')
conn.commit()

# Bot ve Dispatcher
bot = Bot(BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=1)  # workers=1 ile asenkron destek

def start(update, context):
    user_id = update.message.from_user.id
    args = context.args
    referrer_id = None
    if args and args[0].startswith("ref"):
        referrer_id = int(args[0][3:])
        if referrer_id != user_id:
            c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated, referrer_id, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed) VALUES (?, 0, 0, 0, ?, 0, 0, 0, 0, 0)", (user_id, referrer_id))
        else:
            c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed) VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0)", (user_id,))
    else:
        c.execute("INSERT OR IGNORE INTO users (user_id, balance, referrals, participated, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed) VALUES (?, 0, 0, 0, 0, 0, 0, 0, 0)", (user_id,))
    conn.commit()
    show_main_menu(update, context)

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
        update.message.reply_text("Merhaba kanka! Menüden bir seçenek seç:", reply_markup=reply_markup)
    else:
        update.callback_query.message.edit_text("Menüden bir seçenek seç:", reply_markup=reply_markup)

def button_callback(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()

    if query.data == 'balance':
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        balance = c.fetchone()[0]
        query.message.reply_text(f"Bakiyen: {balance} Solium")
        show_main_menu(update, context)

    elif query.data == 'referral':
        c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
        referrals = c.fetchone()[0]
        query.message.reply_text(f"Referans kodun: ref{user_id}\nDavet ettiğin kişi sayısı: {referrals}")
        show_main_menu(update, context)

    elif query.data == 'terms':
        terms = f"Airdrop Şartları:\n1. Telegram grubu takip (@soliumcoinchat) - 20 Solium\n2. Telegram kanalı takip (@soliumcoin) - 20 Solium\n3. X hesabı takip (@soliumcoin) - 20 Solium\n4. X pinned post RT - 20 Solium\n5. WhatsApp kanalı takip - 20 Solium\n6. Referansla arkadaş davet et (hem sen hem arkadaşın 20 Solium, arkadaşın görevleri tamamlarsa)"
        query.message.reply_text(terms)
        show_main_menu(update, context)

    elif query.data == 'airdrop':
        c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
        participated = c.fetchone()[0]
        if participated:
            query.message.reply_text("Zaten airdropa katıldın kanka!")
            show_main_menu(update, context)
        else:
            show_tasks(update, context)

def show_tasks(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    c.execute("SELECT task3_completed FROM users WHERE user_id = ?", (user_id,))
    task3_completed = c.fetchone()[0]
    keyboard = [
        [InlineKeyboardButton("1. Telegram Grubu Takip - Done", callback_data='task1')],
        [InlineKeyboardButton("2. Telegram Kanalı Takip - Done", callback_data='task2')],
        [InlineKeyboardButton("3. X Hesabı Takip - Done", callback_data='task3')],
        [InlineKeyboardButton("4. X Pinned Post RT - Done", callback_data='task4') if task3_completed else []],
        [InlineKeyboardButton("5. WhatsApp Kanalı Takip - Done", callback_data='task5')]
    ]
    keyboard = [row for row in keyboard if row]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.edit_text("Görevleri tamamla kanka:", reply_markup=reply_markup)

def check(update, context):
    user_id = update.message.from_user.id
    c.execute("SELECT participated, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    participated, task1, task2, task3, task4, task5 = result
    if participated:
        update.message.reply_text("Zaten airdropa katıldın kanka!")
        return
    if task1 and task2 and task3 and task4 and task5:
        c.execute("UPDATE users SET participated = 1 WHERE user_id = ?", (user_id,))
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer_id = c.fetchone()[0]
        if referrer_id:
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))
            c.execute("UPDATE users SET balance = balance + 20, referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        update.message.reply_text("Tüm görevler tamamlandı! Cüzdan adresini eklemek için /wallet yaz.")
    else:
        update.message.reply_text("Hala tamamlanmamış görevlerin var kanka! /start ile görevleri kontrol et.")

def handle_task(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    c.execute("SELECT participated, task1_completed, task2_completed, task3_completed, task4_completed, task5_completed FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    participated, task1, task2, task3, task4, task5 = result
    if participated:
        query.message.reply_text("Zaten airdropa katıldın kanka!")
        show_main_menu(update, context)
        return

    if query.data == 'task1':
        if task1:
            query.message.reply_text("Bu görevi zaten tamamladın!")
        else:
            try:
                member = context.bot.get_chat_member(GROUP_ID, user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    c.execute("UPDATE users SET balance = balance + 20, task1_completed = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    query.message.reply_text("Telegram grubu görevi tamamlandı! 20 Solium eklendi.")
                else:
                    query.message.reply_text(f"Lütfen {GROUP_ID} grubuna katıl ve tekrar dene!")
            except:
                query.message.reply_text("Bir hata oluştu, gruba katıldığından emin ol!")
        show_tasks(update, context)

    elif query.data == 'task2':
        if task2:
            query.message.reply_text("Bu görevi zaten tamamladın!")
        else:
            try:
                member = context.bot.get_chat_member(CHANNEL_ID, user_id)
                if member.status in ['member', 'administrator', 'creator']:
                    c.execute("UPDATE users SET balance = balance + 20, task2_completed = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    query.message.reply_text("Telegram kanalı görevi tamamlandı! 20 Solium eklendi.")
                else:
                    query.message.reply_text(f"Lütfen {CHANNEL_ID} kanalına katıl ve tekrar dene!")
            except:
                query.message.reply_text("Bir hata oluştu, kanala katıldığından emin ol!")
        show_tasks(update, context)

    elif query.data == 'task3':
        if task3:
            query.message.reply_text("Bu görevi zaten tamamladın!")
        else:
            query.message.reply_text("Lütfen @soliumcoin X hesabını takip et ve X kullanıcı adını (@username şeklinde) gir:")
            context.user_data['awaiting_x_username'] = True
        show_tasks(update, context)

    elif query.data == 'task4':
        if task4:
            query.message.reply_text("Bu görevi zaten tamamladın!")
        else:
            c.execute("UPDATE users SET balance = balance + 20, task4_completed = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            query.message.reply_text("X pinned post RT görevi işaretlendi! 20 Solium eklendi. (Admin manuel kontrol edecek)")
        show_tasks(update, context)

    elif query.data == 'task5':
        if task5:
            query.message.reply_text("Bu görevi zaten tamamladın!")
        else:
            c.execute("UPDATE users SET balance = balance + 20, task5_completed = 1 WHERE user_id = ?", (user_id,))
            conn.commit()
            query.message.reply_text("WhatsApp kanalı görevi işaretlendi! 20 Solium eklendi. (Admin manuel kontrol edecek)")
        show_tasks(update, context)

def wallet(update, context):
    user_id = update.message.from_user.id
    c.execute("SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed, balance FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    tasks, balance = result[:5], result[5]
    if all(tasks):
        c.execute("UPDATE users SET participated = 1 WHERE user_id = ?", (user_id,))
        c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
        referrer_id = c.fetchone()[0]
        if referrer_id:
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))
            c.execute("UPDATE users SET balance = balance + 20, referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
            c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        update.message.reply_text(f"Tebrikler kanka! Tüm görevleri tamamladın, toplam {balance + (20 if referrer_id else 0)} Solium kazandın! 🎉 BSC cüzdan adresini gir:")
        context.user_data['awaiting_wallet'] = True
    else:
        update.message.reply_text("Önce tüm görevleri tamamla kanka!")

def handle_message(update, context):
    user_id = update.message.from_user.id
    text = update.message.text
    if context.user_data.get('awaiting_wallet'):
        if re.match(r'^0x[a-fA-F0-9]{40}$', text):
            c.execute("UPDATE users SET bsc_address = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            update.message.reply_text("Cüzdan adresin alındı! Airdrop ödüllerin için admin kontrolünü bekle! 🚀")
            context.user_data['awaiting_wallet'] = False
        else:
            update.message.reply_text("Geçersiz BSC adresi! Doğru bir adres gir kanka.")
    elif context.user_data.get('awaiting_x_username'):
        x_username = text
        if re.match(r'^@[A-Za-z0-9_]+$', x_username):
            c.execute("UPDATE users SET x_username = ?, balance = balance + 20, task3_completed = 1 WHERE user_id = ?", (x_username, user_id))
            conn.commit()
            update.message.reply_text(f"X kullanıcı adın ({x_username}) kaydedildi! 20 Solium eklendi. (Admin manuel kontrol edecek)")
            context.user_data['awaiting_x_username'] = False
            show_tasks(update, context)
        else:
            update.message.reply_text("X kullanıcı adı @ ile başlamalı ve sadece harf, rakam veya _ içermeli! Tekrar dene.")

def export_json(update, context):
    if update.message.from_user.id == ADMIN_ID:
        c.execute("SELECT * FROM users")
        users = [{"user_id": row[0], "bsc_address": row[1], "x_username": row[2], "balance": row[3], "referrals": row[4], 
                  "participated": bool(row[5]), "referrer_id": row[6], "task1_completed": bool(row[7]), 
                  "task2_completed": bool(row[8]), "task3_completed": bool(row[9]), "task4_completed": bool(row[10]), 
                  "task5_completed": bool(row[11])} for row in c.fetchall()]
        with open('users.json', 'w') as f:
            json.dump(users, f)
        context.bot.send_document(chat_id=update.message.chat_id, document=open('users.json', 'rb'))
    else:
        update.message.reply_text("Bu komutu sadece admin kullanabilir kanka!")

def export2_json(update, context):
    if update.message.from_user.id == ADMIN_ID:
        c.execute("SELECT bsc_address FROM users WHERE bsc_address IS NOT NULL")
        addresses = [row[0] for row in c.fetchall()]
        with open('addresses.json', 'w') as f:
            json.dump(addresses, f)
        context.bot.send_document(chat_id=update.message.chat_id, document=open('addresses.json', 'rb'))
    else:
        update.message.reply_text("Bu komutu sadece admin kullanabilir kanka!")

# Webhook endpoint
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return 'OK', 200

# Webhook ayarı
@app.route('/')
def setup_webhook():
    webhook_url = f"https://{APP_NAME}.herokuapp.com/{BOT_TOKEN}"
    bot.set_webhook(url=webhook_url)
    return f"Webhook set to {webhook_url}"

def main():
    # Handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("check", check))
    dispatcher.add_handler(CommandHandler("wallet", wallet))
    dispatcher.add_handler(CommandHandler("export", export_json))
    dispatcher.add_handler(CommandHandler("export2", export2_json))
    dispatcher.add_handler(CallbackQueryHandler(button_callback, pattern=r'^(balance|referral|terms|airdrop)$'))
    dispatcher.add_handler(CallbackQueryHandler(handle_task, pattern=r'^(task1|task2|task3|task4|task5)$'))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == '__main__':
    main()  # Handler'ları başlat
    # Heroku port
    port = int(os.environ.get('PORT', 8443))
    app.run(host='0.0.0.0', port=port)
