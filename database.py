import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
import sqlite3
from datetime import datetime, timedelta

class Database:
    def __init__(self):
        self.conn = None
        self.cursor = None
        self.db_type = None
        self.connect()
    
    def connect(self):
        """الاتصال بقاعدة البيانات مع خيار احتياطي"""
        # محاولة PostgreSQL أولاً
        if self._connect_postgresql():
            return
        
        # إذا فشل PostgreSQL، جرب SQLite
        if self._connect_sqlite():
            return
        
        # إذا فشل كلاهما
        print("❌ فشل الاتصال بجميع قواعد البيانات")
        self._create_in_memory_db()
    
    def _connect_postgresql(self):
        """محاولة الاتصال بـ PostgreSQL"""
        try:
            DATABASE_URL = os.environ.get('DATABASE_URL')
            if not DATABASE_URL:
                print("⚠️ DATABASE_URL not found, skipping PostgreSQL")
                return False
            
            self.conn = psycopg2.connect(DATABASE_URL, sslmode='require')
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            self.db_type = 'postgresql'
            
            # اختبار الاتصال
            self.cursor.execute('SELECT 1')
            self.create_tables()
            
            print("✅ Connected to PostgreSQL successfully")
            return True
            
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            return False
    
    def _connect_sqlite(self):
        """محاولة الاتصال بـ SQLite كخيار احتياطي"""
        try:
            self.conn = sqlite3.connect("orders_backup.db", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.db_type = 'sqlite'
            
            self.create_tables()
            print("✅ Connected to SQLite (fallback mode)")
            return True
            
        except Exception as e:
            print(f"❌ SQLite connection failed: {e}")
            return False
    
    def _create_in_memory_db(self):
        """إنشاء قاعدة بيانات في الذاكرة كحل أخير"""
        try:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.db_type = 'memory'
            
            self.create_tables()
            print("⚠️ Using in-memory database (temporary)")
            return True
            
        except Exception as e:
            print(f"❌ Critical: All database connections failed: {e}")
            raise e
    
    def check_connection(self):
        """فحص حالة الاتصال"""
        try:
            if self.db_type == 'postgresql':
                self.cursor.execute('SELECT 1')
            else:
                self.cursor.execute('SELECT 1')
            return True
        except:
            return False
    
    def create_tables(self):
        """إنشاء الجداول"""
        try:
            if self.db_type == 'postgresql':
                self._create_postgres_tables()
            else:
                self._create_sqlite_tables()
            
            self.conn.commit()
            print("✅ Database tables created/verified")
            
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            if self.conn:
                self.conn.rollback()
    
    def _create_postgres_tables(self):
        """إنشاء جداول PostgreSQL"""
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
                subscription_end DATE,
                settings JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # جدول الإحصائيات اليومية
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                id SERIAL PRIMARY KEY,
                merchant_id INTEGER,
                date DATE DEFAULT CURRENT_DATE,
                total_orders INTEGER DEFAULT 0,
                completed_orders INTEGER DEFAULT 0,
                total_revenue DECIMAL(10, 2) DEFAULT 0,
                UNIQUE(merchant_id, date)
            )
        ''')
        
        # إضافة التاجر الرئيسي (أنت)
        self.cursor.execute('''
            INSERT INTO merchants (id, telegram_id, username, business_name, plan)
            VALUES (1, 5812937391, 'admin', 'OrderlyBot Admin', 'pro')
            ON CONFLICT (id) DO NOTHING
        ''')
    
    def _create_sqlite_tables(self):
        """إنشاء جداول SQLite"""
        # جدول الطلبات
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                product TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT NOT NULL,
                quantity TEXT NOT NULL,
                size TEXT,
                language TEXT DEFAULT 'ar',
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                merchant_id INTEGER DEFAULT 1
            )
        ''')
        
        # جدول التجار
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                username TEXT,
                business_name TEXT,
                plan TEXT DEFAULT 'trial',
                subscription_end DATE,
                settings TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # إضافة التاجر الرئيسي
        self.cursor.execute('''
            INSERT OR IGNORE INTO merchants (id, telegram_id, username, business_name, plan)
            VALUES (1, 5812937391, 'admin', 'OrderlyBot Admin', 'pro')
        ''')
    
    def add_order(self, order_data):
        """إضافة طلب جديد"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    INSERT INTO orders 
                    (category, product, customer_name, phone, address, quantity, size, language, merchant_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                '''
            else:
                query = '''
                    INSERT INTO orders 
                    (category, product, customer_name, phone, address, quantity, size, language, merchant_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                '''
            
            params = (
                order_data['category'],
                order_data['product'],
                order_data['name'],
                order_data['phone'],
                order_data['address'],
                order_data['quantity'],
                order_data.get('size', ''),
                order_data['lang'],
                1
            )
            
            self.cursor.execute(query, params)
            self.conn.commit()
            
            # جلب ID الطلب
            if self.db_type == 'postgresql':
                order_id = self.cursor.fetchone()['id']
            else:
                order_id = self.cursor.lastrowid
            
            # تحديث الإحصائيات
            self.update_daily_stats(1)
            
            return order_id
            
        except Exception as e:
            print(f"❌ Error adding order: {e}")
            if self.conn:
                self.conn.rollback()
            return None
    
    def get_orders(self, merchant_id, filters=None, limit=100):
        """جلب الطلبات مع فلتر"""
        try:
            query = '''
                SELECT * FROM orders 
                WHERE merchant_id = %s
            ''' if self.db_type == 'postgresql' else '''
                SELECT * FROM orders 
                WHERE merchant_id = ?
            '''
            
            params = [merchant_id]
            
            # تطبيق الفلاتر
            if filters:
                if filters.get('status'):
                    query += ' AND status = %s' if self.db_type == 'postgresql' else ' AND status = ?'
                    params.append(filters['status'])
                
                if filters.get('category'):
                    query += ' AND category = %s' if self.db_type == 'postgresql' else ' AND category = ?'
                    params.append(filters['category'])
                
                if filters.get('start_date') and filters.get('end_date'):
                    query += ' AND DATE(created_at) BETWEEN %s AND %s' if self.db_type == 'postgresql' else ' AND DATE(created_at) BETWEEN ? AND ?'
                    params.extend([filters['start_date'], filters['end_date']])
            
            query += ' ORDER BY created_at DESC LIMIT %s' if self.db_type == 'postgresql' else ' ORDER BY created_at DESC LIMIT ?'
            params.append(limit)
            
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
            
        except Exception as e:
            print(f"❌ Error getting orders: {e}")
            return []
    
    def get_order_stats(self, merchant_id):
        """الحصول على إحصائيات الطلبات"""
        try:
            stats = {}
            
            # إجمالي الطلبات
            query = 'SELECT COUNT(*) FROM orders WHERE merchant_id = %s' if self.db_type == 'postgresql' else 'SELECT COUNT(*) FROM orders WHERE merchant_id = ?'
            self.cursor.execute(query, (merchant_id,))
            stats['total'] = self.cursor.fetchone()[0] if self.db_type == 'sqlite' else self.cursor.fetchone()['count']
            
            # الطلبات الجديدة
            query = "SELECT COUNT(*) FROM orders WHERE merchant_id = %s AND status = 'new'" if self.db_type == 'postgresql' else "SELECT COUNT(*) FROM orders WHERE merchant_id = ? AND status = 'new'"
            self.cursor.execute(query, (merchant_id,))
            stats['new'] = self.cursor.fetchone()[0] if self.db_type == 'sqlite' else self.cursor.fetchone()['count']
            
            # الطلبات المكتملة
            query = "SELECT COUNT(*) FROM orders WHERE merchant_id = %s AND status = 'completed'" if self.db_type == 'postgresql' else "SELECT COUNT(*) FROM orders WHERE merchant_id = ? AND status = 'completed'"
            self.cursor.execute(query, (merchant_id,))
            stats['completed'] = self.cursor.fetchone()[0] if self.db_type == 'sqlite' else self.cursor.fetchone()['count']
            
            # طلبات اليوم
            if self.db_type == 'postgresql':
                query = '''
                    SELECT COUNT(*) FROM orders 
                    WHERE merchant_id = %s AND DATE(created_at) = CURRENT_DATE
                '''
            else:
                query = '''
                    SELECT COUNT(*) FROM orders 
                    WHERE merchant_id = ? AND DATE(created_at) = DATE('now')
                '''
            
            self.cursor.execute(query, (merchant_id,))
            stats['today'] = self.cursor.fetchone()[0] if self.db_type == 'sqlite' else self.cursor.fetchone()['count']
            
            # طلبات الأسبوع
            if self.db_type == 'postgresql':
                query = '''
                    SELECT COUNT(*) FROM orders 
                    WHERE merchant_id = %s AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                '''
            else:
                query = '''
                    SELECT COUNT(*) FROM orders 
                    WHERE merchant_id = ? AND created_at >= DATE('now', '-7 days')
                '''
            
            self.cursor.execute(query, (merchant_id,))
            stats['weekly'] = self.cursor.fetchone()[0] if self.db_type == 'sqlite' else self.cursor.fetchone()['count']
            
            return stats
            
        except Exception as e:
            print(f"❌ Error getting stats: {e}")
            return {'total': 0, 'new': 0, 'completed': 0, 'today': 0, 'weekly': 0}
    
    def update_order_status(self, order_id, status):
        """تحديث حالة الطلب"""
        try:
            if self.db_type == 'postgresql':
                query = 'UPDATE orders SET status = %s WHERE id = %s'
            else:
                query = 'UPDATE orders SET status = ? WHERE id = ?'
            
            self.cursor.execute(query, (status, order_id))
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"❌ Error updating order status: {e}")
            return False
    
    def update_daily_stats(self, merchant_id):
        """تحديث الإحصائيات اليومية"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    INSERT INTO daily_stats (merchant_id, total_orders, completed_orders)
                    VALUES (%s, 1, 0)
                    ON CONFLICT (merchant_id, date) 
                    DO UPDATE SET total_orders = daily_stats.total_orders + 1
                '''
            else:
                query = '''
                    INSERT OR REPLACE INTO daily_stats (merchant_id, date, total_orders, completed_orders)
                    VALUES (?, DATE('now'), 
                        COALESCE((SELECT total_orders FROM daily_stats WHERE merchant_id = ? AND date = DATE('now')), 0) + 1,
                        COALESCE((SELECT completed_orders FROM daily_stats WHERE merchant_id = ? AND date = DATE('now')), 0)
                    )
                '''
                params = (merchant_id, merchant_id, merchant_id)
                self.cursor.execute(query, params)
                self.conn.commit()
                return
            
            self.cursor.execute(query, (merchant_id,))
            self.conn.commit()
            
        except Exception as e:
            print(f"❌ Error updating daily stats: {e}")
    
    def get_weekly_report(self, merchant_id):
        """تقرير الطلبات الأسبوعي"""
        try:
            if self.db_type == 'postgresql':
                query = '''
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as total_orders,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders
                    FROM orders 
                    WHERE merchant_id = %s 
                    AND created_at >= CURRENT_DATE - INTERVAL '7 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date
                '''
            else:
                query = '''
                    SELECT 
                        DATE(created_at) as date,
                        COUNT(*) as total_orders,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders
                    FROM orders 
                    WHERE merchant_id = ? 
                    AND created_at >= DATE('now', '-7 days')
                    GROUP BY DATE(created_at)
                    ORDER BY date
                '''
            
            self.cursor.execute(query, (merchant_id,))
            return self.cursor.fetchall()
            
        except Exception as e:
            print(f"❌ Error getting weekly report: {e}")
            return []
    
    def backup_database(self, backup_path='backup.db'):
        """إنشاء نسخة احتياطية"""
        try:
            if self.db_type == 'sqlite':
                import shutil
                shutil.copy2('orders_backup.db', backup_path)
                print(f"✅ Backup created: {backup_path}")
            elif self.db_type == 'postgresql':
                print("ℹ️ PostgreSQL backups managed by Render")
            return True
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            return False

# إنشاء كائن قاعدة بيانات عالمي
db = Database()