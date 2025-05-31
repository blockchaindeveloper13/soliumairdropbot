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

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@soliumcoin')
GROUP_ID = os.environ.get('GROUP_ID', '@soliumcoinchat')
DATABASE_URL = os.environ.get('DATABASE_URL')

# Database connection pool
db_pool = None

def init_db_pool():
    global db_pool
    try:
        logger.debug(f"Connecting to database: {DATABASE_URL[:20]}...")
        url = urlparse(DATABASE_URL)
        db_pool = psycopg2.pool.SimpleConnectionPool(
            1, 20,
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port,
            sslmode='require'
        )
        logger.info("Database connection pool initialized")
    except Exception as e:
        logger.error(f"Database pool initialization error: {e}", exc_info=True)
        raise

def init_db():
    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        logger.debug("Creating users table if not exists")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                bsc_address TEXT,
                balance INTEGER DEFAULT 0,
                referrals INTEGER DEFAULT 0,
                participated BOOLEAN DEFAULT FALSE,
                current_task INTEGER DEFAULT 1,
                referrer_id BIGINT,
                task1_completed BOOLEAN DEFAULT FALSE,
                task2_completed BOOLEAN DEFAULT FALSE,
                task3_completed BOOLEAN DEFAULT FALSE,
                task4_completed BOOLEAN DEFAULT FALSE,
                task5_completed BOOLEAN DEFAULT FALSE
            )
        ''')
        # Add missing columns if they don't exist
        columns = [
            ("participated", "BOOLEAN DEFAULT FALSE"),
            ("current_task", "INTEGER DEFAULT 1"),
            ("task1_completed", "BOOLEAN DEFAULT FALSE"),
            ("task2_completed", "BOOLEAN DEFAULT FALSE"),
            ("task3_completed", "BOOLEAN DEFAULT FALSE"),
            ("task4_completed", "BOOLEAN DEFAULT FALSE"),
            ("task5_completed", "BOOLEAN DEFAULT FALSE")
        ]
        for column, column_type in columns:
            cursor.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {column} {column_type}")
        conn.commit()
        logger.info("Database initialized successfully")
        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
        raise

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    args = context.args
    logger.debug(f"Start command received for user_id: {user_id}, args: {args}")

    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        # Test simple query
        cursor.execute("SELECT 1")
        logger.debug("Test query successful")

        # Check if user exists
        cursor.execute("SELECT participated FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if user and user[0]:
            await update.message.reply_text("🎉 You've already participated in the airdrop! You can't join again.")
            cursor.close()
            db_pool.putconn(conn)
            return

        # Handle referral
        if args and args[0].startswith("ref"):
            try:
                referrer_id = int(args[0][3:])
                logger.debug(f"Referrer ID: {referrer_id}")
                if referrer_id != user_id:
                    cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
                    if cursor.fetchone():
                        cursor.execute(
                            "UPDATE users SET referrals = referrals + 1, balance = balance + 20 WHERE user_id = %s",
                            (referrer_id,)
                        )
                        cursor.execute(
                            "INSERT INTO users (user_id, balance, referrer_id) VALUES (%s, 20, %s) ON CONFLICT (user_id) DO NOTHING",
                            (user_id, referrer_id)
                        )
                        await update.message.reply_text(
                            "🎉 You joined through a referral link! Both you and the referrer received 20 Solium."
                        )
                    else:
                        logger.warning(f"Referrer ID {referrer_id} not found")
                        cursor.execute(
                            "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                            (user_id,)
                        )
                else:
                    cursor.execute(
                        "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                        (user_id,)
                    )
            except ValueError as ve:
                logger.error(f"Invalid referrer ID: {ve}")
                cursor.execute(
                    "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                    (user_id,)
                )
        else:
            cursor.execute(
                "INSERT INTO users (user_id) VALUES (%s) ON CONFLICT DO NOTHING",
                (user_id,)
            )

        conn.commit()
        cursor.close()
        db_pool.putconn(conn)
        logger.debug(f"User {user_id} inserted/updated, showing task 1")
        await show_task(update, context, 1)
    except Exception as e:
        logger.error(f"Error in start: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def show_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_number: int):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    logger.debug(f"Showing task {task_number} for user_id: {user_id}")

    tasks = [
        {
            'title': "1️⃣ Join Telegram Group",
            'description': f"Join our official Telegram group: {GROUP_ID}",
            'button': "I Joined ✅",
            'field': 'task1_completed'
        },
        {
            'title': "2️⃣ Follow Telegram Channel",
            'description': f"Follow our official Telegram channel: {CHANNEL_ID}",
            'button': "I'm Following ✅",
            'field': 'task2_completed'
        },
        {
            'title': "3️⃣ Follow X Account",
            'description': "Follow our official X account: @soliumcoin",
            'button': "I'm Following ✅",
            'field': 'task3_completed'
        },
        {
            'title': "4️⃣ Retweet Pinned Post",
            'description': "Retweet our pinned post on X from @soliumcoin",
            'button': "I Retweeted ✅",
            'field': 'task4_completed'
        },
        {
            'title': "5️⃣ Enter Your BSC Wallet Address",
            'description': "Enter your BSC wallet address to receive rewards",
            'button': "Enter My Address",
            'field': 'task5_completed'
        }
    ]

    if task_number <= len(tasks):
        task = tasks[task_number-1]
        keyboard = [[InlineKeyboardButton(task['button'], callback_data=f'task_done_{task_number}')]]
        if task_number > 1:
            keyboard.append([InlineKeyboardButton("◀️ Previous Task", callback_data=f'task_{task_number-1}')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        text = (
            f"🎯 Task {task_number}/{len(tasks)}\n\n"
            f"{task['title']}\n\n"
            f"{task['description']}\n\n"
            f"Click '{task['button']}' after completing the task."
        )
        try:
            if update.message:
                await update.message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
            else:
                await update.callback_query.edit_message_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            await (update.callback_query.message or update.message).reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    else:
        await complete_airdrop(update, context)

async def handle_task_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data
    logger.debug(f"Handling task button: {data} for user_id: {user_id}")

    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()
        cursor.execute("SELECT participated FROM users WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()

        if user and user['participated']:
            await query.message.reply_text("❌ You've already completed the airdrop!")
            cursor.close()
            db_pool.putconn(conn)
            return

        if data.startswith('task_'):
            task_number = int(data.split('_')[1])
            await show_task(update, context, task_number)
        elif data.startswith('task_done_'):
            task_number = int(data.split('_')[2])
            next_task = task_number + 1
            tasks = [
                {'field': 'task1_completed', 'check': lambda: check_telegram_group(context, user_id)},
                {'field': 'task2_completed', 'check': lambda: check_telegram_channel(context, user_id)},
                {'field': 'task3_completed', 'check': lambda: manual_check(query, "X account followed", 20)},
                {'field': 'task4_completed', 'check': lambda: manual_check(query, "Pinned post retweeted", 20)},
                {'field': 'task5_completed', 'check': lambda: wallet_check(context, query, user_id)}
            ]
            if task_number <= len(tasks):
                task = tasks[task_number-1]
                result = await task['check']()
                if result.get('success'):
                    cursor.execute(
                        f"UPDATE users SET {task['field']} = TRUE, balance = balance + %s, current_task = %s WHERE user_id = %s",
                        (result.get('reward', 0), next_task, user_id)
                    )
                    conn.commit()
                    await query.message.reply_text(
                        f"✅ Task {task_number} completed!\n"
                        f"+{result.get('reward', 0)} Solium earned!\n\n"
                        f"Proceeding to the next task..."
                    )
                    await show_task(update, context, next_task)
                else:
                    await query.message.reply_text(result.get('message', "❌ Task not completed!"))
            else:
                await complete_airdrop(update, context)

        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error in handle_task_button: {e}", exc_info=True)
        await query.message.reply_text("❌ An error occurred. Please try again later.")

async def check_telegram_group(context, user_id):
    try:
        member = await context.bot.get_chat_member(GROUP_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return {'success': True, 'reward': 20}
        return {'success': False, 'message': f"❌ You haven't joined {GROUP_ID}!\nPlease join and try again."}
    except Exception as e:
        logger.error(f"Telegram group check error: {e}")
        return {'success': False, 'message': "❌ Error checking group membership. Try again later."}

async def check_telegram_channel(context, user_id):
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'administrator', 'creator']:
            return {'success': True, 'reward': 20}
        return {'success': False, 'message': f"❌ You haven't joined {CHANNEL_ID}!\nPlease follow and try again."}
    except Exception as e:
        logger.error(f"Telegram channel check error: {e}")
        return {'success': False, 'message': "❌ Error checking channel membership. Try again later."}

async def manual_check(query, message, reward):
    await query.message.reply_text(
        f"✅ {message}! This will be manually verified by admins.\n"
        f"+{reward} Solium recorded."
    )
    return {'success': True, 'reward': reward}

async def wallet_check(context, query, user_id):
    await query.message.reply_text(
        "💰 Please send your BSC wallet address:\n\n"
        "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F\n\n"
        "⚠️ Double-check your address!"
    )
    context.user_data['awaiting_wallet'] = True
    return {'success': False}

async def handle_wallet_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text.strip()
    logger.debug(f"Received wallet address: {text} for user_id: {user_id}")

    if not context.user_data.get('awaiting_wallet'):
        return

    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        if re.match(r'^0x[a-fA-F0-9]{40}$', text):
            cursor.execute(
                "UPDATE users SET bsc_address = %s, task5_completed = TRUE, balance = balance + 20, current_task = 6 WHERE user_id = %s",
                (text, user_id)
            )
            conn.commit()
            await update.message.reply_text(
                "✅ Your wallet address has been saved!\n"
                "+20 Solium earned!\n\n"
                "Completing the airdrop process..."
            )
            context.user_data['awaiting_wallet'] = False
            await complete_airdrop(update, context)
        else:
            await update.message.reply_text(
                "❌ Invalid BSC wallet address format!\n\n"
                "Please enter a valid address (42 characters starting with 0x).\n"
                "Example: 0x71C7656EC7ab88b098defB751B7401B5f6d8976F"
            )

        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error in handle_wallet_address: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred. Please try again later.")

async def complete_airdrop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id if update.message else update.callback_query.from_user.id
    logger.debug(f"Completing airdrop for user_id: {user_id}")

    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE users SET balance = balance + 100, participated = TRUE WHERE user_id = %s",
            (user_id,)
        )
        cursor.execute("SELECT referrer_id FROM users WHERE user_id = %s", (user_id,))
        referrer = cursor.fetchone()
        if referrer and referrer['referrer_id']:
            cursor.execute(
                "UPDATE users SET balance = balance + 20 WHERE user_id = %s",
                (referrer['referrer_id'],)
            )
            try:
                await context.bot.send_message(
                    referrer['referrer_id'],
                    "🎉 Your referral completed the airdrop! You earned +20 Solium."
                )
            except Exception as e:
                logger.error(f"Error sending referral notification: {e}")

        conn.commit()
        cursor.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
        balance = cursor.fetchone()['balance']

        await (update.message or update.callback_query.message).reply_text(
            f"🎉 CONGRATULATIONS! Airdrop completed!\n\n"
            f"💵 Total Earned: {balance} Solium\n\n"
            f"Rewards will be sent to your BSC address."
        )

        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error in complete_airdrop: {e}", exc_info=True)
        await (update.message or update.callback_query.message).reply_text("❌ An error occurred. Please try again later.")

async def export_addresses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Only admins can use this command!")
        return

    try:
        conn = db_pool.getconn()
        cursor = conn.cursor()

        cursor.execute("SELECT user_id, bsc_address FROM users WHERE bsc_address IS NOT NULL")
        addresses = [{'user_id': row['user_id'], 'bsc_address': row['bsc_address']} for row in cursor.fetchall()]

        if not addresses:
            await update.message.reply_text("❌ No wallet addresses found!")
            cursor.close()
            db_pool.putconn(conn)
            return

        filename = "bsc_addresses.json"
        with open(filename, 'w') as f:
            json.dump(addresses, f, indent=2)

        try:
            with open(filename, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    caption=f"📋 Total {len(addresses)} BSC wallet addresses"
                )
        except Exception as e:
            await update.message.reply_text(f"❌ Error sending file: {str(e)}")
        finally:
            try:
                os.remove(filename)
            except:
                pass

        cursor.close()
        db_pool.putconn(conn)
    except Exception as e:
        logger.error(f"Error in export_addresses: {e}", exc_info=True)
        await update.message.reply_text("❌ An error occurred. Please try again later.")

def main():
    try:
        logger.info("Initializing database...")
        init_db_pool()
        init_db()
        logger.info("Building application...")
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('export', export_addresses))
        application.add_handler(CallbackQueryHandler(handle_task_button, pattern='^(task_|task_done_)'))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_address))

        logger.info("🚀 Starting bot in polling mode...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=['message', 'callback_query'],
            poll_interval=1.0
        )
    except Exception as e:
        logger.error(f"Error starting bot: {e}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
