import os
import telebot
import sqlite3
import time
from telebot.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton

# Bot setup
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = telebot.TeleBot(BOT_TOKEN)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_data.db')
if DATABASE_URL.startswith('postgres://'):
    import psycopg2
    def get_db_connection():
        return psycopg2.connect(DATABASE_URL.replace('postgres://', 'postgresql://'))
else:
    def get_db_connection():
        return sqlite3.connect(DATABASE_URL.replace('sqlite:///', ''))

def format_amount(amount):
    return f"{amount:,}".replace(",", " ")

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    web_app_button = KeyboardButton("🎰 Play Casino Web", web_app=WebAppInfo(url="https://your-app-name.onrender.com"))  # Update after deployment
    slots_button = KeyboardButton("🎰 Слоты")
    roulette_button = KeyboardButton("🎲 Рулетка")
    profile_button = KeyboardButton("📊 Профиль")
    bonus_button = KeyboardButton("🎁 Бонус")
    markup.add(web_app_button, slots_button, roulette_button, profile_button, bonus_button)
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (user_id, username, balance, total_won, level, xp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, 1000000, 1000000, 1, 1000000, 'Новичок'))
        conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "Добро пожаловать в Казино! Выберите действие:", reply_markup=get_main_menu())

@bot.message_handler(commands=['profile'])
def profile(message):
    user_id = str(message.from_user.id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, balance, total_won, total_lost, level, xp, status, premium_expiry FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        username, balance, total_won, total_lost, level, xp, status, premium_expiry = user
        premium_status = "💎 Премиум" if premium_expiry > time.time() else "🚫 Нет премиума"
        response = (
            f"📊 Профиль\n"
            f"Имя: @{username}\n"
            f"Баланс: {format_amount(balance)} рублей\n"
            f"Выиграно: {format_amount(total_won)} рублей\n"
            f"Проиграно: {format_amount(total_lost)} рублей\n"
            f"Уровень: {level} ({status})\n"
            f"XP: {xp}/{level * 1000}\n"
            f"Премиум: {premium_status}"
        )
    else:
        response = "Профиль не найден!"
    bot.send_message(message.chat.id, response, reply_markup=get_main_menu())

@bot.message_handler(commands=['bonus'])
def bonus(message):
    user_id = str(message.from_user.id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance, last_bonus FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        bot.send_message(message.chat.id, "Профиль не найден!", reply_markup=get_main_menu())
        return
    balance, last_bonus_time = user
    if last_bonus_time is None or time.time() - last_bonus_time >= 86400:
        bonus = 1000  # Simplified bonus for demo
        new_balance = balance + bonus
        cursor.execute('UPDATE users SET balance = ?, last_bonus = ?, total_won = total_won + ? WHERE user_id = ?',
                       (new_balance, time.time(), bonus, user_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"🎁 Вы получили бонус: {format_amount(bonus)} рублей!", reply_markup=get_main_menu())
    else:
        time_left = int((last_bonus_time + 86400 - time.time()) / 3600)
        conn.close()
        bot.send_message(message.chat.id, f"Бонус доступен через {time_left} часов! ⏳", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "🎰 Слоты")
def slots(message):
    bot.send_message(message.chat.id, "Игра в слоты! (Функционал в Web App)", reply_markup=get_main_menu())

@bot.message_handler(func=lambda message: message.text == "🎲 Рулетка")
def roulette(message):
    bot.send_message(message.chat.id, "Игра в рулетку! (Функционал в Web App)", reply_markup=get_main_menu())

if __name__ == '__main__':
    print("Bot is running...")
    bot.infinity_polling()
