import os
import sqlite3
import random
import time
import hmac
import hashlib
import urllib.parse
from flask import Flask, request, render_template, session, redirect, url_for, jsonify
from flask_session import Session
from telegram import Bot
import logging

# Setup logging
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', encoding='utf-8')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')  # Change in production
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Telegram Bot setup
BOT_TOKEN = os.getenv('BOT_TOKEN')
bot = Bot(token=BOT_TOKEN)

# Database setup
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_data.db')
if DATABASE_URL.startswith('postgres://'):
    import psycopg2
    def get_db_connection():
        return psycopg2.connect(DATABASE_URL.replace('postgres://', 'postgresql://'))
else:
    def get_db_connection():
        return sqlite3.connect(DATABASE_URL.replace('sqlite:///', ''))

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                balance INTEGER DEFAULT 0,
                total_won INTEGER DEFAULT 0,
                total_lost INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                xp INTEGER DEFAULT 0,
                status TEXT DEFAULT 'Новичок',
                premium_expiry REAL DEFAULT 0,
                last_bonus REAL DEFAULT 0,
                last_slots_spin REAL DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS blocked_users (
                user_id TEXT PRIMARY KEY
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                user_id TEXT,
                referred_id TEXT,
                PRIMARY KEY (user_id, referred_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

# Global variables
HOST_IDS = {'861123574'}  # Admin IDs
current_bets = {}
muted_users = {}
auto_slots = {}
roulette_numbers = {}
blackjack_games = {}
dice_games = {}
rocket_games = {}
recent_players = []

def load_data():
    global recent_players, HOST_IDS
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM settings WHERE key = ?', ('recent_players',))
        result = cursor.fetchone()
        if result:
            recent_players = eval(result[0]) if result[0] else []
        cursor.execute('SELECT value FROM settings WHERE key = ?', ('HOST_IDS',))
        result = cursor.fetchone()
        if result:
            HOST_IDS.update(eval(result[0]) if result[0] else ['861123574'])
        conn.close()
        logger.info("Data loaded successfully")
    except Exception as e:
        logger.error(f"Data load error: {e}")

def save_data():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('recent_players', str(recent_players)))
        cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', ('HOST_IDS', str(list(HOST_IDS))))
        conn.commit()
        conn.close()
        logger.info("Data saved successfully")
    except Exception as e:
        logger.error(f"Data save error: {e}")

def format_amount(amount):
    return f"{amount:,}".replace(",", " ")

def is_blocked(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM blocked_users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_recent_player(user_id):
    if user_id not in recent_players:
        recent_players.append(user_id)
        if len(recent_players) > 10:
            recent_players.pop(0)
        save_data()

def validate_init_data(init_data):
    try:
        logger.info(f"Received init_data: {init_data}")
        parsed_data = urllib.parse.parse_qs(init_data)
        if not parsed_data:
            logger.error("Empty parsed_data")
            return False
        data_check_string = '\n'.join(f"{key}={value[0]}" for key, value in sorted(parsed_data.items()) if key != 'hash')
        logger.info(f"Data check string: {data_check_string}")
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        data_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        logger.info(f"Computed hash: {data_hash}, Received hash: {parsed_data.get('hash', [''])[0]}")
        return data_hash == parsed_data['hash'][0]
    except Exception as e:
        logger.error(f"Init data validation error: {e}")
        return False

def get_user_from_init_data(init_data):
    try:
        parsed_data = urllib.parse.parse_qs(init_data)
        user_data = eval(parsed_data['user'][0])  # JSON string
        return {
            'user_id': str(user_data['id']),
            'username': user_data.get('username', user_data.get('first_name', 'User'))
        }
    except Exception as e:
        logger.error(f"User data parsing error: {e}")
        return None

@app.route('/')
def index():
    init_data = request.args.get('tgWebAppData', '')
    if not init_data or not validate_init_data(init_data):
        logger.error("Invalid or missing init_data")
        return "Invalid Telegram Web App data!", 403
    user = get_user_from_init_data(init_data)
    if not user:
        logger.error("Failed to authenticate user")
        return "Failed to authenticate user!", 403
    user_id = user['user_id']
    username = user['username']
    session['user_id'] = user_id
    session['username'] = username
    if is_blocked(user_id):
        return "You are blocked!", 403
    if user_id in muted_users and muted_users[user_id] > time.time():
        return "You are muted!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_id,))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO users (user_id, username, balance, total_won, level, xp, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, 1000000, 1000000, 1, 1000000, 'Новичок'))
        conn.commit()
        logger.info(f"New user registered: {user_id} (@{username})")
    conn.close()
    add_recent_player(user_id)
    return render_template('index.html', is_admin=user_id in HOST_IDS)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, balance, total_won, total_lost, level, xp, status, premium_expiry FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        logger.error(f"Profile not found for user_id {user_id}")
        return "User not found!", 404
    username, balance, total_won, total_lost, level, xp, status, premium_expiry = user
    premium_status = "💎 Премиум" if premium_expiry > time.time() else "🚫 Нет премиума"
    return render_template('profile.html', username=username, balance=format_amount(balance), total_won=format_amount(total_won),
                          total_lost=format_amount(total_lost), level=level, status=status, xp=xp, premium_status=premium_status)

@app.route('/slots', methods=['GET', 'POST'])
def slots():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if request.method == 'POST':
        try:
            bet = int(request.form.get('bet', 1000))
            if bet < 100:
                return jsonify({'error': 'Ставка должна быть не менее 100 рублей!'})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance, premium_expiry FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user or user[0] < bet:
                conn.close()
                return jsonify({'error': f"Недостаточно средств! У вас {format_amount(user[0] if user else 0)} рублей 😢"})
            balance, premium_expiry = user
            balance -= bet
            cursor.execute('UPDATE users SET balance = ?, total_lost = total_lost + ? WHERE user_id = ?', (balance, bet, user_id))
            symbols = ["🐶", "🐱", "🐭", "🐰", "🦊"]
            result = [random.choice(symbols) for _ in range(3)]
            win = 0
            if result[0] == result[1] == result[2]:
                win = bet * 5
            elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
                win = bet * 2
            if premium_expiry > time.time():
                win = int(win * 1.5)
            if win > 0:
                balance += win
                cursor.execute('UPDATE users SET balance = ?, total_won = total_won + ? WHERE user_id = ?', (balance, win, user_id))
                add_xp(user_id, win)
            conn.commit()
            conn.close()
            logger.info(f"Slots played by {user_id}: Bet={bet}, Result={result}, Win={win}")
            return jsonify({
                'result': ' | '.join(result),
                'win': win,
                'balance': format_amount(balance),
                'message': f"{'🏆 Выигрыш: ' + format_amount(win) + ' рублей!' if win > 0 else '😢 Проигрыш!'}"
            })
        except Exception as e:
            logger.error(f"Slots error for {user_id}: {e}")
            return jsonify({'error': 'Ошибка при игре в слоты!'}), 500
    return render_template('slots.html', bet=1000)

@app.route('/roulette', methods=['GET', 'POST'])
def roulette():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if request.method == 'POST':
        try:
            bet = int(request.form.get('bet', 1000))
            bet_type = request.form.get('bet_type')
            if bet < 100:
                return jsonify({'error': 'Ставка должна быть не менее 100 рублей!'})
            if not bet_type:
                return jsonify({'error': 'Выберите тип ставки!'})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance, premium_expiry FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user or user[0] < bet:
                conn.close()
                return jsonify({'error': f"Недостаточно средств! У вас {format_amount(user[0] if user else 0)} рублей 😢"})
            balance, premium_expiry = user
            balance -= bet
            cursor.execute('UPDATE users SET balance = ?, total_lost = total_lost + ? WHERE user_id = ?', (balance, bet, user_id))
            number = random.randint(0, 36)
            color = "🟢" if number == 0 else "🔴" if number in [1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36] else "⚫"
            win = 0
            if bet_type == "red" and color == "🔴":
                win = bet * 2
            elif bet_type == "black" and color == "⚫":
                win = bet * 2
            elif bet_type == "green" and color == "🟢":
                win = bet * 36
            elif bet_type == "1-12" and 1 <= number <= 12:
                win = bet * 3
            elif bet_type == "13-24" and 13 <= number <= 24:
                win = bet * 3
            elif bet_type == "25-36" and 25 <= number <= 36:
                win = bet * 3
            elif bet_type == "even" and number % 2 == 0 and number != 0:
                win = bet * 2
            elif bet_type == "odd" and number % 2 == 1:
                win = bet * 2
            elif bet_type.isdigit() and int(bet_type) == number:
                win = bet * 36
            if premium_expiry > time.time():
                win = int(win * 1.5)
            if win > 0:
                balance += win
                cursor.execute('UPDATE users SET balance = ?, total_won = total_won + ? WHERE user_id = ?', (balance, win, user_id))
                add_xp(user_id, win)
            conn.commit()
            conn.close()
            logger.info(f"Roulette played by {user_id}: Bet={bet}, Type={bet_type}, Result={number} {color}, Win={win}")
            return jsonify({
                'result': f"{number} {color}",
                'win': win,
                'balance': format_amount(balance),
                'message': f"{'🏆 Выигрыш: ' + format_amount(win) + ' рублей!' if win > 0 else '😢 Проигрыш!'}"
            })
        except Exception as e:
            logger.error(f"Roulette error for {user_id}: {e}")
            return jsonify({'error': 'Ошибка при игре в рулетку!'}), 500
    return render_template('roulette.html', bet=1000)

@app.route('/rocket', methods=['GET', 'POST'])
def rocket():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            bet = int(request.form.get('bet', 1000))
            if bet < 100:
                return jsonify({'error': 'Ставка должна быть не менее 100 рублей!'})
            if action == 'start':
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT balance, premium_expiry FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
                if not user or user[0] < bet:
                    conn.close()
                    return jsonify({'error': f"Недостаточно средств! У вас {format_amount(user[0] if user else 0)} рублей 😢"})
                balance, premium_expiry = user
                balance -= bet
                cursor.execute('UPDATE users SET balance = ?, total_lost = total_lost + ? WHERE user_id = ?', (balance, bet, user_id))
                conn.commit()
                conn.close()
                rocket_games[user_id] = {
                    'bet': bet,
                    'current_coef': 1.0,
                    'crash_point': random.uniform(1.1, 10.0),
                    'running': True,
                    'premium_expiry': premium_expiry
                }
                logger.info(f"Rocket started by {user_id}: Bet={bet}, Crash={rocket_games[user_id]['crash_point']:.2f}")
                return jsonify({'message': 'Ракета стартовала!', 'coef': 1.0})
            elif action == 'cashout' and user_id in rocket_games:
                game = rocket_games[user_id]
                if not game['running']:
                    return jsonify({'error': 'Игра завершена!'})
                game['running'] = False
                win = int(game['bet'] * game['current_coef'])
                if game['premium_expiry'] > time.time():
                    win = int(win * 1.5)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('UPDATE users SET balance = balance + ?, total_won = total_won + ? WHERE user_id = ?', (win, win, user_id))
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                balance = cursor.fetchone()[0]
                conn.commit()
                conn.close()
                add_xp(user_id, win)
                coef = game['current_coef']
                del rocket_games[user_id]
                logger.info(f"Rocket cashed out by {user_id}: Win={win}, Coef={coef:.2f}")
                return jsonify({
                    'message': f"🏆 Выигрыш: {format_amount(win)} рублей!",
                    'balance': format_amount(balance),
                    'coef': coef
                })
            elif action == 'check' and user_id in rocket_games:
                game = rocket_games[user_id]
                game['current_coef'] += 0.1
                if game['current_coef'] >= game['crash_point']:
                    game['running'] = False
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
                    balance = cursor.fetchone()[0]
                    conn.close()
                    coef = game['current_coef']
                    del rocket_games[user_id]
                    logger.info(f"Rocket crashed for {user_id}: Coef={coef:.2f}")
                    return jsonify({
                        'crashed': True,
                        'balance': format_amount(balance),
                        'coef': coef
                    })
                return jsonify({'crashed': False, 'coef': game['current_coef']})
        except Exception as e:
            logger.error(f"Rocket error for {user_id}: {e}")
            return jsonify({'error': 'Ошибка при игре в ракету!'}), 500
    return render_template('rocket.html', bet=1000)

@app.route('/blackjack', methods=['GET', 'POST'])
def blackjack():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            bet = int(request.form.get('bet', 1000))
            if bet < 100:
                return jsonify({'error': 'Ставка должна быть не менее 100 рублей!'})
            if action == 'start':
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('SELECT balance, premium_expiry FROM users WHERE user_id = ?', (user_id,))
                user = cursor.fetchone()
                if not user or user[0] < bet:
                    conn.close()
                    return jsonify({'error': f"Недостаточно средств! У вас {format_amount(user[0] if user else 0)} рублей 😢"})
                balance, premium_expiry = user
                balance -= bet
                cursor.execute('UPDATE users SET balance = ?, total_lost = total_lost + ? WHERE user_id = ?', (balance, bet, user_id))
                conn.commit()
                conn.close()
                player_cards = [draw_card(), draw_card()]
                dealer_cards = [draw_card(), draw_card()]
                blackjack_games[user_id] = {
                    'bet': bet,
                    'player_cards': player_cards,
                    'dealer_cards': dealer_cards,
                    'premium_expiry': premium_expiry
                }
                logger.info(f"Blackjack started by {user_id}: Bet={bet}")
                return jsonify({
                    'player_cards': format_cards(player_cards),
                    'player_sum': sum_cards(player_cards),
                    'dealer_cards': format_cards([dealer_cards[0]]) + " + 🂠",
                    'message': 'Выберите действие'
                })
            elif action == 'hit' and user_id in blackjack_games:
                game = blackjack_games[user_id]
                game['player_cards'].append(draw_card())
                player_sum = sum_cards(game['player_cards'])
                if player_sum > 21:
                    return end_blackjack_game(user_id, False, "Перебор! 😢")
                logger.info(f"Blackjack hit by {user_id}: Player cards={game['player_cards']}")
                return jsonify({
                    'player_cards': format_cards(game['player_cards']),
                    'player_sum': player_sum,
                    'dealer_cards': format_cards([game['dealer_cards'][0]]) + " + 🂠",
                    'message': 'Выберите действие'
                })
            elif action == 'stand' and user_id in blackjack_games:
                game = blackjack_games[user_id]
                dealer_cards = game['dealer_cards']
                while sum_cards(dealer_cards) < 17:
                    dealer_cards.append(draw_card())
                player_sum = sum_cards(game['player_cards'])
                dealer_sum = sum_cards(dealer_cards)
                logger.info(f"Blackjack stand by {user_id}: Player={player_sum}, Dealer={dealer_sum}")
                if dealer_sum > 21 or player_sum > dealer_sum:
                    return end_blackjack_game(user_id, True, "Ты победил! 🏆")
                elif player_sum < dealer_sum:
                    return end_blackjack_game(user_id, False, "Дилер победил! 😢")
                else:
                    return end_blackjack_game(user_id, False, "Ничья! 😐")
        except Exception as e:
            logger.error(f"Blackjack error for {user_id}: {e}")
            return jsonify({'error': 'Ошибка при игре в блэкджек!'}), 500
    return render_template('blackjack.html', bet=1000)

@app.route('/dice', methods=['GET', 'POST'])
def dice():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if request.method == 'POST':
        try:
            bet = int(request.form.get('bet', 1000))
            if bet < 100:
                return jsonify({'error': 'Ставка должна быть не менее 100 рублей!'})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT balance, premium_expiry FROM users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user or user[0] < bet:
                conn.close()
                return jsonify({'error': f"Недостаточно средств! У вас {format_amount(user[0] if user else 0)} рублей 😢"})
            balance, premium_expiry = user
            balance -= bet
            cursor.execute('UPDATE users SET balance = ?, total_lost = total_lost + ? WHERE user_id = ?', (balance, bet, user_id))
            player_dice = [random.randint(1, 6), random.randint(1, 6)]
            bot_dice = [random.randint(1, 6), random.randint(1, 6)]
            player_sum = sum(player_dice)
            bot_sum = sum(bot_dice)
            win = 0
            result = "😢 Проигрыш!"
            if player_sum > bot_sum:
                win = bet * 2
                result = "🏆 Выигрыш!"
            elif player_sum == bot_sum:
                win = bet
                result = "😶 Ничья!"
            if premium_expiry > time.time():
                win = int(win * 1.5)
            if win > 0:
                balance += win
                cursor.execute('UPDATE users SET balance = ?, total_won = total_won + ? WHERE user_id = ?', (balance, win, user_id))
                add_xp(user_id, win)
            conn.commit()
            conn.close()
            logger.info(f"Dice played by {user_id}: Bet={bet}, Player={player_dice}, Bot={bot_dice}, Win={win}")
            return jsonify({
                'player_dice': player_dice,
                'player_sum': player_sum,
                'bot_dice': bot_dice,
                'bot_sum': bot_sum,
                'win': win,
                'balance': format_amount(balance),
                'message': result
            })
        except Exception as e:
            logger.error(f"Dice error for {user_id}: {e}")
            return jsonify({'error': 'Ошибка при игре в кости!'}), 500
    return render_template('dice.html', bet=1000)

@app.route('/bonus', methods=['POST'])
def bonus():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated!'}), 401
    user_id = session['user_id']
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT balance, last_bonus FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            logger.error(f"Bonus: User not found for {user_id}")
            return jsonify({'error': 'User not found!'}), 404
        balance, last_bonus_time = user
        if last_bonus_time is None or time.time() - last_bonus_time >= 86400:
            bonus = random.randint(1000, 5000)
            new_balance = balance + bonus
            cursor.execute('UPDATE users SET balance = ?, last_bonus = ?, total_won = total_won + ? WHERE user_id = ?',
                           (new_balance, time.time(), bonus, user_id))
            conn.commit()
            conn.close()
            logger.info(f"Bonus claimed by {user_id}: Amount={bonus}")
            return jsonify({'message': f"🎁 Вы получили бонус: {format_amount(bonus)} рублей!", 'balance': format_amount(new_balance)})
        else:
            time_left = int((last_bonus_time + 86400 - time.time()) / 3600)
            conn.close()
            return jsonify({'error': f"Бонус доступен через {time_left} часов! ⏳"})
    except Exception as e:
        logger.error(f"Bonus error for {user_id}: {e}")
        return jsonify({'error': 'Ошибка при получении бонуса!'}), 500

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if user_id not in HOST_IDS:
        logger.warning(f"Admin access denied for {user_id}")
        return "Access denied!", 403
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username FROM users ORDER BY balance DESC LIMIT 10')
    players = cursor.fetchall()
    conn.close()
    if request.method == 'POST':
        try:
            action = request.form.get('action')
            target_id = request.form.get('target_id')
            amount = request.form.get('amount')
            amount = int(amount) if amount else 0
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT username FROM users WHERE user_id = ?', (target_id,))
            target_user = cursor.fetchone()
            if not target_user:
                conn.close()
                return jsonify({'error': 'Пользователь не найден!'})
            if action == 'give':
                cursor.execute('UPDATE users SET balance = balance + ?, total_won = total_won + ? WHERE user_id = ?', (amount, amount, target_id))
                cursor.execute('SELECT balance FROM users WHERE user_id = ?', (target_id))
                new_balance = cursor.fetchone()[0]
                conn.commit()
                logger.info(f"Admin {user_id} gave {amount} to {target_id}")
                return jsonify({'message': f"💰 Игроку выдано {format_amount(amount)} рублей! Новый баланс: {format_amount(new_balance)}"})
            elif action == 'reset':
                cursor.execute('UPDATE users SET balance = 0, total_won = 0, total_lost = 0, level = 1, xp = 0, status = "Новичок" WHERE user_id = ?', (target_id,))
                conn.commit()
                logger.info(f"Admin {user_id} reset stats for {target_id}")
                return jsonify({'message': f"🔄 Баланс и статистика игрока сброшены!"})
            elif action == 'mute':
                if amount <= 0:
                    return jsonify({'error': 'Укажите положительное количество минут!'})
                minutes = amount
                muted_users[target_id] = time.time() + minutes * 60
                logger.info(f"Admin {user_id} muted {target_id} for {minutes} minutes")
                return jsonify({'message': f"🤐 Игрок замучен на {minutes} минут!"})
            elif action == 'unmute':
                if target_id in muted_users:
                    del muted_users[target_id]
                    logger.info(f"Admin {user_id} unmuted {target_id}")
                    return jsonify({'message': f"🔊 Игрок размучен!"})
                return jsonify({'error': 'Игрок не в муте!'})
            elif action == 'block':
                cursor.execute('INSERT OR IGNORE INTO blocked_users (user_id) VALUES (?)', (target_id,))
                conn.commit()
                logger.info(f"Admin {user_id} blocked {target_id}")
                return jsonify({'message': f"🚫 Игрок заблокирован!"})
            elif action == 'unblock':
                cursor.execute('DELETE FROM blocked_users WHERE user_id = ?', (target_id,))
                conn.commit()
                logger.info(f"Admin {user_id} unblocked {target_id}")
                return jsonify({'message': f"🔓 Игрок разблокирован!"})
            elif action == 'premium':
                expiry = time.time() + 30 * 86400
                cursor.execute('UPDATE users SET premium_expiry = ? WHERE user_id = ?', (expiry, target_id))
                conn.commit()
                logger.info(f"Admin {user_id} activated premium for {target_id}")
                return jsonify({'message': f"💎 Премиум активирован на 30 дней!"})
            conn.close()
        except Exception as e:
            logger.error(f"Admin action error by {user_id}: {e}")
            conn.close()
            return jsonify({'error': 'Ошибка при выполнении админ-действия!'}), 500
    return render_template('admin.html', players=players)

@app.route('/broadcast', methods=['GET', 'POST'])
def broadcast():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user_id = session['user_id']
    if user_id not in HOST_IDS:
        logger.warning(f"Broadcast access denied for {user_id}")
        return "Access denied!", 403
    if request.method == 'POST':
        try:
            text = request.form.get('message')
            if not text:
                return jsonify({'error': 'Текст рассылки не может быть пустым!'})
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users')
            users = cursor.fetchall()
            conn.close()
            sent = 0
            for uid in users:
                logger.info(f"Broadcast to {uid[0]}: {text}")
                sent += 1
            logger.info(f"Admin {user_id} sent broadcast to {sent} users")
            return jsonify({'message': f"📢 Рассылка отправлена {sent} пользователям!"})
        except Exception as e:
            logger.error(f"Broadcast error by {user_id}: {e}")
            return jsonify({'error': 'Ошибка при отправке рассылки!'}), 500
    return render_template('broadcast.html')

def add_xp(user_id, amount):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return
        xp, level = user
        xp += int(amount / 100)
        while xp >= level * 1000:
            xp -= level * 1000
            level += 1
            status = "Новичок" if level < 10 else "Игрок" if level < 20 else "Профи" if level < 30 else "Легенда"
            cursor.execute('UPDATE users SET level = ?, xp = ?, status = ? WHERE user_id = ?', (level, xp, status, user_id))
        else:
            cursor.execute('UPDATE users SET xp = ? WHERE user_id = ?', (xp, user_id))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"XP update error for {user_id}: {e}")

def draw_card():
    cards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
    return random.choice(cards)

def sum_cards(cards):
    total = sum(cards)
    aces = cards.count(11)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total

def format_cards(cards):
    card_emojis = {2: "🂢", 3: "🂣", 4: "🂤", 5: "🂥", 6: "🂦", 7: "🂧", 8: "🂨", 9: "🂩", 10: "🂪", 11: "🂡"}
    return " ".join(card_emojis.get(card, "🂠") for card in cards)

def end_blackjack_game(user_id, won, result_text):
    try:
        game = blackjack_games[user_id]
        bet = game['bet']
        premium_expiry = game['premium_expiry']
        win = bet * 2 if won else 0
        if premium_expiry > time.time():
            win = int(win * 1.5)
        conn = get_db_connection()
        cursor = conn.cursor()
        if win > 0:
            cursor.execute('UPDATE users SET balance = balance + ?, total_won = total_won + ? WHERE user_id = ?', (win, win, user_id))
            add_xp(user_id, win)
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        balance = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        response = {
            'player_cards': format_cards(game['player_cards']),
            'player_sum': sum_cards(game['player_cards']),
            'dealer_cards': format_cards(game['dealer_cards']),
            'dealer_sum': sum_cards(game['dealer_cards']),
            'message': result_text,
            'win': win,
            'balance': format_amount(balance)
        }
        del blackjack_games[user_id]
        logger.info(f"Blackjack ended for {user_id}: Won={won}, Result={result_text}, Win={win}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Blackjack end error for {user_id}: {e}")
        return jsonify({'error': 'Ошибка при завершении блэкджека!'}), 500

if __name__ == '__main__':
    init_db()
    load_data()
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
