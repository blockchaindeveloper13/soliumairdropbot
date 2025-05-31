import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import sqlite3
import re

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
    
    # Check if user already participated
    c.execute("SELECT participated FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user['participated']:
        await update.message.reply_text("🎉 You've already participated in the airdrop! You can't join again.")
        conn.close()
        return
    
    if args and args[0].startswith("ref"):
        try:
            referrer_id = int(args[0][3:])
            if referrer_id != user_id:
                # Update referrer's count and balance
                c.execute("UPDATE users SET referrals = referrals + 1, balance = balance + 20 WHERE user_id = ?", (referrer_id,))
                
                # Add new user with referral bonus
                c.execute("""
                    INSERT OR REPLACE INTO users 
                    (user_id, balance, referrer_id) 
                    VALUES (?, 20, ?)
                """, (user_id, referrer_id))
                
                await update.message.reply_text(
                    "🎉 You joined through a referral link! "
                    "Both you and the referrer received 20 Solium."
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
    await show_task(update, context, 1)  # Show first task

async def show_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_number: int):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    tasks = [
        {
            'title': "1️⃣ Join Telegram Group",
            'description': f"Join our official Telegram group: {GROUP_ID}",
            'button': "I Joined ✅"
        },
        {
            'title': "2️⃣ Follow Telegram Channel",
            'description': f"Follow our official Telegram channel: {CHANNEL_ID}",
            'button': "I'm Following ✅"
        },
        {
            'title': "3️⃣ Follow X (Twitter) Account",
            'description': "Follow our official X account: @soliumcoin",
            'button': "I'm Following ✅"
        },
        {
            'title': "4️⃣ Retweet Pinned Post",
            'description': "Retweet our pinned post on X",
            'button': "I Retweeted ✅"
        },
        {
            'title': "5️⃣ Enter Your BSC Wallet Address",
            'description': "Enter your BSC wallet address to receive rewards",
            'button': "Enter My Address"
        }
    ]
    
    if task_number <= len(tasks):
        task = tasks[task_number-1]
        
        keyboard = [[InlineKeyboardButton(task['button'], callback_data=f'task_done_{task_number}')]]
        
        if task_number > 1:
            keyboard.append([InlineKeyboardButton("◀️ Previous Task", callback_data=f'task_{task_number-1}')])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"🎯 Task {task_number}/{len(tasks)}\n\n{task['title']}\n\n{task['description']}"
        
        if update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        else:
            try:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Error editing message: {e}")
                await update.callback_query.message.reply_text(text, reply_markup=reply_markup)
    else:
        # All tasks completed
        await complete_airdrop(update, context)

async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check user participation status
    c.execute("SELECT participated, current_task FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user and user['participated']:
        await query.message.reply_text("❌ You've already completed the airdrop!")
        conn.close()
        return
    
    if data.startswith('task_'):
        # Navigation between tasks
        task_number = int(data.split('_')[1])
        await show_task(update, context, task_number)
    
    elif data.startswith('task_done_'):
        # Marking task as complete
        task_number = int(data.split('_')[2])
        next_task = task_number + 1
        
        # Update current task in database
        c.execute("UPDATE users SET current_task = ? WHERE user_id = ?", (next_task, user_id))
        conn.commit()
        
        if task_number == 5:
            # Special handling for wallet address entry
            await query.message.reply_text(
                "💰 Please send your BSC wallet address:\n\n"
                "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F\n\n"
                "⚠️ Double-check your address!"
            )
            context.user_data['awaiting_wallet'] = True
        else:
            # For normal tasks
            await query.edit_message_text(
                text=f"✅ Task {task_number} completed!\n\n"
                     f"Please proceed to the next task."
            )
            # Show next task after short delay
            await show_task(update, context, next_task)
    
    conn.close()

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    
    if not context.user_data.get('awaiting_wallet'):
        return
    
    if re.match(r'^0x[a-fA-F0-9]{40}$', text):
        conn = get_db_connection()
        c = conn.cursor()
        
        # Save wallet address and complete the task
        c.execute("UPDATE users SET bsc_address = ?, current_task = 6 WHERE user_id = ?", 
                 (text, user_id))
        conn.commit()
        
        await update.message.reply_text(
            "✅ Your wallet address has been saved!\n\n"
            "Now completing the airdrop process..."
        )
        
        await complete_airdrop(update, context)
        context.user_data['awaiting_wallet'] = False
        conn.close()
    else:
        await update.message.reply_text(
            "❌ Invalid BSC wallet address format!\n\n"
            "Please enter a valid address (42 characters starting with 0x).\n"
            "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
        )

async def complete_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    
    conn = get_db_connection()
    c = conn.cursor()
    
    # Add final reward (100 Solium)
    c.execute("UPDATE users SET balance = balance + 100, participated = 1 WHERE user_id = ?", (user_id,))
    
    # Add referral bonus if applicable
    c.execute("SELECT referrer_id FROM users WHERE user_id = ?", (user_id,))
    referrer = c.fetchone()
    if referrer and referrer['referrer_id']:
        c.execute("UPDATE users SET balance = balance + 20 WHERE user_id = ?", (referrer['referrer_id'],))
        try:
            await context.bot.send_message(
                referrer['referrer_id'],
                "🎉 Your referral completed the airdrop! You earned +20 Solium."
            )
        except Exception as e:
            logger.error(f"Error sending referral notification: {e}")
    
    conn.commit()
    
    # Show final message to user
    c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = c.fetchone()['balance']
    
    await (update.message or update.callback_query.message).reply_text(
        f"🎉 CONGRATULATIONS! Airdrop completed!\n\n"
        f"💵 Total Earned: {balance} Solium\n\n"
        f"Rewards will be sent to your BSC address."
    )
    
    conn.close()

async def export_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admins can use this command!")
        return
    
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
    addresses = [dict(row) for row in c.fetchall()]
    
    if not addresses:
        await update.message.reply_text("❌ No wallet addresses found!")
        conn.close()
        return
    
    # Create temporary file
    filename = "bsc_addresses.txt"
    with open(filename, 'w') as f:
        for addr in addresses:
            f.write(f"{addr['user_id']}: {addr['bsc_address']}\n")
    
    # Send file
    try:
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption=f"📋 Total {len(addresses)} BSC wallet addresses"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Error sending file: {str(e)}")
    finally:
        # Remove temporary file
        try:
            os.remove(filename)
        except:
            pass
    
    conn.close()

def main():
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('export', export_addresses))
    application.add_handler(CallbackQueryHandler(handle_task_button, pattern='^(task_|task_done_)'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))
    
    # Start polling
    logger.info("🚀 Starting bot in polling mode...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=['message', 'callback_query'],
        poll_interval=1.0
    )

if __name__ == '__main__':
    main()
