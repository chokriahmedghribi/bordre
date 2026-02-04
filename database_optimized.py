# database_optimized.py - نسخة محسنة مع Connection Pooling و Caching
import sqlite3
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
import hashlib
from functools import lru_cache
from contextlib import contextmanager
import threading

# Connection Pool
class ConnectionPool:
    """مجمع اتصالات قاعدة البيانات لتحسين الأداء"""
    def __init__(self, db_name='management.db', pool_size=5):
        self.db_name = db_name
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        
    def get_connection(self):
        """الحصول على اتصال من المجمع"""
        with self.lock:
            if self.connections:
                return self.connections.pop()
            return sqlite3.connect(self.db_name, check_same_thread=False)
    
    def return_connection(self, conn):
        """إرجاع الاتصال إلى المجمع"""
        with self.lock:
            if len(self.connections) < self.pool_size:
                self.connections.append(conn)
            else:
                conn.close()
    
    def close_all(self):
        """إغلاق جميع الاتصالات"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()

# إنشاء مجمع الاتصالات العام
_connection_pool = ConnectionPool()

@contextmanager
def get_db_connection():
    """Context manager للحصول على اتصال قاعدة البيانات"""
    conn = _connection_pool.get_connection()
    try:
        yield conn
    finally:
        _connection_pool.return_connection(conn)

def hash_password(password):
    """تجزئة كلمة المرور باستخدام SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

# Cache للبيانات المستخدمة بشكل متكرر
@st.cache_data(ttl=300)  # Cache لمدة 5 دقائق
def get_contacts_cached():
    """جلب جهات الاتصال مع التخزين المؤقت"""
    with get_db_connection() as conn:
        try:
            df = pd.read_sql(
                "SELECT id, code, name, organization, phone, email FROM contacts ORDER BY name",
                conn
            )
            return df
        except:
            return pd.DataFrame()

@st.cache_data(ttl=300)
def get_users_cached():
    """جلب المستخدمين مع التخزين المؤقت"""
    with get_db_connection() as conn:
        try:
            df = pd.read_sql(
                "SELECT id, username, full_name, role FROM users WHERE is_active = 1 ORDER BY full_name",
                conn
            )
            return df
        except:
            return pd.DataFrame()

@st.cache_data(ttl=60)  # Cache لمدة دقيقة واحدة
def get_statistics_cached():
    """الحصول على إحصائيات النظام مع التخزين المؤقت"""
    with get_db_connection() as conn:
        stats = {}
        try:
            stats['total_users'] = pd.read_sql("SELECT COUNT(*) as count FROM users WHERE is_active = 1", conn).iloc[0,0]
            stats['total_incoming'] = pd.read_sql("SELECT COUNT(*) as count FROM incoming_mail", conn).iloc[0,0]
            stats['total_outgoing'] = pd.read_sql("SELECT COUNT(*) as count FROM outgoing_mail", conn).iloc[0,0]
            stats['new_mail'] = pd.read_sql("SELECT COUNT(*) as count FROM incoming_mail WHERE status = 'جديد'", conn).iloc[0,0]
            stats['pending_mail'] = pd.read_sql("SELECT COUNT(*) as count FROM incoming_mail WHERE status = 'قيد المعالجة'", conn).iloc[0,0]
            stats['total_contacts'] = pd.read_sql("SELECT COUNT(*) as count FROM contacts", conn).iloc[0,0]
        except:
            pass
        return stats

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول مع الفهارس المحسنة"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # جدول المستخدمين
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
        
        # جدول الإجراءات
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
        
        # إنشاء فهارس محسنة للأداء
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_incoming_mail_reference ON incoming_mail(reference_no)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_mail_status ON incoming_mail(status)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_mail_priority ON incoming_mail(priority)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_mail_due_date ON incoming_mail(due_date)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_mail_received_date ON incoming_mail(received_date)",
            "CREATE INDEX IF NOT EXISTS idx_outgoing_mail_reference ON outgoing_mail(reference_no)",
            "CREATE INDEX IF NOT EXISTS idx_outgoing_mail_status ON outgoing_mail(status)",
            "CREATE INDEX IF NOT EXISTS idx_outgoing_mail_sent_date ON outgoing_mail(sent_date)",
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
            "CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_user ON activity_log(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_log_date ON activity_log(created_at)"
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        # إضافة مستخدمين افتراضيين
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            default_users = [
                ('admin', hash_password('admin123'), 'المشرف الرئيسي', 'admin', 'admin@school.edu.tn', 1),
                ('user1', hash_password('user123'), 'مستخدم عادي', 'user', 'user@school.edu.tn', 1),
                ('viewer', hash_password('viewer123'), 'مستشار', 'viewer', 'viewer@school.edu.tn', 1)
            ]
            
            for user in default_users:
                cursor.execute('''
                INSERT INTO users (username, password, full_name, role, email, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', user)
        
        conn.commit()
        print("✅ تم تهيئة قاعدة البيانات بنجاح!")

def log_activity(user_id, action, details=""):
    """تسجيل نشاط المستخدم بشكل غير متزامن"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO activity_log (user_id, action, details, ip_address)
            VALUES (?, ?, ?, ?)
            ''', (user_id, action, details, '127.0.0.1'))
            conn.commit()
    except Exception as e:
        print(f"⚠️ خطأ في تسجيل النشاط: {e}")

def get_mail_paginated(mail_type="incoming", page=1, per_page=20, filters=None):
    """جلب البريد مع الترقيم (Pagination) لتحسين الأداء"""
    offset = (page - 1) * per_page
    
    with get_db_connection() as conn:
        table = "incoming_mail" if mail_type == "incoming" else "outgoing_mail"
        
        # بناء الاستعلام مع الفلاتر
        where_clauses = []
        params = []
        
        if filters:
            if filters.get('status'):
                where_clauses.append("status = ?")
                params.append(filters['status'])
            if filters.get('priority'):
                where_clauses.append("priority = ?")
                params.append(filters['priority'])
            if filters.get('search'):
                where_clauses.append("(reference_no LIKE ? OR subject LIKE ? OR sender_name LIKE ?)")
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term, search_term])
        
        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        # الحصول على العدد الإجمالي
        count_query = f"SELECT COUNT(*) FROM {table}{where_sql}"
        total = pd.read_sql(count_query, conn, params=params).iloc[0,0]
        
        # جلب البيانات
        date_field = "received_date" if mail_type == "incoming" else "sent_date"
        query = f"SELECT * FROM {table}{where_sql} ORDER BY {date_field} DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        
        df = pd.read_sql(query, conn, params=params)
        
        return df, total

def clear_cache():
    """مسح جميع البيانات المخزنة مؤقتاً"""
    st.cache_data.clear()

# تهيئة قاعدة البيانات عند الاستيراد
init_db()
