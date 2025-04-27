import os
import telebot
from flask import Flask, request, render_template, abort
import psycopg2
import logging
import hmac
import hashlib
import json
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN', '7473315933:AAHx8W5gbffy7ICYhZAgypOJV9Z8Ym-Va2A')
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://casino_db_puaq_user:kyDkwkYOHnUrQXvildekqxPD2AiJMkUE@dpg-d067pb2li9vc73e38d70-a.oregon-postgres.render.com/casino_db_puaq?sslmode=require')
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key')  # Generate in Render

# Initialize Telegram bot
bot = telebot.TeleBot(BOT_TOKEN)

# Database connection
def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        logger.info("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise

# Initialize database
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                last_bonus TIMESTAMP
            )
        ''')
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

# Validate Telegram Web App initData
def validate_init_data(init_data, bot_token):
    try:
        parsed_data = dict(param.split('=') for param in init_data.split('&'))
        check_hash = parsed_data.pop('hash', None)
        data_check_string = '\n'.join(f'{k}={v}' for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
        computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        return computed_hash == check_hash
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False

# Initialize database on startup
try:
    init_db()
except Exception as e:
    logger.error(f"Failed to initialize database on startup: {e}")
    raise

# Telegram bot handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    username = message.from_user.username or 'Unknown'
    logger.info(f"Processing /start for user_id: {user_id}, username: {username}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO users (user_id, username) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING',
            (user_id, username)
        )
        conn.commit()
        bot.reply_to(message, "Welcome to Casino Web! Use /profile to view your profile or /bonus to claim a daily bonus.")
        logger.info(f"User {user_id} registered successfully")
    except Exception as e:
        logger.error(f"Error in /start for user {user_id}: {e}")
        bot.reply_to(message, "An error occurred. Please try again later.")
    finally:
        cursor.close()
        conn.close()

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = message.from_user.id
    logger.info(f"Processing /profile for user_id: {user_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT username, balance FROM users WHERE user_id = %s', (user_id,))
        user = cursor.fetchone()
        if user:
            bot.reply_to(message, f"Profile:\nUsername: {user[0]}\nBalance: {user[1]} coins")
            logger.info(f"Profile retrieved for user {user_id}")
        else:
            bot.reply_to(message, "Profile not found. Use /start to register.")
            logger.info(f"No profile found for user {user_id}")
    except Exception as e:
        logger.error(f"Error in /profile for user {user_id}: {e}")
        bot.reply_to(message, "An error occurred. Please try again later.")
    finally:
        cursor.close()
        conn.close()

@bot.message_handler(commands=['bonus'])
def bonus(message):
    user_id = message.from_user.id
    logger.info(f"Processing /bonus for user_id: {user_id}")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT last_bonus FROM users WHERE user_id = %s', (user_id,))
        last_bonus = cursor.fetchone()
        if last_bonus and last_bonus[0] and (datetime.now() - last_bonus[0]).total_seconds() < 86400:
            bot.reply_to(message, "You can claim a bonus once every 24 hours. Try again later.")
            logger.info(f"Bonus denied for user {user_id}: too soon")
        else:
            cursor.execute(
                'UPDATE users SET balance = balance + 100, last_bonus = %s WHERE user_id = %s',
                (datetime.now(), user_id)
            )
            conn.commit()
            bot.reply_to(message, "You claimed a 100-coin bonus!")
            logger.info(f"Bonus claimed for user {user_id}")
    except Exception as e:
        logger.error(f"Error in /bonus for user {user_id}: {e}")
        bot.reply_to(message, "An error occurred. Please try again later.")
    finally:
        cursor.close()
        conn.close()

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        try:
            json_data = request.get_json()
            logger.info(f"Received webhook update: {json_data}")
            update = telebot.types.Update.de_json(json_data)
            if update:
                bot.process_new_updates([update])
                logger.info("Webhook processed successfully")
                return '', 200
            else:
                logger.warning("Invalid update received")
                return '', 400
        except Exception as e:
            logger.error(f"Webhook processing failed: {e}")
            return '', 500
    logger.warning(f"Invalid content-type: {request.headers.get('content-type')}")
    return '', 403

# Web App endpoint
@app.route('/')
def index():
    init_data = request.args.get('tgWebAppData', '')
    if not init_data or not validate_init_data(init_data, BOT_TOKEN):
        logger.warning("Invalid tgWebAppData")
        abort(403)
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        abort(500)

# Health check endpoint
@app.route('/health')
def health():
    return 'OK', 200

# Main entry point
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    logger.info(f"Starting application on port {port}")
    try:
        bot.remove_webhook()
        webhook_url = "https://web-1ov4.onrender.com/webhook"
        bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook set to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
    app.run(host="0.0.0.0", port=port)
