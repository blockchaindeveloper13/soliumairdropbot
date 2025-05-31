import os
import logging
import re
import json
from urllib.parse import urlparse
import psycopg2
from psycopg2 import pool
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Enhanced logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Environment variables with validation
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("Missing BOT_TOKEN environment variable!")
    raise ValueError("BOT_TOKEN is required")

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin').replace('@', '')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat').replace('@', '')
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    logger.error("Missing DATABASE_URL environment variable!")
    raise ValueError("DATABASE_URL is required")

# Database connection pool
db_pool = None

def init_db_pool():
    global db_pool
    try:
        url = urlparse(DATABASE_URL)
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=20,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            sslmode='require'
        )
        logger.info("✅ Database connection pool initialized successfully")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

def init_db():
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                bsc_address TEXT CHECK (bsc_address IS NULL OR bsc_address ~ '^0x[a-fA-F0-9]{40}$'),
                balance INTEGER DEFAULT 0 NOT NULL CHECK (balance >= 0),
                referrals INTEGER DEFAULT 0 NOT NULL CHECK (referrals >= 0),
                referrer_id BIGINT REFERENCES users(user_id),
                participated BOOLEAN DEFAULT FALSE NOT NULL,
                current_task INTEGER DEFAULT 1 NOT NULL CHECK (current_task BETWEEN 1 AND 6),
                task1_completed BOOLEAN DEFAULT FALSE NOT NULL,
                task2_completed BOOLEAN DEFAULT FALSE NOT NULL,
                task3_completed BOOLEAN DEFAULT FALSE NOT NULL,
                task4_completed BOOLEAN DEFAULT FALSE NOT NULL,
                task5_completed BOOLEAN DEFAULT FALSE NOT NULL,
                has_referred BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrer_id ON users(referrer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_participated ON users(participated)")
        
        conn.commit()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/start command from {user.id} ({user.username})")
    
    if not db_pool:
        await update.message.reply_text("⚠️ System is initializing, please try again shortly.")
        return
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT participated, current_task FROM users WHERE user_id = %s", (user.id,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[0]:  # Already completed
            await update.message.reply_text("🎉 You've already completed the airdrop!")
            return
            
        # Insert or update user
        cursor.execute('''
            INSERT INTO users (user_id, username)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET username = EXCLUDED.username
            RETURNING current_task
        ''', (user.id, user.username))
        
        current_task = cursor.fetchone()[0]
        conn.commit()
        
        await show_task(update, context, current_task)
        
    except Exception as e:
        logger.error(f"Start command error: {str(e)}")
        await update.message.reply_text("❌ System error. Please try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def show_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_number: int):
    user = update.effective_user
    logger.info(f"Showing task {task_number} for {user.id}")
    
    tasks = [
        {
            'title': "1️⃣ Join Telegram Group",
            'description': f"Join our Telegram group: t.me/{GROUP_ID}",
            'button': "I Joined ✅",
            'callback': f'task_1_verify',
            'reward': 20
        },
        {
            'title': "2️⃣ Follow Telegram Channel",
            'description': f"Follow our channel: t.me/{CHANNEL_ID}",
            'button': "I'm Following ✅",
            'callback': f'task_2_verify',
            'reward': 20
        },
        {
            'title': "3️⃣ Follow X Account",
            'description': "Follow @soliumcoin on X (Twitter)",
            'button': "I'm Following ✅",
            'callback': f'task_3_verify',
            'reward': 20
        },
        {
            'title': "4️⃣ Retweet Pinned Post",
            'description': "Retweet our pinned X (Twitter) post",
            'button': "I Retweeted ✅",
            'callback': f'task_4_verify',
            'reward': 20
        },
        {
            'title': "5️⃣ Enter BSC Wallet",
            'description': "Enter your BSC address to receive rewards",
            'button': "Enter Address",
            'callback': f'task_5_verify',
            'reward': 20
        }
    ]
    
    if task_number > len(tasks):
        await complete_airdrop(update, context)
        return
    
    task = tasks[task_number-1]
    keyboard = []
    
    # Main task button
    keyboard.append([InlineKeyboardButton(task['button'], callback_data=task['callback'])])
    
    # Add Referral Code button
    keyboard.append([InlineKeyboardButton("🤝 Enter Referral Code", callback_data='enter_referral')])
    
    # Navigation buttons
    nav_buttons = []
    if task_number > 1:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f'show_task_{task_number-1}'))
    if task_number < len(tasks):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f'show_task_{task_number+1}'))
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    message_text = (
        f"🎯 Task {task_number}/{len(tasks)}\n\n"
        f"{task['title']}\n\n"
        f"{task['description']}\n\n"
        f"Reward: +{task['reward']} Solium"
    )
    
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error showing task: {str(e)}")
        await context.bot.send_message(
            chat_id=user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )

async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    logger.info(f"Button pressed: {data} by user_id {user.id}")
    
    # Handle referral code entry
    if data == 'enter_referral':
        context.user_data['awaiting_referral'] = True
        await query.edit_message_text(
            "🤝 Please enter the referral code (user ID):\n\n"
            "Example: 123456789\n\n"
            "⚠️ You cannot use your own ID!"
        )
        return
    
    # Handle task navigation
    if data.startswith('show_task_'):
        try:
            task_number = int(data.split('_')[2])
            await show_task(update, context, task_number)
            return
        except (IndexError, ValueError) as e:
            logger.error(f"Invalid task navigation data: {data}, error: {str(e)}")
            await query.edit_message_text("❌ Invalid task navigation. Please try again.")
            return
    
    # Handle task verification
    if data.startswith('task_') and data.endswith('_verify'):
        try:
            task_number = int(data.split('_')[1])
            await verify_task(update, context, task_number)
            return
        except (IndexError, ValueError) as e:
            logger.error(f"Invalid task verification data: {data}, error: {str(e)}")
            await query.edit_message_text("❌ Invalid task data. Please try again.")
            return

async def verify_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_number: int):
    query = update.callback_query
    user = query.from_user
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT participated FROM users WHERE user_id = %s", (user.id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await query.edit_message_text("❌ User not found. Please /start again.")
            return
            
        if user_data[0]:
            await query.edit_message_text("🎉 You've already completed the airdrop!")
            return
        
        verification_result = None
        if task_number == 1:
            verification_result = await check_telegram_membership(context, user.id, GROUP_ID, 'group')
        elif task_number == 2:
            verification_result = await check_telegram_membership(context, user.id, CHANNEL_ID, 'channel')
        elif task_number in (3, 4):
            verification_result = {'success': True, 'message': "✅ Task recorded"}  # Geçici: X task'ları otomatik geç
        elif task_number == 5:
            context.user_data['awaiting_wallet'] = True
            await query.edit_message_text(
                "💰 Please send your BSC wallet address:\n\n"
                "Format: 0x... (42 characters)\n\n"
                "⚠️ Double-check before sending!"
            )
            return
        
        if verification_result and verification_result['success']:
            task_column = f'task{task_number}_completed'
            cursor.execute(f'''
                UPDATE users 
                SET {task_column} = TRUE,
                    balance = balance + %s,
                    current_task = %s,
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING balance
            ''', (20, task_number + 1, user.id))
            
            new_balance = cursor.fetchone()[0]
            conn.commit()
            
            await query.edit_message_text(
                f"✅ Task {task_number} completed!\n"
                f"+20 Solium added!\n\n"
                f"💰 Total Balance: {new_balance} Solium"
            )
            
            if task_number < 5:
                await show_task(update, context, task_number + 1)
            else:
                await complete_airdrop(update, context)
        else:
            await query.edit_message_text(
                verification_result.get('message', "❌ Verification failed. Try again.")
            )
            
    except Exception as e:
        logger.error(f"Task verification error for user_id {user.id}, task {task_number}: {str(e)}")
        await query.edit_message_text("❌ System error. Please try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def check_telegram_membership(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: str, chat_type: str):
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return {'success': True}
        
        return {
            'success': False,
            'message': f"❌ You haven't joined the {chat_type}!\n\n"
                      f"Please join t.me/{chat_id} and try again."
        }
    except Exception as e:
        logger.error(f"Membership check error for user_id {user_id} in {chat_id}: {str(e)}")
        return {
            'success': False,
            'message': "❌ Verification service unavailable. Try again later."
        }

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wallet_address = update.message.text.strip()

    if not context.user_data.get('awaiting_wallet'):
        return

    # BSC address format validation
    if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
        await update.message.reply_text(
            "❌ **Invalid BSC address!**\n\n"
            "Please enter a **42-character** address starting with `0x`.\n"
            "Example: `0x71C7656EC7ab88b098defB751B7401B5f6d8976F`"
        )
        return

    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE users 
            SET bsc_address = %s,
                task5_completed = TRUE,
                balance = balance + 20,
                current_task = 6,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (wallet_address, user.id))

        new_balance = cursor.fetchone()[0]
        conn.commit()

        await update.message.reply_text(
            f"✅ **Wallet address saved!**\n\n"
            f"💰 **Your new balance:** {new_balance} Solium\n\n"
            f"Completing airdrop..."
        )

        await complete_airdrop(update, context)

    except Exception as e:
        logger.error(f"Wallet save error: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def handle_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.strip()
    
    if not context.user_data.get('awaiting_referral'):
        return
    
    try:
        referrer_id = int(text)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid referral code format!\n\n"
            "Must be a numeric user ID.\n"
            "Example: 123456789\n\n"
            "Please try again:"
        )
        return
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT has_referred, participated FROM users WHERE user_id = %s", (user.id,))
        user_data = cursor.fetchone()
        if not user_data:
            await update.message.reply_text("❌ User not found. Please /start again.")
            return
            
        if user_data[0]:
            await update.message.reply_text("❌ You've already used a referral code!")
            return
            
        if user_data[1]:
            await update.message.reply_text("❌ You've already completed the airdrop, cannot use referral code!")
            return
        
        cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
        if not cursor.fetchone():
            await update.message.reply_text("❌ Invalid referral code: User not found!")
            return
            
        if referrer_id == user.id:
            await update.message.reply_text("❌ You can't refer yourself!")
            return
        
        cursor.execute('''
            UPDATE users 
            SET referrals = referrals + 1,
                balance = balance + 20,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (referrer_id,))
        
        referrer_balance = cursor.fetchone()[0]
        
        cursor.execute('''
            UPDATE users 
            SET referrer_id = %s,
                balance = balance + 20,
                has_referred = TRUE,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (referrer_id, user.id))
        
        user_balance = cursor.fetchone()[0]
        conn.commit()
        
        context.user_data['awaiting_referral'] = False
        await update.message.reply_text(
            f"✅ Referral code accepted!\n"
            f"+20 Solium added to your balance!\n"
            f"💰 Your Balance: {user_balance} Solium\n\n"
            f"Referrer also received +20 Solium."
        )
        
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 User @{user.username or user.id} used your referral code! +20 Solium added!\n"
                     f"💰 Your Balance: {referrer_balance} Solium"
            )
        except Exception as e:
            logger.warning(f"Failed to notify referrer {referrer_id}: {str(e)}")
        
    except Exception as e:
        logger.error(f"Referral code error for user_id {user.id}: {str(e)}")
        await update.message.reply_text("❌ System error while processing referral code. Please try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def complete_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT participated, bsc_address FROM users WHERE user_id = %s", (user.id,))
        user_data = cursor.fetchone()
        if not user_data:
            await update.message.reply_text("❌ User not found. Please /start again.")
            return
            
        if user_data[0]:
            await update.message.reply_text("🎉 You've already completed the airdrop!")
            return
            
        if not user_data[1]:
            await update.message.reply_text("❌ No wallet address provided. Please complete task 5.")
            return
        
        cursor.execute('''
            UPDATE users 
            SET participated = TRUE,
                balance = balance + 100,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (user.id,))
        
        final_balance = cursor.fetchone()[0]
        
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = %s", (user.id,))
        referrer_id = cursor.fetchone()[0]
        if referrer_id:
            cursor.execute('''
                UPDATE users 
                SET balance = balance + 20,
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING balance
            ''', (referrer_id,))
            
            referrer_balance = cursor.fetchone()[0]
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Your referral @{user.username or user.id} completed the airdrop! +20 Solium added!\n"
                         f"💰 Your Balance: {referrer_balance} Solium"
                )
            except Exception as e:
                logger.warning(f"Couldn't notify referrer: {str(e)}")
        
        conn.commit()
        
        completion_text = (
            f"🎉 AIRDROP COMPLETED!\n\n"
            f"💰 Total Earned: {final_balance} Solium\n\n"
            f"Tokens will be distributed to your wallet after verification.\n\n"
            f"Thank you for participating!"
        )
        
        if update.callback_query:
            await update.callback_query.edit_message_text(completion_text)
        else:
            await update.message.reply_text(completion_text)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"🚀 New airdrop completion:\n\n"
                     f"User: @{user.username or 'no_username'} ({user.id})\n"
                     f"Balance: {final_balance} Solium\n"
                     f"Wallet: {user_data[1]}"
            )
        except Exception as e:
            logger.error(f"Admin notification failed: {str(e)}")
            
    except Exception as e:
        logger.error(f"Airdrop completion error for user_id {user.id}: {str(e)}")
        await update.message.reply_text("❌ System error during completion. Please try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

def main():
    try:
        logger.info("🚀 Starting Solium Airdrop Bot")
        
        init_db_pool()
        init_db()
        
        application = Application.builder().token(BOT_TOKEN).build()
        
        handlers = [
            CommandHandler('start', start),
            CallbackQueryHandler(handle_task_button, pattern='^(show_task_|task_.*_verify|enter_referral)'),
            MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: handle_wallet_address(u, c) or handle_referral_code(u, c))
        ]
        
        application.add_handlers(handlers)
        
        logger.info("✅ Bot initialized, starting polling...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=10
        )
        
    except Exception as e:
        logger.critical(f"Fatal error: {str(e)}")
        raise

if __name__ == '__main__':
    main()
