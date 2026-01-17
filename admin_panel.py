from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# استيراد قاعدة البيانات من ملفنا الرئيسي
import sys
sys.path.append('.')
from database import db

# ================= FLASK APP =================
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

# كلمات مرور مشفرة (أنت فقط الآن)
ADMINS = {
    "admin": {
        "id": 1,
        "password_hash": generate_password_hash("admin123")  # مشفرة
    }
}

@login_manager.user_loader
def load_user(user_id):
    if user_id == "1":  # أنت فقط حالياً
        return User(1, "admin")
    return None

# ================= HELPER FUNCTIONS =================
def get_orders_with_filters(status_filter='all', category_filter='all', limit=50):
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
        
        db.cursor.execute(query, params)
        return db.cursor.fetchall()
    except Exception as e:
        print(f"❌ Error in get_orders_with_filters: {e}")
        return []

def get_advanced_stats():
    """جلب إحصائيات متقدمة"""
    try:
        stats = {}
        
        # إحصائيات أساسية
        db.cursor.execute('''
            SELECT 
                COUNT(*) as total_orders,
                SUM(CASE WHEN status = 'new' THEN 1 ELSE 0 END) as new_orders,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_orders,
                SUM(CASE WHEN DATE(created_at) = CURRENT_DATE THEN 1 ELSE 0 END) as today_orders
            FROM orders 
            WHERE merchant_id = 1
        ''')
        basic_stats = db.cursor.fetchone()
        
        stats.update(basic_stats)
        
        # إحصائيات حسب الفئة
        db.cursor.execute('''
            SELECT category, COUNT(*) as count
            FROM orders 
            WHERE merchant_id = 1
            GROUP BY category
        ''')
        stats['category_stats'] = db.cursor.fetchall()
        
        # آخر 7 أيام
        db.cursor.execute('''
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as count
            FROM orders 
            WHERE merchant_id = 1 
            AND created_at >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(created_at)
            ORDER BY date
        ''')
        stats['weekly_stats'] = db.cursor.fetchall()
        
        return stats
        
    except Exception as e:
        print(f"❌ Error getting advanced stats: {e}")
        return {}

# ================= ROUTES =================
@admin_app.route('/')
@login_required
def dashboard():
    """الصفحة الرئيسية"""
    stats = get_advanced_stats()
    recent_orders = get_orders_with_filters(limit=10)
    
    return render_template('dashboard.html', 
                         stats=stats, 
                         orders=recent_orders,
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

# ================= API ROUTES =================
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
        
        # جلب الإحصائيات المحدثة
        stats = get_advanced_stats()
        
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
        
        # جلب الإحصائيات المحدثة
        stats = get_advanced_stats()
        
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
        stats = get_advanced_stats()
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

# ================= RUN ADMIN PANEL =================
# في نهاية الملف بدل run_admin_panel()
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    admin_app.run(host='0.0.0.0', port=port, debug=False)