import os
import time
import telegram.error
import threading
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import psycopg
from psycopg.rows import dict_row

# ================= IMPORT FLASK FOR ADMIN PANEL =================
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash

# ================= FLASK APP FOR ADMIN PANEL =================
admin_app = Flask(__name__)
admin_app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

# ================= LOGIN MANAGER =================
login_manager = LoginManager()
login_manager.init_app(admin_app)
login_manager.login_view = 'login'

# ================= USER MODEL =================
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

# كلمات مرور مشفرة
ADMINS = {
    "admin": {
        "id": 1,
        "password_hash": generate_password_hash("admin123")
    }
}

@login_manager.user_loader
def load_user(user_id):
    if user_id == "1":
        return User(1, "admin")
    return None

# ================= DATABASE CLASS =================
class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """الاتصال بقاعدة البيانات PostgreSQL"""
        try:
            DATABASE_URL = os.getenv('DATABASE_URL')
            if not DATABASE_URL:
                raise ValueError("DATABASE_URL not found in environment variables")
            
            # استخدم psycopg بدل psycopg2
            self.conn = psycopg.connect(DATABASE_URL, sslmode='require')
            self.cursor = self.conn.cursor(row_factory=dict_row)  # تغيير هنا
            print("✅ Connected to PostgreSQL successfully")
            
            # اختبر الاتصال
            self.cursor.execute("SELECT 1")
            test = self.cursor.fetchone()
            print(f"✅ Database test result: {test}")
            
            self.create_tables()
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            import traceback
            traceback.print_exc()  # طباعة تفاصيل الخطأ
            self.use_sqlite_as_fallback()
    
    def use_sqlite_as_fallback(self):
        """استخدام SQLite كخيار احتياطي"""
        import sqlite3
        try:
            self.conn = sqlite3.connect("orders.db", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            print("⚠️ Using SQLite as fallback")
            self.create_sqlite_tables()
        except Exception as e:
            print(f"❌ SQLite fallback also failed: {e}")
    
    def create_tables(self):
        """إنشاء الجداول في PostgreSQL"""
        try:
            # جدول الطلبات
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(20) NOT NULL,
                    product TEXT NOT NULL,
                    customer_name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    quantity TEXT NOT NULL,
                    size TEXT,
                    language VARCHAR(5) DEFAULT 'ar',
                    status VARCHAR(20) DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    merchant_id INTEGER DEFAULT 1
                )
            ''')
            
            # جدول التجار
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS merchants (
                    id SERIAL PRIMARY KEY,
                    telegram_id BIGINT UNIQUE,
                    username VARCHAR(100),
                    business_name TEXT,
                    plan VARCHAR(20) DEFAULT 'trial',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # إضافة بعض البيانات الافتراضية
            self.cursor.execute('''
                INSERT INTO merchants (id, telegram_id, username, business_name, plan)
                VALUES (1, 5812937391, 'admin', 'OrderlyBot Admin', 'pro')
                ON CONFLICT (id) DO NOTHING
            ''')
            
            self.conn.commit()
            print("✅ PostgreSQL tables created successfully")
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            self.conn.rollback()
    
    def create_sqlite_tables(self):
        """إنشاء الجداول في SQLite"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT,
                    product TEXT,
                    customer_name TEXT,
                    phone TEXT,
                    address TEXT,
                    quantity TEXT,
                    size TEXT,
                    language TEXT DEFAULT 'ar',
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
            print("✅ SQLite tables created as fallback")
        except Exception as e:
            print(f"❌ Error creating SQLite tables: {e}")
    
    def add_order(self, order_data):
        """إضافة طلب جديد"""
        try:
            query = '''
                INSERT INTO orders 
                (category, product, customer_name, phone, address, quantity, size, language, merchant_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            '''
            
            self.cursor.execute(query, (
                order_data['category'],
                order_data['product'],
                order_data['name'],
                order_data['phone'],
                order_data['address'],
                order_data['quantity'],
                order_data.get('size', ''),
                order_data['lang'],
                1
            ))
            
            # تغيير هنا لأن psycopg يرجع tuple
            result = self.cursor.fetchone()
            order_id = result['id'] if isinstance(result, dict) else result[0]
            
            self.conn.commit()
            print(f"✅ Order #{order_id} saved to database")
            return order_id
            
        except Exception as e:
            print(f"❌ Error saving order: {e}")
            import traceback
            traceback.print_exc()
            self.conn.rollback()
            return None
    
    def get_orders_by_merchant(self, merchant_id, limit=50):
        """جلب طلبات تاجر معين"""
        try:
            query = '''
                SELECT * FROM orders 
                WHERE merchant_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            '''
            self.cursor.execute(query, (merchant_id, limit))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"❌ Error fetching orders: {e}")
            return []
    
    def get_order_stats(self, merchant_id):
        """الحصول على إحصائيات الطلبات"""
        try:
            stats = {}
            
            self.cursor.execute('SELECT COUNT(*) FROM orders WHERE merchant_id = %s', (merchant_id,))
            stats['total'] = self.cursor.fetchone()['count']
            
            self.cursor.execute('SELECT COUNT(*) FROM orders WHERE merchant_id = %s AND status = %s', 
                              (merchant_id, 'new'))
            stats['new'] = self.cursor.fetchone()['count']
            
            self.cursor.execute('SELECT COUNT(*) FROM orders WHERE merchant_id = %s AND status = %s', 
                              (merchant_id, 'completed'))
            stats['completed'] = self.cursor.fetchone()['count']
            
            self.cursor.execute('''
                SELECT COUNT(*) FROM orders 
                WHERE merchant_id = %s AND DATE(created_at) = CURRENT_DATE
            ''', (merchant_id,))
            stats['today'] = self.cursor.fetchone()['count']
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {'total': 0, 'new': 0, 'completed': 0, 'today': 0}
    
    # ===== FUNCTIONS FOR ADMIN PANEL =====
    
    def get_orders_with_filters(self, status_filter='all', category_filter='all', limit=50):
        """جلب الطلبات مع التصفية"""
        try:
            query = '''
                SELECT * FROM orders 
                WHERE merchant_id = 1
            '''
            params = []
            
            if status_filter != 'all':
                query += ' AND status = %s'
                params.append(status_filter)
            
            if category_filter != 'all':
                query += ' AND category = %s'
                params.append(category_filter)
            
            query += ' ORDER BY created_at DESC LIMIT %s'
            params.append(limit)
            
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"❌ Error in get_orders_with_filters: {e}")
            return []
    
    def get_advanced_stats(self):
        """جلب إحصائيات متقدمة"""
        try:
            stats = {}
            
            self.cursor.execute('''
                SELECT 
                    COUNT(*) as total_orders,
                    SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new_orders,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                    SUM(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 ELSE 0 END) as today_orders
                FROM orders 
                WHERE merchant_id = 1
            ''')
            basic_stats = self.cursor.fetchone()
            
            stats.update(basic_stats)
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting advanced stats: {e}")
            return {}

# ================= INITIALIZE DATABASE =================
db = Database()
db.connect()

# ================= TELEGRAM BOT CONFIGURATION =================
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 5812937391

# ================= TEXTS =================
TEXT = {
    "lang": {
        "ar": "اختر نوع النشاط:",
        "en": "Choose business type:"
    },
    "category": {
        "ar": ["🍔 طعام", "👕 ملابس"],
        "en": ["🍔 Food", "👕 Clothing"]
    },
    "ask_product": {
        "ar": "اختر المنتج:",
        "en": "Choose product:"
    },
    "ask_name": {
        "ar": "اكتب اسمك:",
        "en": "Enter your name:"
    },
    "ask_phone": {
        "ar": "اكتب رقم الهاتف:",
        "en": "Enter phone number:"
    },
    "ask_address": {
        "ar": "اكتب العنوان:",
        "en": "Enter address:"
    },
    "ask_quantity": {
        "ar": "اكتب الكمية:",
        "en": "Enter quantity:"
    },
    "ask_size": {
        "ar": "اكتب المقاس:",
        "en": "Enter size:"
    },
    "confirm": {
        "ar": "✅ تم استلام طلبك، سنتواصل معك قريبًا",
        "en": "✅ Order received, we will contact you soon"
    }
}

PRODUCTS = {
    "food": ["🍕 Pizza", "🍔 Burger", "🥗 Salad"],
    "clothing": ["👕 T-Shirt", "👖 Jeans", "🧥 Jacket"]
}

# ================= TELEGRAM BOT HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء المحادثة"""
    keyboard = [
        [
            InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")
        ]
    ]
    await update.message.reply_text(
        "اختر اللغة / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الردود من الأزرار"""
    query = update.callback_query
    await query.answer()

    data = query.data

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        context.user_data["lang"] = lang

        keyboard = [
            [
                InlineKeyboardButton(TEXT["category"][lang][0], callback_data="cat_food"),
                InlineKeyboardButton(TEXT["category"][lang][1], callback_data="cat_clothing")
            ]
        ]
        await query.edit_message_text(
            TEXT["lang"][lang],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("cat_"):
        category = data.split("_")[1]
        context.user_data["category"] = category
        lang = context.user_data["lang"]

        keyboard = [
            [InlineKeyboardButton(p, callback_data=f"prod_{p}")]
            for p in PRODUCTS[category]
        ]

        await query.edit_message_text(
            TEXT["ask_product"][lang],
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data.startswith("prod_"):
        product = data.replace("prod_", "")
        context.user_data["product"] = product
        lang = context.user_data["lang"]

        await query.edit_message_text(TEXT["ask_name"][lang])
        context.user_data["step"] = "name"

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل النصية"""
    step = context.user_data.get("step")
    lang = context.user_data.get("lang")

    if step == "name":
        context.user_data["name"] = update.message.text
        await update.message.reply_text(TEXT["ask_phone"][lang])
        context.user_data["step"] = "phone"

    elif step == "phone":
        context.user_data["phone"] = update.message.text
        await update.message.reply_text(TEXT["ask_address"][lang])
        context.user_data["step"] = "address"

    elif step == "address":
        context.user_data["address"] = update.message.text
        await update.message.reply_text(TEXT["ask_quantity"][lang])
        context.user_data["step"] = "quantity"

    elif step == "quantity":
        context.user_data["quantity"] = update.message.text
        if context.user_data["category"] == "clothing":
            await update.message.reply_text(TEXT["ask_size"][lang])
            context.user_data["step"] = "size"
        else:
            await save_order(update, context)

    elif step == "size":
        context.user_data["size"] = update.message.text
        await save_order(update, context)

async def save_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حفظ الطلب في قاعدة البيانات"""
    data = context.user_data
    lang = data["lang"]

    try:
        order_data = {
            'category': data["category"],
            'product': data["product"],
            'name': data["name"],
            'phone': data["phone"],
            'address': data["address"],
            'quantity': data["quantity"],
            'size': data.get("size", ""),
            'lang': lang
        }

        order_id = db.add_order(order_data)

        if order_id:
            await update.message.reply_text(TEXT["confirm"][lang])

            order_msg = f"""
📦 **طلب جديد #{order_id}**

**التفاصيل:**
- النوع: {'🍔 طعام' if data['category'] == 'food' else '👕 ملابس'}
- المنتج: {data['product']}
- الاسم: {data['name']}
- الهاتف: {data['phone']}
- العنوان: {data['address']}
- الكمية: {data['quantity']}
- المقاس: {data.get('size', 'غير محدد')}
- اللغة: {'عربي' if lang == 'ar' else 'English'}

⏰ {datetime.now().strftime('%Y-%m-%d %I:%M %p')}
            """
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=order_msg,
                parse_mode='Markdown'
            )
            
            print(f"✅ Order #{order_id} processed successfully")
        else:
            await update.message.reply_text("❌ حدث خطأ في حفظ الطلب، يرجى المحاولة لاحقاً")

    except Exception as e:
        print(f"❌ Error in save_order: {e}")
        await update.message.reply_text("❌ حدث خطأ غير متوقع، يرجى المحاولة لاحقاً")

    finally:
        context.user_data.clear()

async def myorders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض الطلبات للتاجر"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        try:
            stats = db.get_order_stats(1)
            orders = db.get_orders_by_merchant(1, limit=10)
            
            if not orders:
                await update.message.reply_text("📭 لا توجد طلبات حتى الآن.")
                return
            
            stats_msg = f"""
📊 **إحصائيات الطلبات:**

• إجمالي الطلبات: {stats['total']}
• طلبات جديدة: {stats['new']}
• طلبات مكتملة: {stats['completed']}
• طلبات اليوم: {stats['today']}
────────────────────
            """
            
            orders_msg = "📋 **آخر الطلبات:**\n\n"
            
            for order in orders:
                status_emoji = "🆕" if order['status'] == 'new' else "✅" if order['status'] == 'completed' else "⏳"
                category_emoji = "🍔" if order['category'] == 'food' else "👕"
                
                orders_msg += f"""
{status_emoji} **طلب #{order['id']}** ({category_emoji})
👤 {order['customer_name']} - 📞 {order['phone']}
📍 {order['address']}
📦 {order['product']} × {order['quantity']}
⏰ {order['created_at'].strftime('%d/%m %I:%M %p')}
────────────────────
                """
            
            await update.message.reply_text(stats_msg, parse_mode='Markdown')
            await update.message.reply_text(orders_msg, parse_mode='Markdown')
            
        except Exception as e:
            print(f"❌ Error in myorders_command: {e}")
            await update.message.reply_text("❌ حدث خطأ في جلب الطلبات")
    else:
        await update.message.reply_text("⛔ هذا الأمر للمسؤول فقط.")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إحصائيات سريعة"""
    user_id = update.effective_user.id
    
    if user_id == ADMIN_ID:
        try:
            stats = db.get_order_stats(1)
            
            stats_msg = f"""
📈 **إحصائيات OrderlyBot:**

🎯 **المبيعات:**
• إجمالي الطلبات: {stats['total']}
• طلبات جديدة: {stats['new']}
• طلبات مكتملة: {stats['completed']}
• طلبات اليوم: {stats['today']}

💾 **قاعدة البيانات:**
• نوع قاعدة البيانات: {'PostgreSQL' if 'postgres' in str(db.conn) else 'SQLite (Fallback)'}
• حالة الاتصال: ✅ نشط

🔄 **آخر تحديث:** {datetime.now().strftime('%Y-%m-%d %I:%M %p')}
            """
            
            await update.message.reply_text(stats_msg, parse_mode='Markdown')
            
        except Exception as e:
            print(f"❌ Error in stats_command: {e}")
            await update.message.reply_text("❌ حدث خطأ في جلب الإحصائيات")
    else:
        await update.message.reply_text("⛔ هذا الأمر للمسؤول فقط.")

# ================= ADMIN PANEL ROUTES =================

@admin_app.route('/')
@login_required
def dashboard():
    """لوحة التحكم الرئيسية"""
    stats = db.get_advanced_stats()
    recent_orders = db.get_orders_with_filters(limit=10)
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         orders=recent_orders,
                         datetime=datetime)

@admin_app.route('/reports')
@login_required
def reports():
    """صفحة التقارير المتقدمة"""
    
    # جلب بيانات الطلبات الأخيرة
    orders = db.get_orders_with_filters(limit=100)
    
    # تحليل البيانات
    stats = {
        'total_orders': len(orders),
        'total_sales': sum(1 for o in orders if o['status'] == 'completed'),
        'today_orders': sum(1 for o in orders if o['created_at'].date() == datetime.now().date())
    }
    
    return render_template('reports.html', 
                         stats=stats, 
                         orders=orders,
                         datetime=datetime)

@admin_app.route('/login', methods=['GET', 'POST'])
def login():
    """تسجيل الدخول"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in ADMINS and check_password_hash(ADMINS[username]['password_hash'], password):
            user = User(ADMINS[username]['id'], username)
            login_user(user)
            session['username'] = username
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='بيانات الدخول غير صحيحة')
    
    return render_template('login.html')

@admin_app.route('/logout')
@login_required
def logout():
    """تسجيل الخروج"""
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# ================= ADMIN PANEL API ROUTES =================

@admin_app.route('/api/orders/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    """تحديث حالة الطلب"""
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['new', 'processing', 'completed', 'cancelled']:
            return jsonify({'error': 'Invalid status'}), 400
        
        db.cursor.execute('''
            UPDATE orders 
            SET status = %s 
            WHERE id = %s AND merchant_id = 1
        ''', (new_status, order_id))
        db.conn.commit()
        
        stats = db.get_advanced_stats()
        
        return jsonify({
            'success': True, 
            'new_status': new_status,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_app.route('/api/orders/<int:order_id>', methods=['DELETE'])
@login_required
def delete_order(order_id):
    """حذف طلب"""
    try:
        db.cursor.execute('DELETE FROM orders WHERE id = %s AND merchant_id = 1', (order_id,))
        db.conn.commit()
        
        stats = db.get_advanced_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_app.route('/api/stats')
@login_required
def get_stats():
    """API للإحصائيات"""
    try:
        stats = db.get_advanced_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@admin_app.route('/api/orders/new/count', methods=['GET'])
@login_required
def new_orders_count():
    """عدد الطلبات الجديدة"""
    try:
        db.cursor.execute('''
            SELECT COUNT(*) as count
            FROM orders 
            WHERE merchant_id = 1 AND status = 'new'
        ''')
        result = db.cursor.fetchone()
        return jsonify({
            'success': True, 
            'count': result['count'] if result else 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_app.route('/api/orders/<int:order_id>', methods=['GET'])
@login_required
def get_order_details(order_id):
    """جلب تفاصيل طلب معين"""
    try:
        db.cursor.execute('''
            SELECT * FROM orders 
            WHERE id = %s AND merchant_id = 1
        ''', (order_id,))
        order = db.cursor.fetchone()
        
        if order:
            return jsonify({
                'success': True,
                'order': order
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'الطلب غير موجود'
            }), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@admin_app.route('/health')
def health():
    """فحص صحة التطبيق"""
    return jsonify({
        'status': 'healthy',
        'service': 'OrderlyBot',
        'database': 'connected' if db.conn else 'disconnected',
        'timestamp': datetime.now().isoformat()
    })

# ================= MAIN FUNCTIONS =================

def run_flask_app():
    """تشغيل تطبيق Flask"""
    port = int(os.getenv('PORT', 10000))
    print(f"🌐 Flask admin panel running on port {port}")
    admin_app.run(host='0.0.0.0', port=port, debug=False, threaded=True)

def run_telegram_bot():
    """تشغيل بوت التليجرام"""
    print("🤖 Starting Telegram Bot...")
    
    # تأخير 120 ثانية (دقيقتين) لتجنب التعارض
    print("⏳ Waiting 120 seconds to avoid bot conflict...")
    time.sleep(120)
    print("✅ Delay completed, starting bot now...")
    
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myorders", myorders_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("✅ Bot handlers registered")
    print("🤖 Bot is polling...")
    
    try:
        app.run_polling(
            drop_pending_updates=True,
            poll_interval=3,
            timeout=20,
            close_loop=False
        )
    except Exception as e:
        print(f"❌ Bot error: {e}")
        print("ℹ️ Bot stopped, but Flask app continues...")
                    
# ================= ENTRY POINT =================
if __name__ == '__main__':
    print("🚀 Starting OrderlyBot with integrated admin panel...")
    print("================================================")
    
    # تشغيل Flask في thread منفصل
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    
    # تشغيل البوت في thread الرئيسي
    try:
        run_telegram_bot()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"❌ Bot error: {e}")