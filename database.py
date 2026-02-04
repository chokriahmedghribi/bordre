# database.py - نسخة معدلة لنظام المصادقة المحسن
import sqlite3
import streamlit as st
from datetime import datetime
import pandas as pd
import hashlib

def hash_password(password):
    """تجزئة كلمة المرور باستخدام SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول مع نظام الصلاحيات"""
    conn = sqlite3.connect('management.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين (محدث مع حقول جديدة)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        created_by INTEGER,
        notes TEXT
    )
    ''')
    
    # جدول جهات الاتصال
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        organization TEXT,
        phone TEXT,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول البريد الوارد
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS incoming_mail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE,
        sender_id INTEGER,
        sender_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        content TEXT,
        priority TEXT DEFAULT 'عادي',
        status TEXT DEFAULT 'جديد',
        received_date DATE NOT NULL,
        due_date DATE,
        category TEXT,
        attachments TEXT,
        bordereau TEXT,
        notes TEXT,
        recorded_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES contacts(id),
        FOREIGN KEY (recorded_by) REFERENCES users(id)
    )
    ''')
    
    # جدول البريد الصادر
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS outgoing_mail (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_no TEXT UNIQUE,
        recipient_id INTEGER,
        recipient_name TEXT NOT NULL,
        subject TEXT NOT NULL,
        content TEXT,
        priority TEXT DEFAULT 'عادي',
        status TEXT DEFAULT 'مسودة',
        sent_date DATE,
        sent_by INTEGER,
        category TEXT,
        attachments TEXT,
        bordereau TEXT,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (recipient_id) REFERENCES contacts(id),
        FOREIGN KEY (sent_by) REFERENCES users(id)
    )
    ''')
    
    # جدول الإجراءات (المتابعات)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mail_id INTEGER NOT NULL,
        mail_type TEXT NOT NULL,
        action_type TEXT NOT NULL,
        description TEXT,
        assigned_to INTEGER,
        due_date DATE,
        status TEXT DEFAULT 'معلق',
        completed_date DATE,
        notes TEXT,
        created_by INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (mail_id) REFERENCES incoming_mail(id) ON DELETE CASCADE,
        FOREIGN KEY (assigned_to) REFERENCES users(id),
        FOREIGN KEY (created_by) REFERENCES users(id)
    )
    ''')
    
    # جدول سجل النشاطات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT NOT NULL,
        details TEXT,
        ip_address TEXT,
        user_agent TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    # جدول تصنيفات البريد
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mail_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        color TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول أولويات البريد
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS mail_priorities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        level INTEGER DEFAULT 1,
        color TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # جدول إعدادات النظام
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        setting_key TEXT UNIQUE NOT NULL,
        setting_value TEXT,
        description TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # إضافة مستخدمين افتراضيين إذا لم يوجدوا
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        # المشرف الرئيسي
        cursor.execute('''
        INSERT INTO users (username, password, full_name, role, email, created_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('admin', hash_password('admin123'), 'المشرف الرئيسي', 'admin', 
              'admin@school.edu.tn', 1, 'المشرف الرئيسي للنظام'))
        
        # مستخدم عادي
        cursor.execute('''
        INSERT INTO users (username, password, full_name, role, email, created_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('user1', hash_password('user123'), 'مستخدم عادي', 'user', 
              'user@school.edu.tn', 1, 'مستخدم عادي'))
        
        # مستخدم للاستشارة فقط
        cursor.execute('''
        INSERT INTO users (username, password, full_name, role, email, created_by, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('viewer', hash_password('viewer123'), 'مستشار', 'viewer', 
              'viewer@school.edu.tn', 1, 'مستخدم للاستشارة فقط'))
        
        # تحديث الـ ID الخاص بـ created_by
        cursor.execute("UPDATE users SET created_by = 1 WHERE id > 1")
    
    # إضافة تصنيفات البريد الافتراضية
    cursor.execute("SELECT COUNT(*) FROM mail_categories")
    if cursor.fetchone()[0] == 0:
        categories = [
            ('إداري', 'المراسلات الإدارية', '#3498db'),
            ('مالي', 'المراسلات المالية', '#2ecc71'),
            ('فني', 'المراسلات الفنية', '#e74c3c'),
            ('قانوني', 'المراسلات القانونية', '#9b59b6'),
            ('أخرى', 'تصنيفات أخرى', '#95a5a6')
        ]
        
        for category in categories:
            cursor.execute('''
            INSERT INTO mail_categories (name, description, color)
            VALUES (?, ?, ?)
            ''', category)
    
    # إضافة أولويات البريد الافتراضية
    cursor.execute("SELECT COUNT(*) FROM mail_priorities")
    if cursor.fetchone()[0] == 0:
        priorities = [
            ('عادي', 1, '#95a5a6'),
            ('مهم', 2, '#f39c12'),
            ('عاجل', 3, '#e74c3c')
        ]
        
        for priority in priorities:
            cursor.execute('''
            INSERT INTO mail_priorities (name, level, color)
            VALUES (?, ?, ?)
            ''', priority)
    
    # إضافة إعدادات النظام الافتراضية
    cursor.execute("SELECT COUNT(*) FROM system_settings")
    if cursor.fetchone()[0] == 0:
        settings = [
            ('system_name', 'نظام إدارة البريد - المدرسة الإعدادية حي الأمل قابس', 'اسم النظام'),
            ('institution_name', 'المدرسة الإعدادية حي الأمل قابس', 'اسم المؤسسة'),
            ('mail_prefix_incoming', 'و', 'بادئة البريد الوارد'),
            ('mail_prefix_outgoing', 'ص', 'بادئة البريد الصادر'),
            ('due_date_reminder_days', '3', 'أيام التنبيه قبل تاريخ الاستحقاق'),
            ('items_per_page', '20', 'عدد العناصر في الصفحة'),
            ('backup_enabled', '1', 'تفعيل النسخ الاحتياطي'),
            ('backup_frequency', 'daily', 'تكرار النسخ الاحتياطي')
        ]
        
        for setting in settings:
            cursor.execute('''
            INSERT INTO system_settings (setting_key, setting_value, description)
            VALUES (?, ?, ?)
            ''', setting)
    
    # إنشاء فهارس لتحسين الأداء
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_incoming_mail_reference ON incoming_mail(reference_no);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_incoming_mail_status ON incoming_mail(status);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_incoming_mail_due_date ON incoming_mail(due_date);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_outgoing_mail_reference ON outgoing_mail(reference_no);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_outgoing_mail_status ON outgoing_mail(status);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(user_id);
    ''')
    
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_activity_log_date ON activity_log(created_at);
    ''')
    
    conn.commit()
    conn.close()
    print("✅ تم تهيئة قاعدة البيانات بنجاح!")

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    return sqlite3.connect('management.db', check_same_thread=False)

def log_activity(user_id, action, details=""):
    """تسجيل نشاط المستخدم"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # الحصول على معلومات المتصفح (إذا كان في سياق Streamlit)
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            ctx = get_script_run_ctx()
            if ctx:
                ip_address = ctx.request.remote_ip
                user_agent = ctx.request.headers.get('User-Agent', '')
            else:
                ip_address = '127.0.0.1'
                user_agent = 'Unknown'
        except:
            ip_address = '127.0.0.1'
            user_agent = 'Unknown'
        
        cursor.execute('''
        INSERT INTO activity_log (user_id, action, details, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, action, details, ip_address, user_agent))
        
        conn.commit()
    except Exception as e:
        print(f"⚠️ خطأ في تسجيل النشاط: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def update_user_last_login(user_id):
    """تحديث وقت آخر تسجيل دخول للمستخدم"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        UPDATE users 
        SET last_login = CURRENT_TIMESTAMP 
        WHERE id = ?
        ''', (user_id,))
        
        conn.commit()
    except Exception as e:
        print(f"⚠️ خطأ في تحديث وقت آخر تسجيل دخول: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def get_system_setting(key, default=None):
    """الحصول على إعداد نظام"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT setting_value FROM system_settings 
        WHERE setting_key = ?
        ''', (key,))
        
        result = cursor.fetchone()
        return result[0] if result else default
    except Exception as e:
        print(f"⚠️ خطأ في الحصول على إعداد النظام: {e}")
        return default
    finally:
        if 'conn' in locals():
            conn.close()

def set_system_setting(key, value):
    """تعيين إعداد نظام"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO system_settings (setting_key, setting_value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ خطأ في تعيين إعداد النظام: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_statistics():
    """الحصول على إحصائيات النظام"""
    try:
        conn = get_db_connection()
        
        stats = {}
        
        # إحصائيات المستخدمين
        stats['total_users'] = pd.read_sql("SELECT COUNT(*) FROM users WHERE is_active = 1", conn).iloc[0,0]
        stats['active_users'] = pd.read_sql("SELECT COUNT(*) FROM users WHERE is_active = 1 AND last_login IS NOT NULL", conn).iloc[0,0]
        
        # إحصائيات البريد
        stats['total_incoming'] = pd.read_sql("SELECT COUNT(*) FROM incoming_mail", conn).iloc[0,0]
        stats['total_outgoing'] = pd.read_sql("SELECT COUNT(*) FROM outgoing_mail", conn).iloc[0,0]
        stats['pending_incoming'] = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status IN ('جديد', 'قيد المعالجة')", conn).iloc[0,0]
        stats['urgent_mail'] = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE priority = 'عاجل'", conn).iloc[0,0]
        
        # إحصائيات جهات الاتصال
        stats['total_contacts'] = pd.read_sql("SELECT COUNT(*) FROM contacts", conn).iloc[0,0]
        
        # أحدث النشاطات
        stats['recent_activities'] = pd.read_sql('''
        SELECT a.action, a.details, u.full_name, a.created_at 
        FROM activity_log a 
        LEFT JOIN users u ON a.user_id = u.id 
        ORDER BY a.created_at DESC 
        LIMIT 10
        ''', conn)
        
        # البريد القريب من الاستحقاق
        today = datetime.now().strftime('%Y-%m-%d')
        next_week = (datetime.now() + pd.Timedelta(days=7)).strftime('%Y-%m-%d')
        
        stats['due_soon'] = pd.read_sql('''
        SELECT reference_no, subject, due_date, sender_name 
        FROM incoming_mail 
        WHERE due_date IS NOT NULL 
        AND due_date BETWEEN ? AND ?
        AND status NOT IN ('مكتمل', 'ملغي')
        ORDER BY due_date
        ''', conn, params=(today, next_week))
        
        conn.close()
        return stats
        
    except Exception as e:
        print(f"⚠️ خطأ في الحصول على الإحصائيات: {e}")
        return {}

def create_backup():
    """إنشاء نسخة احتياطية من قاعدة البيانات"""
    try:
        import shutil
        from datetime import datetime
        
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/management_backup_{timestamp}.db"
        
        shutil.copy2('management.db', backup_file)
        
        # تسجيل إنشاء النسخة الاحتياطية
        log_activity(0, "نسخة احتياطية", f"تم إنشاء نسخة احتياطية: {backup_file}")
        
        # الحفاظ على آخر 10 نسخ فقط
        import glob
        backups = sorted(glob.glob(f"{backup_dir}/*.db"), key=os.path.getmtime)
        if len(backups) > 10:
            for old_backup in backups[:-10]:
                os.remove(old_backup)
        
        return backup_file
    except Exception as e:
        print(f"⚠️ خطأ في إنشاء النسخة الاحتياطية: {e}")
        return None

def reset_user_password(user_id, new_password):
    """إعادة تعيين كلمة مرور المستخدم"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        hashed_password = hash_password(new_password)
        
        cursor.execute('''
        UPDATE users 
        SET password = ? 
        WHERE id = ?
        ''', (hashed_password, user_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"⚠️ خطأ في إعادة تعيين كلمة المرور: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_user_permissions(user_id):
    """الحصول على صلاحيات المستخدم"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
        SELECT role FROM users WHERE id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        if not result:
            return []
        
        role = result[0]
        
        # تعريف صلاحيات كل دور
        permissions = {
            'admin': ['view', 'add', 'edit', 'delete', 'manage_users', 'export', 
                     'configure_system', 'view_reports', 'manage_backups'],
            'user': ['view', 'add', 'edit', 'export', 'view_reports'],
            'viewer': ['view', 'export']
        }
        
        return permissions.get(role, [])
        
    except Exception as e:
        print(f"⚠️ خطأ في الحصول على صلاحيات المستخدم: {e}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

# تهيئة قاعدة البيانات عند الاستيراد
if __name__ == "__main__":
    init_db()
    
    # عرض معلومات التهيئة
    print("=" * 50)
    print("نظام إدارة البريد - المدرسة الإعدادية حي الأمل قابس")
    print("=" * 50)
    
    conn = get_db_connection()
    
    # عرض المستخدمين المنشئين
    print("\n👥 المستخدمون المنشئون:")
    users_df = pd.read_sql("SELECT username, full_name, role FROM users", conn)
    print(users_df.to_string(index=False))
    
    # عرض الإحصائيات
    print("\n📊 إحصائيات النظام:")
    stats = get_statistics()
    print(f"عدد المستخدمين: {stats.get('total_users', 0)}")
    print(f"البريد الوارد: {stats.get('total_incoming', 0)}")
    print(f"البريد الصادر: {stats.get('total_outgoing', 0)}")
    print(f"جهات الاتصال: {stats.get('total_contacts', 0)}")
    
    # معلومات تسجيل الدخول
    print("\n🔐 معلومات تسجيل الدخول الافتراضية:")
    print("1. المشرف (admin) - صلاحيات كاملة")
    print("   اسم المستخدم: admin")
    print("   كلمة المرور: admin123")
    print("\n2. المستخدم العادي (user) - صلاحيات محدودة")
    print("   اسم المستخدم: user1")
    print("   كلمة المرور: user123")
    print("\n3. المستشار (viewer) - صلاحيات استشارية فقط")
    print("   اسم المستخدم: viewer")
    print("   كلمة المرور: viewer123")
    
    print("\n⚠️ ملاحظة: الرجاء تغيير كلمات المرور بعد أول تسجيل دخول!")
    print("=" * 50)
    
    conn.close()