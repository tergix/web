import os
import time
import hmac
import hashlib
import psycopg2
import telebot
from telebot.types import WebAppInfo,ReplyKeyboardMarkup,KeyboardButton
from flask import Flask,request,render_template,jsonify,abort
app=Flask(__name__)
app.config['SECRET_KEY']=os.getenv('SECRET_KEY','a1b2c3d4e5f6g7h8')
BOT_TOKEN=os.getenv('BOT_TOKEN','7473315933:AAHx8W5gbffy7ICYhZAgypOJV9Z8Ym-Va2A')
bot=telebot.TeleBot(BOT_TOKEN)
DATABASE_URL=os.getenv('DATABASE_URL','postgresql://casino_db_puaq_user:kyDkwkYOHnUrQXvildekqxPD2AiJMkUE@dpg-d067pb2li9vc73e38d70-a/casino_db_puaq')
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)
def init_db():
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            username TEXT,
            balance INTEGER DEFAULT 1000000,
            total_won INTEGER DEFAULT 0,
            total_lost INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Новичок',
            premium_expiry INTEGER DEFAULT 0,
            last_bonus INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully")
init_db()
def validate_init_data(init_data,bot_token):
    try:
        data={k:v for k,v in (pair.split('=') for pair in init_data.split('&'))}
        received_hash=data.pop('hash','')
        data_check_string='\n'.join(f"{k}={v}" for k,v in sorted(data.items()))
        secret_key=hmac.new("WebAppData".encode(),bot_token.encode(),hashlib.sha256).digest()
        computed_hash=hmac.new(secret_key,data_check_string.encode(),hashlib.sha256).hexdigest()
        return computed_hash==received_hash
    except Exception:
        return False
def format_amount(amount):
    return f"{amount:,}".replace(","," ")
def get_main_menu():
    markup=ReplyKeyboardMarkup(resize_keyboard=True,row_width=2)
    web_app_button=KeyboardButton("🎰 Play Casino Web",web_app=WebAppInfo(url="https://casino-web.onrender.com"))
    slots_button=KeyboardButton("🎰 Слоты")
    roulette_button=KeyboardButton("🎲 Рулетка")
    profile_button=KeyboardButton("📊 Профиль")
    bonus_button=KeyboardButton("🎁 Бонус")
    markup.add(web_app_button,slots_button,roulette_button,profile_button,bonus_button)
    return markup
@bot.message_handler(commands=['start'])
def start(message):
    user_id=str(message.from_user.id)
    username=message.from_user.username or message.from_user.first_name
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = %s',(user_id,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (user_id,username,balance,total_won,level,xp,status)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        ''',(user_id,username,1000000,1000000,1,1000000,'Новичок'))
        conn.commit()
    conn.close()
    bot.send_message(message.chat.id,"Добро пожаловать в Казино! Выберите действие:",reply_markup=get_main_menu())
@bot.message_handler(commands=['profile'])
def profile(message):
    user_id=str(message.from_user.id)
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('SELECT username,balance,total_won,total_lost,level,xp,status,premium_expiry FROM users WHERE user_id = %s',(user_id,))
    user=cursor.fetchone()
    conn.close()
    if user:
        username,balance,total_won,total_lost,level,xp,status,premium_expiry=user
        premium_status="💎 Премиум" if premium_expiry>time.time() else "🚫 Нет премиума"
        response=f"📊 Профиль\nИмя: @{username}\nБаланс: {format_amount(balance)} рублей\nВыиграно: {format_amount(total_won)} рублей\nПроиграно: {format_amount(total_lost)} рублей\nУровень: {level} ({status})\nXP: {xp}/{level*1000}\nПремиум: {premium_status}"
    else:
        response="Профиль не найден!"
    bot.send_message(message.chat.id,response,reply_markup=get_main_menu())
@bot.message_handler(commands=['bonus'])
def bonus(message):
    user_id=str(message.from_user.id)
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('SELECT balance,last_bonus FROM users WHERE user_id = %s',(user_id,))
    user=cursor.fetchone()
    if not user:
        conn.close()
        bot.send_message(message.chat.id,"Профиль не найден!",reply_markup=get_main_menu())
        return
    balance,last_bonus_time=user
    if last_bonus_time is None or time.time()-last_bonus_time>=86400:
        bonus=1000
        new_balance=balance+bonus
        cursor.execute('UPDATE users SET balance=%s,last_bonus=%s,total_won=total_won+%s WHERE user_id=%s',(new_balance,time.time(),bonus,user_id))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id,f"🎁 Вы получили бонус: {format_amount(bonus)} рублей!",reply_markup=get_main_menu())
    else:
        time_left=int((last_bonus_time+86400-time.time())/3600)
        conn.close()
        bot.send_message(message.chat.id,f"Бонус доступен через {time_left} часов! ⏳",reply_markup=get_main_menu())
@bot.message_handler(func=lambda message:message.text=="🎰 Слоты")
def slots(message):
    bot.send_message(message.chat.id,"Игра в слоты! (Функционал в Web App)",reply_markup=get_main_menu())
@bot.message_handler(func=lambda message:message.text=="🎲 Рулетка")
def roulette(message):
    bot.send_message(message.chat.id,"Игра в рулетку! (Функционал в Web App)",reply_markup=get_main_menu())
@app.route('/')
def index():
    init_data=request.args.get('tgWebAppData','')
    if not init_data or not validate_init_data(init_data,BOT_TOKEN):
        abort(403)
    return render_template('index.html')
@app.route('/profile')
def profile_page():
    init_data=request.args.get('tgWebAppData','')
    if not init_data or not validate_init_data(init_data,BOT_TOKEN):
        abort(403)
    user_id=init_data.split('&')[0].split('=')[1]
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('SELECT username,balance,level,status FROM users WHERE user_id = %s',(user_id,))
    user=cursor.fetchone()
    conn.close()
    if user:
        return render_template('profile.html',username=user[0],balance=format_amount(user[1]),level=user[2],status=user[3])
    abort(404)
@app.route('/slots')
def slots_page():
    init_data=request.args.get('tgWebAppData','')
    if not init_data or not validate_init_data(init_data,BOT_TOKEN):
        abort(403)
    return render_template('slots.html')
@app.route('/roulette')
def roulette_page():
    init_data=request.args.get('tgWebAppData','')
    if not init_data or not validate_init_data(init_data,BOT_TOKEN):
        abort(403)
    return render_template('roulette.html')
@app.route('/update_balance',methods=['POST'])
def update_balance():
    init_data=request.args.get('tgWebAppData','')
    if not init_data or not validate_init_data(init_data,BOT_TOKEN):
        abort(403)
    user_id=init_data.split('&')[0].split('=')[1]
    data=request.get_json()
    amount=data.get('amount',0)
    conn=get_db_connection()
    cursor=conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = %s',(user_id,))
    user=cursor.fetchone()
    if user:
        new_balance=user[0]+amount
        total_won=amount if amount>0 else 0
        total_lost=-amount if amount<0 else 0
        cursor.execute('''
            UPDATE users SET balance=%s,total_won=total_won+%s,total_lost=total_lost+%s WHERE user_id=%s
        ''',(new_balance,total_won,total_lost,user_id))
        conn.commit()
        conn.close()
        return jsonify({'balance':format_amount(new_balance)})
    conn.close()
    abort(404)
@app.route('/webhook',methods=['POST'])
def webhook():
    if request.headers.get('content-type')=='application/json':
        json_string=request.get_data().decode('utf-8')
        update=telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return '',200
    return '',403
if __name__=='__main__':
    bot.remove_webhook()
    bot.set_webhook(url="https://casino-web.onrender.com/webhook")
    app.run(host="0.0.0.0",port=int(os.getenv('PORT',5000)))
