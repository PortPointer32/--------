import psycopg2
from psycopg2 import pool
from contextlib import contextmanager
import time

POSTGRES_DB_PAYMENT = "payment_db"
POSTGRES_USER_PAYMENT = "admin"
POSTGRES_PASSWORD_PAYMENT = "admin"
POSTGRES_HOST_PAYMENT = "localhost"

POSTGRES_DB = "gostt"
POSTGRES_USER = "admin"
POSTGRES_PASSWORD = "admin"
POSTGRES_HOST = "localhost"

payment_db_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 100,
    dbname=POSTGRES_DB_PAYMENT,
    user=POSTGRES_USER_PAYMENT,
    password=POSTGRES_PASSWORD_PAYMENT,
    host=POSTGRES_HOST_PAYMENT
)

main_db_pool = psycopg2.pool.ThreadedConnectionPool(
    1, 100,
    dbname=POSTGRES_DB,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    host=POSTGRES_HOST
)

@contextmanager
def get_connection(pool):
    conn = None
    while conn is None:
        try:
            conn = pool.getconn()
        except psycopg2.pool.PoolError:
            time.sleep(1)
    try:
        yield conn
    finally:
        pool.putconn(conn)

def initialize_payment_db():
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS payment_details_obmen (
                id SERIAL PRIMARY KEY,
                type TEXT,
                text TEXT,
                coefficient_buy REAL DEFAULT 1.0,
                coefficient_sell REAL DEFAULT 1.0
            )''')
            conn.commit()

def initialize():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                username TEXT
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT,
                bot_token TEXT,
                FOREIGN KEY (bot_token) REFERENCES tokens(token)
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS settings (
                name TEXT PRIMARY KEY,
                text TEXT
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS crypto_prices (
                currency TEXT PRIMARY KEY,
                price REAL
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS payment_details (
                type TEXT PRIMARY KEY,
                text TEXT,
                coefficient_buy REAL DEFAULT 1.0,
                coefficient_sell REAL DEFAULT 1.0
            )''')

            cursor.execute('''CREATE TABLE IF NOT EXISTS daily_mailings (
                id SERIAL PRIMARY KEY,
                time TEXT,
                text TEXT,
                photo_path TEXT
            )''')

            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('card', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")
            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('sbp', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")
            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('btc', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")
            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('xmr', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")
            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('ltc', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")
            cursor.execute("INSERT INTO payment_details (type, text) VALUES ('usdt', 'Пока не установлено.') ON CONFLICT (type) DO NOTHING")

            cursor.execute("INSERT INTO settings (name, text) VALUES ('help', 'durov') ON CONFLICT (name) DO NOTHING")

            conn.commit()

def clear_database():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS daily_mailings, payment_details, crypto_prices, settings, users, tokens CASCADE")
            conn.commit()

def get_buy_coefficient(type):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT coefficient_buy FROM payment_details_obmen WHERE type = %s", (type,))
            result = cursor.fetchone()
            return result[0] if result else None

def get_sell_coefficient(type):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT coefficient_sell FROM payment_details_obmen WHERE type = %s", (type,))
            result = cursor.fetchone()
            return result[0] if result else None

def get_payment_method_status(payment_type):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT boolean FROM payment_details_obmen WHERE type = %s", (payment_type,))
            row = cursor.fetchone()
            return row[0] if row else False

def set_payment_photo(payment_type, photo_path):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE payment_details_obmen SET photo_path = %s WHERE type = %s", (photo_path, payment_type))
            conn.commit()

def set_payment_method_status(payment_type, new_status):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE payment_details_obmen SET boolean = %s WHERE type = %s", (new_status, payment_type))
            conn.commit()

def set_buy_coefficient(type, coefficient):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE payment_details_obmen SET coefficient_buy = %s WHERE type = %s", (coefficient, type))
            conn.commit()

def get_enabled_payment_methods():
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT type, text FROM payment_details_obmen WHERE boolean = 1")
            methods = cursor.fetchall()
            return methods

def get_payment_methods():
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT type, text FROM payment_details_obmen")
            methods = cursor.fetchall()
            return methods

def set_sell_coefficient(type, coefficient):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE payment_details_obmen SET coefficient_sell = %s WHERE type = %s", (coefficient, type))
            conn.commit()
       
def update_crypto_price(currency, price):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO crypto_prices (currency, price) VALUES (%s, %s) ON CONFLICT (currency) DO UPDATE SET price = EXCLUDED.price", (currency, price))
            conn.commit()

def get_crypto_price(currency):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT price FROM crypto_prices WHERE currency = %s", (currency,))
            result = cursor.fetchone()
            return result[0] if result else None
            
def add_daily_mailing(time, text, photo_path):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO daily_mailings (time, text, photo_path) VALUES (%s, %s, %s)", (time, text, photo_path))
            conn.commit()

def delete_daily_mailing(id):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM daily_mailings WHERE id = %s", (id,))
            conn.commit()

def get_daily_mailings():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM daily_mailings")
            return cursor.fetchall()

def get_daily_mailing_by_id(id):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM daily_mailings WHERE id = %s", (id,))
            return cursor.fetchone()

def add_token(token, username):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO tokens (token, username) VALUES (%s, %s)", (token, username))
            conn.commit()

def delete_token(token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM users WHERE bot_token = %s", (token,))
            cursor.execute("DELETE FROM tokens WHERE token = %s", (token,))
            conn.commit()

def get_tokens():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT token, username FROM tokens")
            return cursor.fetchall()

def get_total_users_count():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users")
            return cursor.fetchone()[0]

def get_users_count_of_bot(bot_token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM users WHERE bot_token = %s", (bot_token,))
            return cursor.fetchone()[0]
            
def get_bot_data(token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username, token FROM tokens WHERE token = %s", (token,))
            return cursor.fetchone()

def add_user(user_id, bot_token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO users (user_id, bot_token) VALUES (%s, %s)", (user_id, bot_token))
            conn.commit()

def get_users_by_token(bot_token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE bot_token = %s", (bot_token,))
            return cursor.fetchall()

def check_user_exists(user_id, bot_token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM users WHERE user_id = %s AND bot_token = %s", (user_id, bot_token))
            return cursor.fetchone() is not None

def get_help_text():
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT text FROM settings WHERE name = 'help'")
            return cursor.fetchone()[0]

def get_bot_username_by_token(token):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT username FROM tokens WHERE token = %s", (token,))
            result = cursor.fetchone()
            return result[0] if result else None

def set_help_text(new_text):
    with get_connection(main_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE settings SET text = %s WHERE name = 'help'", (new_text,))
            conn.commit()

def get_payment_details(payment_type):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT text FROM payment_details_obmen WHERE type = %s", (payment_type,))
            row = cursor.fetchone()
            return row[0] if row else "Реквизиты не найдены."

def set_payment_details(payment_type, new_text):
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE payment_details_obmen SET text = %s WHERE type = %s", (new_text, payment_type))
            conn.commit()

def get_active_payment_types():
    with get_connection(payment_db_pool) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT type FROM payment_details_obmen WHERE boolean = 1")
            active_types = cursor.fetchall()
            return [type[0] for type in active_types]
