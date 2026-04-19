import psycopg2
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from telegram.helpers import escape_markdown
from datetime import datetime
import json
import os

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

ASKING_FULL_NAME, ASKING_ADDRESS, ASKING_PHONE_NUMBER, CONFIRM_EDIT = range(4)

# --- إعدادات الاتصال بـ PostgreSQL ---
DATABASE_URL = os.environ.get('DATABASE_URL')  # Render يعطيك هذا تلقائياً

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات."""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        raise


def init_db():
    """
    تهيئة قاعدة البيانات وإنشاء جدول المستخدمين إذا لم يكن موجوداً.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY,
            full_name TEXT,
            address TEXT,
            phone_number TEXT,
            wallet_balance REAL DEFAULT 0.0,
            investment_balance REAL DEFAULT 0.0,
            is_subscribed INTEGER DEFAULT 0,
            subscription_plan TEXT,
            expiry_date TEXT,
            subscribed_pairs TEXT,
            daily_recommendations_count INTEGER DEFAULT 0,
            last_recommendation_date TEXT
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("تم تهيئة قاعدة البيانات PostgreSQL.")


def add_user(user_id: int, full_name: str, address: str, phone_number: str):
    """
    يضيف مستخدماً جديداً إلى قاعدة البيانات.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, full_name, address, phone_number)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO NOTHING
    ''', (user_id, full_name, address, phone_number))
    conn.commit()
    conn.close()
    logger.info(f"تم إضافة المستخدم {user_id} إلى قاعدة البيانات.")


def get_user_data(user_id: int) -> dict | None:
    """
    يسترجع بيانات المستخدم من قاعدة البيانات.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
    row = cursor.fetchone()
    cols = [desc[0] for desc in cursor.description] if cursor.description else []
    conn.close()
    
    if row:
        user_data = dict(zip(cols, row))
        if user_data.get('subscribed_pairs'):
            try:
                user_data['subscribed_pairs'] = json.loads(user_data['subscribed_pairs'])
            except json.JSONDecodeError:
                user_data['subscribed_pairs'] = []
        else:
            user_data['subscribed_pairs'] = []
        return user_data
    return None


def get_all_users_data() -> dict:
    """
    يسترجع بيانات جميع المستخدمين من قاعدة البيانات.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    rows = cursor.fetchall()
    cols = [desc[0] for desc in cursor.description] if cursor.description else []
    conn.close()

    all_users = {}
    for row in rows:
        user_data = dict(zip(cols, row))
        if user_data.get('subscribed_pairs'):
            try:
                user_data['subscribed_pairs'] = json.loads(user_data['subscribed_pairs'])
            except json.JSONDecodeError:
                user_data['subscribed_pairs'] = []
        else:
            user_data['subscribed_pairs'] = []
        all_users[str(user_data['user_id'])] = user_data
    return all_users


ALLOWED_USER_COLUMNS = {
    'full_name', 'address', 'phone_number', 'wallet_balance',
    'investment_balance', 'is_subscribed', 'subscription_plan',
    'expiry_date', 'subscribed_pairs', 'daily_recommendations_count',
    'last_recommendation_date'
}


def update_user_data(user_id: int, **kwargs):
    """
    يحدث بيانات مستخدم موجود في قاعدة البيانات.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    set_clause = []
    values = []
    for key, value in kwargs.items():
        if key not in ALLOWED_USER_COLUMNS:
            logger.warning(f"محاولة تحديث عمود غير مسموح به: {key}")
            continue
        if key == 'subscribed_pairs':
            value = json.dumps(value)
        set_clause.append(f"{key} = %s")
        values.append(value)

    if set_clause:
        values.append(user_id)
        cursor.execute(f"UPDATE users SET {', '.join(set_clause)} WHERE user_id = %s", tuple(values))
        conn.commit()
    conn.close()
    logger.info(f"تم تحديث بيانات المستخدم {user_id}.")


def update_wallet_balance(user_id: int, amount: float):
    """
    يحدث رصيد المحفظة للمستخدم.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET wallet_balance = wallet_balance + %s WHERE user_id = %s', (amount, user_id))
    conn.commit()
    conn.close()
    logger.info(f"تم تحديث رصيد المحفظة للمستخدم {user_id} بالمبلغ {amount}.")


def update_investment_balance(user_id: int, amount: float):
    """
    يحدث رصيد الاستثمار للمستخدم.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET investment_balance = investment_balance + %s WHERE user_id = %s', (amount, user_id))
    conn.commit()
    conn.close()
    logger.info(f"تم تحديث رصيد الاستثمار للمستخدم {user_id} بالمبلغ {amount}.")


def update_subscription_status(user_id: int, is_subscribed: bool, plan_name: str = None, expiry_date: str = None):
    """
    يحدث حالة اشتراك المستخدم.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET is_subscribed = %s, subscription_plan = %s, expiry_date = %s
        WHERE user_id = %s
    ''', (is_subscribed, plan_name, expiry_date, user_id))
    conn.commit()
    conn.close()
    logger.info(f"تم تحديث حالة اشتراك المستخدم {user_id} إلى {is_subscribed} للخطة {plan_name}.")


def get_subscription_info(user_id: int) -> dict | None:
    """
    يسترجع معلومات الاشتراك للمستخدم.
    """
    user_data = get_user_data(user_id)
    if user_data:
        return {
            'is_subscribed': bool(user_data.get('is_subscribed')),
            'plan_name': user_data.get('subscription_plan'),
            'expiry_date': user_data.get('expiry_date'),
            'subscribed_pairs': user_data.get('subscribed_pairs', [])
        }
    return None


def update_subscribed_pairs(user_id: int, pairs: list):
    """
    يحدث قائمة أزواج التداول المشترك بها للمستخدم.
    """
    update_user_data(user_id, subscribed_pairs=pairs)
    logger.info(f"تم تحديث أزواج التداول المشترك بها للمستخدم {user_id}.")


def update_daily_recommendations_count(user_id: int, count: int):
    """
    يحدث عدد التوصيات اليومية المرسلة للمستخدم.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    update_user_data(user_id, daily_recommendations_count=count, last_recommendation_date=today)
    logger.info(f"تم تحديث عدد التوصيات اليومية للمستخدم {user_id} إلى {count}.")