import os
import logging
import re
import json
import random
import string
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

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("Missing BOT_TOKEN!")
    raise ValueError("BOT_TOKEN required")

ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
DATABASE_URL = os.environ.get('DATABASE_URL')

if not DATABASE_URL:
    logger.error("Missing DATABASE_URL!")
    raise ValueError("DATABASE_URL required")

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
        logger.info("✅ Database connection pool initialized")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

def init_db():
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        logger.info("Initializing DB tables...")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                bsc_address TEXT CHECK (bsc_address IS NULL OR bsc_address ~ '^0x[a-fA-F0-9]{40}$'),
                balance INTEGER DEFAULT 0 NOT NULL CHECK (balance >= 0),
                referrals INTEGER DEFAULT 0 NOT NULL CHECK (referrals >= 0),
                referrer_id BIGINT,
                referral_code VARCHAR(10),
                referral_count INTEGER DEFAULT 0,
                referral_rewards INTEGER DEFAULT 0,
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
        
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(10)")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_count INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_rewards INTEGER DEFAULT 0")
        except Exception as e:
            logger.warning(f"Column addition warning: {e}")
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_referrer_id ON users(referrer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_participated ON users(participated)")
        
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_code ON users(referral_code) WHERE referral_code IS NOT NULL")
        except Exception as e:
            logger.warning(f"Index creation warning: {e}")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS referral_code VARCHAR(10)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_referral_code ON users(referral_code) WHERE referral_code IS NOT NULL")
        
        conn.commit()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"DB initialization failed: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

def generate_referral_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/start command from {user.id} ({user.username})")
    
    if not db_pool:
        await update.message.reply_text("⚠️ System initializing, try again soon.")
        return
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT participated, current_task, referral_code, balance FROM users WHERE user_id = %s", (user.id,))
        user_data = cursor.fetchone()
        
        if user_data and user_data[0]:  # Airdrop tamamlanmış
            balance = user_data[3]
            referral_code = user_data[2]
            message = (
                f"🎉 Airdrop already completed!\n\n"
                f"💰 Your Balance: {balance} Solium\n"
                f"🔗 Your Referral Code: {referral_code}\n\n"
                f"Use the buttons below to check your balance or enter a referral code."
            )
            keyboard = [
                [
                    InlineKeyboardButton("💰 Balance", callback_data='show_balance'),
                    InlineKeyboardButton("🤝 Referral", callback_data='enter_referral')
                ]
            ]
            await update.message.reply_text(
                text=message,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
            return
            
        if user_data and not user_data[2]:
            referral_code = generate_referral_code()
            cursor.execute('''
                UPDATE users 
                SET referral_code = %s,
                    updated_at = NOW()
                WHERE user_id = %s
            ''', (referral_code, user.id))
        
        if not user_data:
            referral_code = generate_referral_code()
            cursor.execute('''
                INSERT INTO users (user_id, username, referral_code)
                VALUES (%s, %s, %s)
                RETURNING current_task
            ''', (user.id, user.username, referral_code))
        else:
            cursor.execute('''
                UPDATE users 
                SET username = %s,
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING current_task
            ''', (user.username, user.id))
        
        current_task = cursor.fetchone()[0]
        conn.commit()
        
        if not user_data or not user_data[2]:
            await update.message.reply_text(
                f"🎉 Your unique referral code: {referral_code}\n\n"
                f"Share this code to earn more rewards!"
            )
        
        await show_task(update, context, current_task)
        
    except Exception as e:
        logger.error(f"Start command error: {e}", exc_info=True)
        await update.message.reply_text("❌ System error. Try again.")
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
            'title': "1️⃣ Join Our Telegram Group",
            'description': (
                "Join the official Solium Telegram group @soliumcoinchat to stay updated on project announcements and community events.\n\n"
                "<a href='https://t.me/soliumcoinchat'>Click here to join</a>"
            ),
            'reward': 20
        },
        {
            'title': "2️⃣ Follow Our Telegram Channel",
            'description': (
                "Follow the Solium Telegram channel for the latest news and updates.\n\n"
                "<a href='https://t.me/soliumcoin'>Click here to follow</a>"
            ),
            'reward': 20
        },
        {
            'title': "3️⃣ Follow Solium on X",
            'description': (
                "Follow our official X account (@soliumcoin) to get real-time updates.\n\n"
                "<a href='https://x.com/soliumcoin'>Click here to follow</a>"
            ),
            'reward': 20
        },
        {
            'title': "4️⃣ Retweet Our Pinned Post",
            'description': (
                "Retweet the pinned post on our X account to spread the word about Solium.\n\n"
                "<a href='https://x.com/soliumcoin'>Click here to retweet</a>"
            ),
            'reward': 20
        },
        {
            'title': "5️⃣ Enter Your BSC Wallet",
            'description': (
                "Provide your Binance Smart Chain (BSC) wallet address to receive your Solium rewards.\n\n"
                "Click the 'Enter Address' button below and send your wallet address (e.g., 0x...)."
            ),
            'reward': 20,
            'button': "Enter Address",
            'callback': "task_5_wallet"
        }
    ]
    
    if task_number > len(tasks):
        await complete_airdrop(update, context)
        return
    
    task = tasks[task_number-1]
    keyboard = []
    
    if task_number == 5:
        keyboard.append([InlineKeyboardButton(task['button'], callback_data=task['callback'])])
    
    keyboard.append([
        InlineKeyboardButton("💰 Balance", callback_data='show_balance'),
        InlineKeyboardButton("🤝 Referral", callback_data='enter_referral')
    ])
    
    # Sadece Next butonu
    if task_number < len(tasks):
        keyboard.append([InlineKeyboardButton("Next ▶️", callback_data=f'show_task_{task_number+1}')])
    
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
                parse_mode='HTML',  # HTML için
                disable_web_page_preview=True
            )
        else:
            await update.message.reply_text(
                text=message_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML',  # HTML için
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error showing task: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=user.id,
            text=message_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML',  # HTML için
            disable_web_page_preview=True
        )
async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data
    
    logger.info(f"Button pressed: {data} by user_id {user.id}")
    
    if data == 'enter_referral':
        context.user_data['awaiting_referral'] = True
        await query.edit_message_text(
            "🤝 Please enter the referral code:\n\n"
            "Example: ABC12345\n\n"
            "⚠️ You cannot use your own code!"
        )
        return
    
    if data == 'show_balance':
        await show_user_balance(update, context, query)
        return
    
    if data == 'task_5_wallet':
        context.user_data['awaiting_wallet'] = True
        await query.edit_message_text(
            "💰 Please send your BSC wallet address:\n\n"
            "Format: 0x... (42 characters)\n\n"
            "⚠️ Double-check before sending!"
        )
        return
    
    if data.startswith('show_task_'):
        try:
            task_number = int(data.split('_')[2])
            conn = None
            cursor = None
            try:
                conn = db_pool.getconn()
                cursor = conn.cursor()
                
                if task_number <= 4:
                    task_column = f'task{task_number}_completed'
                    cursor.execute(f'''
                        UPDATE users 
                        SET {task_column} = TRUE,
                            balance = balance + 20,
                            current_task = %s,
                            updated_at = NOW()
                        WHERE user_id = %s
                        RETURNING balance
                    ''', (task_number + 1, user.id))
                    
                    new_balance = cursor.fetchone()[0]
                    conn.commit()
                    logger.info(f"Task {task_number} marked complete for user {user.id}, balance: {new_balance}")
                
                await show_task(update, context, task_number)
                
            except Exception as e:
                logger.error(f"Task update error for user_id {user.id}, task {task_number}: {e}", exc_info=True)
                await query.edit_message_text("❌ System error. Try again.")
                if conn:
                    conn.rollback()
            finally:
                if cursor:
                    cursor.close()
                if conn:
                    db_pool.putconn(conn)
        except (IndexError, ValueError) as e:
            logger.error(f"Invalid task navigation data: {data}, error: {e}")
            await query.edit_message_text("❌ Invalid task navigation. Try again.")

async def show_user_balance(update: Update, context: ContextTypes.DEFAULT_TYPE, query):
    user = query.from_user
    
    logger.info(f"Showing balance for user {user.id}")
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT balance, referral_code, referral_count, referral_rewards 
            FROM users 
            WHERE user_id = %s
        ''', (user.id,))
        
        user_data = cursor.fetchone()
        
        if not user_data:
            logger.warning(f"User {user.id} not found in database")
            await query.edit_message_text("❌ User not found. Use /start first.")
            return
        
        balance, referral_code, referral_count, referral_rewards = user_data
        
        message = (
            f"💰 Balance: {balance} Solium\n"
            f"🔗 Ref Code: {referral_code}\n"
            f"👥 Referrals: {referral_count}\n"
            f"🎁 Rewards: {referral_rewards} Solium"
        )
        
        logger.info(f"Balance shown for user {user.id}: {balance} Solium")
        
        await query.edit_message_text(
            text=message,
            reply_markup=query.message.reply_markup
        )
        
    except Exception as e:
        logger.error(f"Balance check error for user_id {user.id}: {e}", exc_info=True)
        await query.answer("❌ Error showing balance", show_alert=True)
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    wallet_address = update.message.text.strip()
    
    if not context.user_data.get('awaiting_wallet'):
        logger.debug(f"User {user.id} sent text without awaiting wallet: {wallet_address}")
        return
    
    logger.info(f"Attempting to save wallet for user {user.id}: {wallet_address}")
    
    if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
        await update.message.reply_text(
            "❌ Invalid BSC address!\n\nMust be 42 chars starting with 0x.\nExample: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F\n\nTry again:"
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
        
        result = cursor.fetchone()
        if not result:
            logger.error(f"Wallet update failed for user {user.id}: No rows affected")
            await update.message.reply_text("❌ Failed to save wallet. Try again.")
            return
        
        new_balance = result[0]
        conn.commit()
        logger.info(f"Wallet saved for user {user.id}, balance: {new_balance}")
        
        context.user_data['awaiting_wallet'] = False
        await update.message.reply_text(
            f"✅ Wallet address saved!\n+20 Solium added!\n\n💰 Balance: {new_balance} Solium\n\nCompleting airdrop..."
        )
        
        await complete_airdrop(update, context)
        
    except Exception as e:
        logger.error(f"Wallet save error for user_id {user.id}: {e}", exc_info=True)
        await update.message.reply_text(f"❌ System error saving wallet: {str(e)}")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def handle_referral_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referral_code = update.message.text.strip().upper()
    
    if not context.user_data.get('awaiting_referral'):
        logger.debug(f"User {user.id} sent text without awaiting referral: {referral_code}")
        return
    
    logger.info(f"Processing referral code for user {user.id}: {referral_code}")
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT has_referred, participated, referral_code 
            FROM users 
            WHERE user_id = %s
        ''', (user.id,))
        user_data = cursor.fetchone()
        
        if not user_data:
            await update.message.reply_text("❌ User not found. Use /start.")
            return
            
        has_referred, participated, user_referral_code = user_data
        
        if has_referred:
            await update.message.reply_text("❌ You've already used a referral code!")
            return
            
        if participated:
            await update.message.reply_text("❌ Airdrop completed, can't use referral code!")
            return
            
        if referral_code == user_referral_code:
            await update.message.reply_text("❌ You can't use your own referral code!")
            return
        
        cursor.execute('''
            SELECT user_id 
            FROM users 
            WHERE referral_code = %s
        ''', (referral_code,))  # username kaldirildi
        referrer_data = cursor.fetchone()
        
        if not referrer_data:
            await update.message.reply_text("❌ Invalid referral code!")
            return
            
        referrer_id = referrer_data[0]
        
        # Update referrer's balance and stats
        cursor.execute('''
            UPDATE users 
            SET 
                referrals = referrals + 1,
                referral_count = referral_count + 1,
                balance = balance + 20,
                referral_rewards = referral_rewards + 20,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (referrer_id,))
        referrer_new_balance = cursor.fetchone()[0]
        
        # Update user's balance and stats
        cursor.execute('''
            UPDATE users 
            SET 
                referrer_id = %s,
                has_referred = TRUE,
                balance = balance + 20,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (referrer_id, user.id))
        user_new_balance = cursor.fetchone()[0]
        
        conn.commit()
        
        context.user_data['awaiting_referral'] = False
        
        await update.message.reply_text(
            f"✅ Referral code accepted!\n\n"
            f"💰 +20 Solium added to your balance!\n"
            f"💵 Your new balance: {user_new_balance} Solium"
            # Referred by kismi tamamen kaldirildi
        )
        
        try:
            await context.bot.send_message(
                chat_id=referrer_id,
                text=f"🎉 New referral!\n\n"
                     f"A user used your referral code.\n"
                     f"💰 +20 Solium added to your balance!\n"
                     f"💵 Your new balance: {referrer_new_balance} Solium"
            )
        except Exception as e:
            logger.warning(f"Failed to notify referrer {referrer_id}: {e}")
        
    except Exception as e:
        logger.error(f"Referral code error for user_id {user.id}: {e}", exc_info=True)
        await update.message.reply_text("❌ System error processing referral code. Try again.")
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
        
        cursor.execute('''
            SELECT participated, bsc_address, referrer_id, username 
            FROM users 
            WHERE user_id = %s
        ''', (user.id,))  # username eklendi
        user_data = cursor.fetchone()
        
        if not user_data:
            await update.message.reply_text("❌ User not found. Use /start.")
            return
            
        participated, bsc_address, referrer_id, username = user_data
        
        if participated:
            await update.message.reply_text("🎉 Airdrop already completed!")
            return
            
        if not bsc_address:
            await update.message.reply_text("❌ No wallet address provided. Complete Task 5.")
            return
        
        cursor.execute('''
            UPDATE users 
            SET 
                participated = TRUE,
                balance = balance + 100,
                updated_at = NOW()
            WHERE user_id = %s
            RETURNING balance
        ''', (user.id,))
        final_balance = cursor.fetchone()[0]
        
        if referrer_id:
            cursor.execute('''
                UPDATE users 
                SET 
                    balance = balance + 20,
                    referral_rewards = referral_rewards + 20,
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING balance
            ''', (referrer_id,))
            referrer_data = cursor.fetchone()
            referrer_new_balance = referrer_data[0]
            
            try:
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 Your referral completed the airdrop!\n\n"
                         f"💰 +20 Solium added to your balance!\n"
                         f"💵 Your new balance: {referrer_new_balance} Solium"
                )
            except Exception as e:
                logger.warning(f"Couldn't notify referrer: {e}")
        
        conn.commit()
        
        completion_text = (
            f"🎉 AIRDROP COMPLETED!\n\n"
            f"💰 Total Earned: {final_balance} Solium\n\n"
            f"Tokens will be distributed to:\n"
            f"{bsc_address}\n\n"
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
                     f"User: @{username or 'Unknown'}\n"
                     f"User ID: {user.id}\n"
                     f"Wallet: {bsc_address}\n"
                     f"Balance: {final_balance} Solium\n"
                     f"Referrer: {'User ' + str(referrer_id) if referrer_id else 'None'}"
            )
        except Exception as e:
            logger.error(f"Admin notification failed: {e}")
            
    except Exception as e:
        logger.error(f"Airdrop completion error for user_id {user.id}: {e}", exc_info=True)
        await update.message.reply_text("❌ System error during completion. Try again.")
        if conn:
            conn.rollback()
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)

async def export_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        return
        
    logger.info("Admin requested wallet export")
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                user_id, 
                username, 
                bsc_address, 
                balance, 
                referral_code,
                referral_count,
                referral_rewards,
                created_at 
            FROM users 
            WHERE bsc_address IS NOT NULL
            ORDER BY created_at DESC
        ''')
        
        wallets = []
        for row in cursor.fetchall():
            wallets.append({
                'user_id': row[0],
                'username': row[1] or 'no_username',
                'wallet_address': row[2],
                'balance': row[3],
                'referral_code': row[4],
                'referral_count': row[5],
                'referral_rewards': row[6],
                'registration_date': row[7].isoformat()
            })
        
        if not wallets:
            await update.message.reply_text("❌ No wallet addresses found!")
            return
            
        filename = f"solium_wallets_{len(wallets)}.json"
        with open(filename, 'w') as f:
            json.dump(wallets, f, indent=2, ensure_ascii=False)
        
        with open(filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                caption=f"📊 Exported {len(wallets)} wallets",
                filename=filename
            )
        
        os.remove(filename)
        logger.info(f"Exported {len(wallets)} wallets")
        
    except Exception as e:
        logger.error(f"Wallet export error: {e}", exc_info=True)
        await update.message.reply_text("❌ Export failed. Check logs.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            db_pool.putconn(conn)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"/message command from {user.id}")

    # Admin kontrolü
    if user.id != ADMIN_ID:
        await update.message.reply_text("❌ Admin access required!")
        logger.warning(f"Unauthorized /message attempt by user {user.id}")
        return

    # Mesaj içeriğini al
    if not context.args:
        await update.message.reply_text("❌ Please provide a message!\nExample: /message Join our channel: t.me/soliumchannel")
        logger.warning("No message provided for /message command")
        return

    message_text = ' '.join(context.args)
    
    conn = None
    cursor = None
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        
        # Tüm kullanıcı ID'lerini al
        cursor.execute("SELECT user_id FROM users")
        user_ids = [row[0] for row in cursor.fetchall()]
        
        if not user_ids:
            await update.message.reply_text("❌ No users found in database!")
            logger.info("No users to send message to")
            return
        
        sent_count = 0
        failed_count = 0
        
        # Her kullanıcıya mesaj gönder
        for user_id in user_ids:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=message_text,
                    parse_mode='HTML',  # Linkler için HTML desteği
                    disable_web_page_preview=True
                )
                sent_count += 1
                logger.info(f"Message sent to user {user_id}")
            except Exception as e:
                failed_count += 1
                logger.warning(f"Failed to send message to user {user_id}: {e}")
        
        # Admin'e özet gönder
        await update.message.reply_text(
            f"📬 Message sent!\n"
            f"✅ Successfully sent to {sent_count} users\n"
            f"❌ Failed for {failed_count} users\n"
            f"Message: {message_text}"
        )
        logger.info(f"Message broadcast completed: {sent_count} sent, {failed_count} failed")
        
    except Exception as e:
        logger.error(f"Message broadcast error: {e}", exc_info=True)
        await update.message.reply_text("❌ System error while sending messages. Check logs.")
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
        
        # Message handler fonksiyonu
        async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if context.user_data.get('awaiting_wallet'):
                await handle_wallet_address(update, context)
            elif context.user_data.get('awaiting_referral'):
                await handle_referral_code(update, context)
        
        # Handlers
        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('export_wallets', export_wallets))
        application.add_handler(CommandHandler('message', message))  # Yeni handler
        application.add_handler(CallbackQueryHandler(handle_task_button))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
        
        logger.info("✅ Bot initialized, starting polling...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            poll_interval=1.0,
            timeout=10
        )
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main()
