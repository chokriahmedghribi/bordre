# database.py - نسخة معدلة
import sqlite3
import streamlit as st
from datetime import datetime
import pandas as pd

def init_db():
    """تهيئة قاعدة البيانات وإنشاء الجداول"""
    conn = sqlite3.connect('management.db')
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
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # جدول جهات الاتصال (هيكل مبسط)
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES contacts(id)
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
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    
    # إضافة مستخدم افتراضي إذا لم يوجد
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
        INSERT INTO users (username, password, full_name, role, email)
        VALUES (?, ?, ?, ?, ?)
        ''', ('admin', 'admin123', 'مدير النظام', 'مدير', 'admin@system.com'))
    
    conn.commit()
    conn.close()

def get_db_connection():
    """إنشاء اتصال بقاعدة البيانات"""
    return sqlite3.connect('management.db', check_same_thread=False)

def log_activity(user_id, action, details=""):
    """تسجيل نشاط المستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO activity_log (user_id, action, details)
    VALUES (?, ?, ?)
    ''', (user_id, action, details))
    conn.commit()
    conn.close()

# تهيئة قاعدة البيانات عند الاستيراد
init_db()