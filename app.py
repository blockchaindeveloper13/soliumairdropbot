import os
import logging
import sqlite3
import json
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID'))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat')
X_ACCOUNT = os.environ.get('X_ACCOUNT', '@soliumcoin')  # X account for tasks
WHATSAPP_LINK = os.environ.get('WHATSAPP_LINK', 'https://whatsapp.com/channel/your_channel')  # WhatsApp channel link

# Database connection
def get_db_connection():
    conn = sqlite3.connect('users.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# Initialize database
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
                  task1_completed BOOLEAN DEFAULT 0,  -- Join Telegram group
                  task2_completed BOOLEAN DEFAULT 0,  -- Follow Telegram channel
                  task3_completed BOOLEAN DEFAULT 0,  -- Follow X account
                  task4_completed BOOLEAN DEFAULT 0,  -- Retweet pinned X post
                  task5_completed BOOLEAN DEFAULT 0)  -- Join WhatsApp channel''')
    conn.commit()
    conn.close()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    referrer_id = None

    conn = get_db_connection()
    c = conn.cursor()

    # Handle referral
    if args and args[0].startswith("ref"):
        try:
            referrer_id = int(args[0][3:])
            if referrer_id != user_id:
                c.execute("""
                    INSERT OR IGNORE INTO users 
                    (user_id, balance, referrals, participated, referrer_id) 
                    VALUES (?, 0, 0, 0, ?)
                """, (user_id, referrer_id))
                c.execute("UPDATE users SET referrals = referrals + 1 WHERE user_id = ?", (referrer_id,))
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

# Show main menu
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id

    keyboard = [
        [InlineKeyboardButton("💰 Balance", callback_data='balance')],
        [InlineKeyboardButton("🤝 Referral", callback_data='referral')],
        [InlineKeyboardButton("🎯 Start Airdrop Tasks", callback_data='start_tasks')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(
            "🚀 Welcome to the Solium Airdrop Bot!\n\n"
            "Join our airdrop to earn Solium tokens by completing tasks.\n"
            "Select an option from the menu:",
            reply_markup=reply_markup
        )
    else:
        await update.callback_query.message.edit_text(
            "🚀 Solium Airdrop Bot - Main Menu:\n\n"
            "Select an option:",
            reply_markup=reply_markup
        )

# Button callbacks
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
        await query.message.reply_text(f"💰 Your Balance: {balance} Solium")

    elif query.data == 'referral':
        c.execute("SELECT referrals FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        referrals = result['referrals'] if result else 0
        referral_link = f"https://t.me/{context.bot.username}?start=ref{user_id}"
        await query.message.reply_text(
            f"📢 Referral Information:\n\n"
            f"🔗 Your Referral Link: {referral_link}\n"
            f"👥 Number of Referrals: {referrals}\n\n"
            f"Earn 20 Solium for each friend you invite!\n"
            f"Plus, get an extra 20 Solium if they complete all tasks."
        )

    elif query.data == 'start_tasks':
        c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
        result = c.fetchone()
        if result['participated']:
            await query.message.reply_text(
                "🎉 You've already participated in the airdrop!\n"
                "Please wait for the reward distribution."
            )
        else:
            await show_next_task(update, context)

    conn.close()
    await show_main_menu(update, context)

# Show next incomplete task
async def show_next_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT task1_completed, task2_completed, task3_completed, task4_completed, task5_completed, participated
        FROM users WHERE user_id = ?
    """, (user_id,))
    tasks = c.fetchone()

    if tasks['participated']:
        await query.message.reply_text(
            "🎉 You've already completed all tasks!\n"
            "Please wait for the reward distribution."
        )
        conn.close()
        await show_main_menu(update, context)
        return

    # Determine the next incomplete task
    tasks_list = [
        ('task1', tasks['task1_completed'], "Join our Telegram group", f"Join {GROUP_ID}"),
        ('task2', tasks['task2_completed'], "Follow our Telegram channel", f"Follow {CHANNEL_ID}"),
        ('task3', tasks['task3_completed'], "Follow our X account", f"Follow {X_ACCOUNT} on X"),
        ('task4', tasks['task4_completed'], "Retweet our pinned X post", f"Retweet the pinned post from {X_ACCOUNT}"),
        ('task5', tasks['task5_completed'], "Join our WhatsApp channel", f"Join our WhatsApp channel: {WHATSAPP_LINK}")
    ]

    for task_id, completed, task_name, task_instruction in tasks_list:
        if not completed:
            keyboard = [
                [InlineKeyboardButton("✅ Complete Task", callback_data=task_id)],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(
                f"🎯 Task: {task_name}\n\n"
                f"Instruction: {task_instruction}\n\n"
                f"Click 'Complete Task' after finishing the task.",
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            conn.close()
            return

    # All tasks completed
    await complete_airdrop(update, context)
    conn.close()

# Complete airdrop
async def complete_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.callback_query.from_user.id

    conn = get_db_connection()
    c = conn.cursor()

    # Add referral bonus
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    referrer_id = result['referrer_id'] if result else None

    if referrer_id:
        c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer_id,))

    # Reward user
    c.execute("""
        UPDATE users 
        SET balance = balance + 100, participated = 1 
        WHERE user_id = ?
    """, (user_id,))
    conn.commit()

    await update.callback_query.message.reply_text(
        "🎉 CONGRATULATIONS! You've completed all airdrop tasks!\n\n"
        "Total Earned: 100 Solium\n"
        "Please submit your BSC wallet address using /wallet."
    )
    conn.close()
    await show_main_menu(update, context)

# Handle tasks
async def handle_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    if c.fetchone()['participated']:
        await query.message.reply_text(
            "🎉 You've already participated in the airdrop!\n"
            "Please wait for the reward distribution."
        )
        conn.close()
        await show_main_menu(update, context)
        return

    task_data = query.data

    if task_data == 'task1':
        try:
            member = await context.bot.get_chat_member(GROUP_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("UPDATE users SET task1_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
                conn.commit()
                await query.message.reply_text(
                    "✅ Telegram Group Task Completed!\n"
                    "+20 Solium Earned!"
                )
            else:
                await query.message.reply_text(
                    f"❌ You haven't joined {GROUP_ID}!\n\n"
                    "Please join the group and try again."
                )
        except Exception as e:
            logger.error(f"Telegram group check error: {e}")
            await query.message.reply_text(
                "❌ Error checking group membership!\n"
                "Please try again later."
            )

    elif task_data == 'task2':
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            if member.status in ['member', 'administrator', 'creator']:
                c.execute("UPDATE users SET task2_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
                conn.commit()
                await query.message.reply_text(
                    "✅ Telegram Channel Task Completed!\n"
                    "+20 Solium Earned!"
                )
            else:
                await query.message.reply_text(
                    f"❌ You haven't joined {CHANNEL_ID}!\n\n"
                    "Please follow the channel and try again."
                )
        except Exception as e:
            logger.error(f"Telegram channel check error: {e}")
            await query.message.reply_text(
                "❌ Error checking channel membership!\n"
                "Please try again later."
            )

    elif task_data == 'task3':
        await query.message.reply_text(
            "🔍 To verify you followed our X account, please send your X username (starting with @).\n"
            "Example: @soliumcoin"
        )
        context.user_data['awaiting_x_username'] = True

    elif task_data == 'task4':
        c.execute("UPDATE users SET task4_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        await query.message.reply_text(
            "✅ X Pinned Post Retweet Task Recorded!\n"
            "+20 Solium Earned!\n\n"
            "Note: This will be manually verified by admins."
        )

    elif task_data == 'task5':
        c.execute("UPDATE users SET task5_completed = 1, balance = balance + 20 WHERE user_id = ?", (user_id,))
        conn.commit()
        await query.message.reply_text(
            "✅ WhatsApp Channel Task Recorded!\n"
            "+20 Solium Earned!\n\n"
            "Note: This will be manually verified by admins."
        )

    conn.close()
    await show_next_task(update, context)

# Wallet address submission
async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT participated, bsc_address, task1_completed, task2_completed, 
               task3_completed, task4_completed, task5_completed 
        FROM users WHERE user_id = ?
    """, (user_id,))
    result = c.fetchone()

    if not result['participated']:
        all_tasks_completed = all([
            result['task1_completed'], result['task2_completed'], result['task3_completed'],
            result['task4_completed'], result['task5_completed']
        ])
        if not all_tasks_completed:
            await update.message.reply_text(
                "❌ You haven't completed all tasks yet!\n\n"
                "Please complete all tasks before submitting a wallet address."
            )
            conn.close()
            return

    if result['bsc_address']:
        await update.message.reply_text(
            f"⚠️ A wallet address is already registered:\n\n"
            f"{result['bsc_address']}\n\n"
            f"To change it, send a new address."
        )
    else:
        await update.message.reply_text(
            "💰 Please send your BSC (Binance Smart Chain) wallet address:\n\n"
            "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        )

    context.user_data['awaiting_wallet'] = True
    conn.close()

# Handle text messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    conn = get_db_connection()
    c = conn.cursor()

    if context.user_data.get('awaiting_wallet'):
        if re.match(r'^0x[a-fA-F0-9]{40}$', text):
            c.execute("UPDATE users SET bsc_address = ? WHERE user_id = ?", (text, user_id))
            conn.commit()
            await update.message.reply_text(
                "✅ Your wallet address has been successfully recorded!\n\n"
                "Your rewards are pending admin approval.\n"
                "Track your progress with /start."
            )
            # Notify admin
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔥 New wallet address recorded!\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"💰 Wallet: {text}\n\n"
                    f"Use /export to get the list."
                )
            except Exception as e:
                logger.error(f"Admin notification error: {e}")
            context.user_data['awaiting_wallet'] = False
        else:
            await update.message.reply_text(
                "❌ Invalid BSC wallet address!\n\n"
                "Please send a valid Binance Smart Chain (BSC) address.\n"
                "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
            )

    elif context.user_data.get('awaiting_x_username'):
        if re.match(r'^@[A-Za-z0-9_]+$', text):
            c.execute("""
                UPDATE users 
                SET x_username = ?, task3_completed = 1, balance = balance + 20 
                WHERE user_id = ?
            """, (text, user_id))
            conn.commit()
            await update.message.reply_text(
                f"✅ Your X username ({text}) has been recorded!\n"
                "+20 Solium Earned!\n\n"
                "Note: This will be manually verified by admins."
            )
            # Notify admin
            try:
                await context.bot.send_message(
                    ADMIN_ID,
                    f"🔍 New X username recorded!\n\n"
                    f"👤 User ID: {user_id}\n"
                    f"🐦 X Username: {text}\n\n"
                    f"Check: https://x.com/{text[1:]}"
                )
            except Exception as e:
                logger.error(f"Admin notification error: {e}")
            context.user_data['awaiting_x_username'] = False
            await show_next_task(Update(
                update_id=update.update_id,
                callback_query=update.callback_query or type('CallbackQuery', (), {
                    'from_user': update.message.from_user,
                    'message': update.message,
                    'data': 'task3'
                })(),
                message=update.message
            ), context)
        else:
            await update.message.reply_text(
                "❌ Invalid X username format!\n\n"
                "Please send a username starting with @.\n"
                "Example: @soliumcoin"
            )

    conn.close()

# Admin export command
async def export_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admins can use this command!")
        return

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    conn.close()

    filename = "bsc_addresses.json"
    with open(filename, 'w') as f:
        json.dump(addresses, f, indent=2)

    try:
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption="📊 List of BSC Wallet Addresses"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending file: {e}")
    finally:
        try:
            os.remove(filename)
        except:
            pass

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('wallet', wallet))
    application.add_handler(CommandHandler('export', export_addresses))
    application.add_handler(CallbackQueryHandler(button_callback, pattern='^(balance|referral|start_tasks|main_menu)$'))
    application.add_handler(CallbackQueryHandler(handle_task, pattern='^(task1|task2|task3|task4|task5)$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🚀 Bot starting in polling mode...")
    application.run_polling()

if __name__ == '__main__':
    main()
