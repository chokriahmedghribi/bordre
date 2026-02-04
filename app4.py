# app.py - مع سكربت إنشاء البوردرية المحدث والنظام المحسن
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
from datetime import datetime, date, timedelta
import json
import tempfile
import io
import hashlib
import secrets
from database import get_db_connection, log_activity
from docxtpl import DocxTemplate
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="المدرسة الإعدادية حي الامل قابس - مكتب الضبط",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تحميل التنسيقات
try:
    with open('style.css', encoding='utf-8') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("⚠️ ملف style.css غير موجود. سيتم استخدام تنسيقات افتراضية.")

# إدارة حالة التنقل والمستخدم
if 'page' not in st.session_state:
    st.session_state.page = "لوحة القيادة"
if 'user' not in st.session_state:
    st.session_state.user = None
if 'mail_filter' not in st.session_state:
    st.session_state.mail_filter = "الكل"
if 'edit_mail_id' not in st.session_state:
    st.session_state.edit_mail_id = None
if 'edit_mail_type' not in st.session_state:
    st.session_state.edit_mail_type = None
if 'view_mail_id' not in st.session_state:
    st.session_state.view_mail_id = None
if 'view_mail_type' not in st.session_state:
    st.session_state.view_mail_type = None
if 'show_contact_form' not in st.session_state:
    st.session_state.show_contact_form = False
if 'selected_mail_for_bordereau' not in st.session_state:
    st.session_state.selected_mail_for_bordereau = None
if 'bordereau_data' not in st.session_state:
    st.session_state.bordereau_data = None
if 'bordereau_buffer' not in st.session_state:
    st.session_state.bordereau_buffer = None
if 'manage_users_mode' not in st.session_state:
    st.session_state.manage_users_mode = "view"

# --- دالة التجزئة لكلمات المرور ---
def hash_password(password):
    """تجزئة كلمة المرور باستخدام SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_temp_password(length=8):
    """توليد كلمة مرور مؤقتة"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# --- نظام المصادقة المحسن ---
def authenticate_user(username, password):
    """مصادقة المستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    hashed_password = hash_password(password)
    
    cursor.execute('''
    SELECT id, username, full_name, role, email, is_active FROM users 
    WHERE username = ? AND password = ? AND is_active = 1
    ''', (username, hashed_password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        st.session_state.user = {
            'id': user[0],
            'username': user[1],
            'full_name': user[2],
            'role': user[3],
            'email': user[4],
            'is_active': user[5]
        }
        log_activity(user[0], "تسجيل دخول", f"المستخدم {user[2]} سجل دخول")
        return True
    return False

def logout_user():
    """تسجيل خروج المستخدم"""
    if st.session_state.user:
        log_activity(st.session_state.user['id'], "تسجيل خروج")
    st.session_state.user = None
    st.session_state.page = "لوحة القيادة"
    st.rerun()

def check_permission(required_permission="view"):
    """
    التحقق من صلاحيات المستخدم
    
    الصلاحيات:
    - admin: يمكنه كل شيء
    - user: يمكنه إضافة وتعديل البريد
    - viewer: يمكنه فقط الاستعلام والقراءة
    """
    if not st.session_state.user:
        return False
    
    user_role = st.session_state.user['role']
    
    # تعريف صلاحيات كل دور
    permissions = {
        'admin': ['view', 'add', 'edit', 'delete', 'manage_users', 'export'],
        'user': ['view', 'add', 'edit', 'export'],
        'viewer': ['view', 'export']
    }
    
    # التحقق من أن الدور موجود في القائمة
    if user_role not in permissions:
        return False
    
    # التحقق من الصلاحية المطلوبة
    return required_permission in permissions[user_role]

# --- وظائف إدارة المستخدمين ---
def get_all_users():
    """جلب جميع المستخدمين"""
    conn = get_db_connection()
    try:
        df = pd.read_sql("""
            SELECT id, username, full_name, role, email, 
                   created_at, last_login, is_active,
                   CASE WHEN role = 'admin' THEN 'مشرف'
                        WHEN role = 'user' THEN 'مستخدم'
                        WHEN role = 'viewer' THEN 'مستشار'
                        ELSE role END as role_display
            FROM users 
            ORDER BY created_at DESC
        """, conn)
    except Exception as e:
        st.error(f"خطأ في جلب المستخدمين: {str(e)}")
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def create_user(username, full_name, email, role, password=None):
    """إنشاء مستخدم جديد"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # التحقق من أن اسم المستخدم غير مستخدم
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, "اسم المستخدم موجود مسبقاً"
        
        # توليد كلمة مرور مؤقتة إذا لم يتم تقديم واحدة
        if not password:
            temp_password = generate_temp_password()
        else:
            temp_password = password
        
        hashed_password = hash_password(temp_password)
        
        cursor.execute('''
        INSERT INTO users (username, password, full_name, email, role, is_active, created_by)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        ''', (username, hashed_password, full_name, email, role, st.session_state.user['id']))
        
        conn.commit()
        log_activity(st.session_state.user['id'], "إنشاء مستخدم", 
                   f"تم إنشاء مستخدم جديد: {username}")
        
        return True, temp_password
    
    except Exception as e:
        return False, f"خطأ في إنشاء المستخدم: {str(e)}"
    
    finally:
        conn.close()

def update_user(user_id, full_name=None, email=None, role=None, is_active=None):
    """تحديث بيانات المستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        updates = []
        params = []
        
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name)
        
        if email is not None:
            updates.append("email = ?")
            params.append(email)
        
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        
        if updates:
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            
            log_activity(st.session_state.user['id'], "تحديث مستخدم", 
                       f"تم تحديث بيانات المستخدم ID: {user_id}")
            return True, "تم تحديث بيانات المستخدم بنجاح"
        
        return False, "لا توجد تحديثات لإجرائها"
    
    except Exception as e:
        return False, f"خطأ في تحديث المستخدم: {str(e)}"
    
    finally:
        conn.close()

def reset_user_password(user_id):
    """إعادة تعيين كلمة مرور المستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # توليد كلمة مرور مؤقتة جديدة
        temp_password = generate_temp_password()
        hashed_password = hash_password(temp_password)
        
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", 
                      (hashed_password, user_id))
        conn.commit()
        
        log_activity(st.session_state.user['id'], "إعادة تعيين كلمة مرور", 
                   f"تم إعادة تعيين كلمة مرور المستخدم ID: {user_id}")
        
        return True, temp_password
    
    except Exception as e:
        return False, f"خطأ في إعادة تعيين كلمة المرور: {str(e)}"
    
    finally:
        conn.close()

def change_own_password(old_password, new_password):
    """تغيير كلمة مرور المستخدم الحالي"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # التحقق من كلمة المرور القديمة
        user_id = st.session_state.user['id']
        hashed_old = hash_password(old_password)
        
        cursor.execute("SELECT id FROM users WHERE id = ? AND password = ?", 
                      (user_id, hashed_old))
        
        if not cursor.fetchone():
            return False, "كلمة المرور القديمة غير صحيحة"
        
        # تحديث كلمة المرور الجديدة
        hashed_new = hash_password(new_password)
        cursor.execute("UPDATE users SET password = ? WHERE id = ?", 
                      (hashed_new, user_id))
        conn.commit()
        
        log_activity(user_id, "تغيير كلمة المرور", "تم تغيير كلمة المرور بنجاح")
        return True, "تم تغيير كلمة المرور بنجاح"
    
    except Exception as e:
        return False, f"خطأ في تغيير كلمة المرور: {str(e)}"
    
    finally:
        conn.close()

def delete_user(user_id):
    """حذف مستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # التحقق من أن المستخدم ليس المشرف الوحيد
        cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1")
        admin_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        user_role = cursor.fetchone()[0]
        
        if user_role == 'admin' and admin_count <= 1:
            return False, "لا يمكن حذف المشرف الوحيد في النظام"
        
        # حذف المستخدم
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        
        log_activity(st.session_state.user['id'], "حذف مستخدم", 
                   f"تم حذف المستخدم ID: {user_id}")
        return True, "تم حذف المستخدم بنجاح"
    
    except Exception as e:
        return False, f"خطأ في حذف المستخدم: {str(e)}"
    
    finally:
        conn.close()

# --- الوظائف المساعدة ---
def generate_ref_no(mail_type="incoming"):
    """توليد رقم مرجعي بالتنسيق الجديد"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    current_month = datetime.now().strftime('%m')
    current_year = datetime.now().strftime('%Y')
    
    prefix = "و" if mail_type == "incoming" else "ص"
    
    try:
        if mail_type == "incoming":
            cursor.execute(f'''
            SELECT MAX(CAST(SUBSTR(reference_no, 3, 4) AS INTEGER)) 
            FROM incoming_mail 
            WHERE reference_no LIKE '{prefix}-____-{current_month}-{current_year}'
            ''')
        else:
            cursor.execute(f'''
            SELECT MAX(CAST(SUBSTR(reference_no, 3, 4) AS INTEGER)) 
            FROM outgoing_mail 
            WHERE reference_no LIKE '{prefix}-____-{current_month}-{current_year}'
            ''')
        
        result = cursor.fetchone()[0]
        count = result if result is not None else 0
    except:
        count = 0
    
    conn.close()
    
    return f"{prefix}-{count+1:04d}-{current_month}-{current_year}"

def get_contacts():
    """جلب جميع جهات الاتصال"""
    conn = get_db_connection()
    try:
        df = pd.read_sql("SELECT id, code, name, organization, phone, email FROM contacts ORDER BY name", conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def get_users():
    """جلب جميع المستخدمين (للأغراض العامة)"""
    conn = get_db_connection()
    try:
        df = pd.read_sql("SELECT id, username, full_name, role FROM users WHERE is_active = 1 ORDER BY full_name", conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df

def get_contact_by_id(contact_id):
    """جلب معلومات جهة اتصال حسب ID"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name, organization, phone, email FROM contacts WHERE id = ?", (contact_id,))
    contact = cursor.fetchone()
    conn.close()
    
    if contact:
        return {
            'name': contact[0],
            'organization': contact[1],
            'phone': contact[2],
            'email': contact[3]
        }
    return None

def get_mail_by_id(mail_id, mail_type="incoming"):
    """جلب معلومات البريد حسب ID"""
    conn = get_db_connection()
    
    if mail_type == "incoming":
        query = "SELECT * FROM incoming_mail WHERE id = ?"
    else:
        query = "SELECT * FROM outgoing_mail WHERE id = ?"
    
    try:
        df = pd.read_sql(query, conn, params=(mail_id,))
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    
    if not df.empty:
        return df.iloc[0].to_dict()
    return None

def check_due_date_reminders():
    """فحص تواريخ الاستحقاق القريبة"""
    conn = get_db_connection()
    today = date.today()
    three_days_later = today + timedelta(days=3)
    
    query = """
    SELECT reference_no, subject, due_date, sender_name 
    FROM incoming_mail 
    WHERE due_date IS NOT NULL 
    AND due_date BETWEEN ? AND ?
    AND status NOT IN ('مكتمل', 'ملغي')
    ORDER BY due_date
    """
    
    try:
        df = pd.read_sql(query, conn, params=(today.strftime('%Y-%m-%d'), three_days_later.strftime('%Y-%m-%d')))
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    
    return df

# --- وظائف إدارة الملفات ---
def save_uploaded_file(uploaded_file, mail_type="incoming"):
    """حفظ الملف المرفوع"""
    if uploaded_file is None:
        return None
    
    upload_dir = f"uploads/{mail_type}"
    os.makedirs(upload_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = os.path.splitext(uploaded_file.name)[1]
    filename = f"{timestamp}_{uploaded_file.name}"
    filepath = os.path.join(upload_dir, filename)
    
    try:
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return filepath
    except Exception as e:
        st.error(f"خطأ في حفظ الملف: {str(e)}")
        return None

def get_attachment_list(attachments_json):
    """الحصول على قائمة المرفقات من JSON"""
    if attachments_json and isinstance(attachments_json, str):
        try:
            return json.loads(attachments_json)
        except:
            return []
    elif attachments_json and isinstance(attachments_json, list):
        return attachments_json
    return []

# --- وظيفة إنشاء البوردرية باستخدام القالب ---
def generate_bordereau_for_mail(mail_data, contact_info=None):
    """
    إنشاء بوردرية للبريد الصادر باستخدام القالب الموجود
    
    Args:
        mail_data (dict): بيانات البريد الصادر
        contact_info (dict): معلومات جهة الاتصال (اختياري)
    
    Returns:
        BytesIO: الملف الناتج في الذاكرة أو None إذا فشل
    """
    template_path = "templates/bordereau_template.docx"
    
    # التحقق من وجود القالب
    if not os.path.exists(template_path):
        st.error("❌ قالب البوردرية غير موجود. الرجاء وضع القالب في: templates/bordereau_template.docx")
        st.info("""
        **متغيرات القالب المطلوبة:**
        - {{ reference_no }} : رقم المرجع
        - {{ sent_date }} : تاريخ الإرسال
        - {{ recipient_name }} : اسم المستلم
        - {{ organization }} : المؤسسة
        - {{ phone }} : الهاتف
        - {{ email }} : البريد الإلكتروني
        - {{ subject }} : الموضوع
        - {{ notes }} : الملاحظات
        """)
        return None
    
    try:
        # تحميل القالب
        doc = DocxTemplate(template_path)
        
        # إعداد البيانات (Context)
        context = {
            'reference_no': mail_data.get('reference_no', 'غير محدد'),
            'sent_date': mail_data.get('sent_date', 'غير محدد'),
            'recipient_name': mail_data.get('recipient_name', 'غير محدد'),
            'organization': contact_info.get('organization', '') if contact_info else '',
            'phone': contact_info.get('phone', '') if contact_info else '',
            'email': contact_info.get('email', '') if contact_info else '',
            'subject': mail_data.get('subject', 'غير محدد'),
            'notes': mail_data.get('notes', '')
        }
        
        # تعبئة القالب بالبيانات
        doc.render(context)
        
        # حفظ الملف في الذاكرة
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
        
    except Exception as e:
        st.error(f"❌ خطأ في إنشاء البوردرية: {str(e)}")
        return None

# --- وظائف تعديل البريد ---
def edit_incoming_mail(mail_id):
    """تعديل بريد وارد"""
    if not check_permission('edit'):
        st.warning("⚠️ ليس لديك صلاحية لتعديل البريد الوارد")
        st.session_state.edit_mail_id = None
        st.session_state.edit_mail_type = None
        st.rerun()
        return
    
    st.markdown('<div class="card"><h3>تعديل البريد الوارد</h3></div>', unsafe_allow_html=True)
    
    # جلب بيانات البريد
    mail_data = get_mail_by_id(mail_id, "incoming")
    
    if not mail_data:
        st.error("❌ لم يتم العثور على البريد المطلوب")
        st.button("← العودة", on_click=lambda: [setattr(st.session_state, 'edit_mail_id', None), 
                                                 setattr(st.session_state, 'edit_mail_type', None), 
                                                 st.rerun()])
        return
    
    # جلب قائمة جهات الاتصال
    contacts_df = get_contacts()
    
    with st.form("edit_incoming_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع *", value=mail_data.get('reference_no', ''))
            
            # الحصول على المرسل الحالي
            current_sender = mail_data.get('sender_name', '')
            sender_options = ["--- اختر من جهات الاتصال ---"]
            
            if not contacts_df.empty:
                for _, row in contacts_df.iterrows():
                    display_text = f"{row['name']}"
                    if row['organization']:
                        display_text += f" - {row['organization']}"
                    sender_options.append(display_text)
            
            # تحديد اختيار المرسل
            sender_display = current_sender
            if mail_data.get('sender_id'):
                contact_info = get_contact_by_id(mail_data['sender_id'])
                if contact_info:
                    sender_display = f"{contact_info['name']} - {contact_info.get('organization', '')}"
            
            sender_choice = st.selectbox(
                "المرسل *",
                options=sender_options,
                index=0,
                help="اختر المرسل من قائمة جهات الاتصال"
            )
            
            if sender_choice == "--- اختر من جهات الاتصال ---":
                sender_name = mail_data.get('sender_name', '')
                sender_id = mail_data.get('sender_id')
            else:
                # استخراج اسم المرسل من الاختيار
                sender_parts = sender_choice.split(' - ')
                sender_name = sender_parts[0]
                # البحث عن ID في قاعدة البيانات
                matched = contacts_df[contacts_df['name'] == sender_name]
                if not matched.empty:
                    sender_id = matched.iloc[0]['id']
                else:
                    sender_id = None
            
            subject = st.text_input("الموضوع *", value=mail_data.get('subject', ''))
        
        with col2:
            received_date = st.date_input("تاريخ الاستلام", 
                                        value=datetime.strptime(mail_data.get('received_date', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date())
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"], 
                                  index=["عادي", "مهم", "عاجل"].index(mail_data.get('priority', 'عادي')))
            status = st.selectbox("الحالة", ["جديد", "قيد المعالجة", "مكتمل", "ملغي"], 
                                index=["جديد", "قيد المعالجة", "مكتمل", "ملغي"].index(mail_data.get('status', 'جديد')))
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"], 
                                  index=["إداري", "مالي", "فني", "قانوني", "أخرى"].index(mail_data.get('category', 'إداري')))
        
        # تاريخ الاستحقاق
        due_date_val = mail_data.get('due_date')
        if due_date_val:
            try:
                due_date_val = datetime.strptime(due_date_val, '%Y-%m-%d').date()
            except:
                due_date_val = None
        
        col_due1, col_due2 = st.columns([1, 2])
        with col_due1:
            has_due_date = st.checkbox("تحديد تاريخ استحقاق", value=bool(due_date_val))
        
        with col_due2:
            if has_due_date:
                due_date = st.date_input("تاريخ الاستحقاق", value=due_date_val or (date.today() + timedelta(days=7)))
            else:
                due_date = None
        
        content = st.text_area("محتوى الرسالة", value=mail_data.get('content', ''), height=150)
        notes = st.text_area("ملاحظات إضافية", value=mail_data.get('notes', ''), height=100)
        
        # عرض المرفقات الحالية
        current_attachments = get_attachment_list(mail_data.get('attachments'))
        if current_attachments:
            st.markdown("#### 📎 المرفقات الحالية")
            for attachment in current_attachments:
                st.markdown(f"- {attachment}")
        
        # إضافة مرفقات جديدة
        st.markdown("#### 📎 إضافة مرفقات جديدة")
        uploaded_files = st.file_uploader(
            "إرفاق مستندات جديدة", 
            type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'],
            accept_multiple_files=True,
            help="يمكنك رفع أكثر من ملف"
        )
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            save_changes = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.edit_mail_id = None
                st.session_state.edit_mail_type = None
                st.rerun()
        
        if save_changes:
            if not sender_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    # حفظ المرفقات الجديدة
                    new_attachments = current_attachments.copy() if current_attachments else []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "incoming")
                            if filepath:
                                new_attachments.append(os.path.basename(filepath))
                    
                    # تحديث البريد الوارد
                    cursor.execute('''
                    UPDATE incoming_mail 
                    SET reference_no = ?, sender_id = ?, sender_name = ?, subject = ?, 
                        content = ?, received_date = ?, priority = ?, status = ?, 
                        category = ?, due_date = ?, attachments = ?, notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (
                        reference_no,
                        sender_id,
                        sender_name,
                        subject,
                        content,
                        received_date.strftime('%Y-%m-%d'),
                        priority,
                        status,
                        category,
                        due_date.strftime('%Y-%m-%d') if due_date else None,
                        json.dumps(new_attachments) if new_attachments else None,
                        notes,
                        mail_id
                    ))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تعديل بريد وارد", 
                               f"رقم المرجع: {reference_no}")
                    
                    st.success("✅ تم تحديث البريد الوارد بنجاح!")
                    
                    # تأخير لإظهار الرسالة ثم العودة
                    st.rerun()
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً لبريد آخر!")
                except Exception as e:
                    st.error(f"❌ خطأ في التحديث: {str(e)}")
                finally:
                    conn.close()

def edit_outgoing_mail(mail_id):
    """تعديل بريد صادر"""
    if not check_permission('edit'):
        st.warning("⚠️ ليس لديك صلاحية لتعديل البريد الصادر")
        st.session_state.edit_mail_id = None
        st.session_state.edit_mail_type = None
        st.rerun()
        return
    
    st.markdown('<div class="card"><h3>تعديل البريد الصادر</h3></div>', unsafe_allow_html=True)
    
    # جلب بيانات البريد
    mail_data = get_mail_by_id(mail_id, "outgoing")
    
    if not mail_data:
        st.error("❌ لم يتم العثور على البريد المطلوب")
        st.button("← العودة", on_click=lambda: [setattr(st.session_state, 'edit_mail_id', None), 
                                                 setattr(st.session_state, 'edit_mail_type', None), 
                                                 st.rerun()])
        return
    
    # جلب قائمة جهات الاتصال
    contacts_df = get_contacts()
    contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
    
    with st.form("edit_outgoing_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع *", value=mail_data.get('reference_no', ''))
            
            # تحديد المستلم الحالي
            current_recipient = mail_data.get('recipient_name', '')
            if current_recipient in contact_names:
                recipient_index = contact_names.index(current_recipient)
            else:
                recipient_index = 0
            
            recipient_choice = st.selectbox("المستلم *", contact_names, index=recipient_index)
            
            if recipient_choice == "--- اختر من جهات الاتصال ---":
                st.warning("الرجاء اختيار المستلم من القائمة")
                recipient_name = current_recipient
                recipient_id = mail_data.get('recipient_id')
            else:
                recipient_name = recipient_choice
                recipient_id = contacts_df[contacts_df['name'] == recipient_choice].iloc[0]['id'] if not contacts_df.empty else None
            
            subject = st.text_input("الموضوع *", value=mail_data.get('subject', ''))
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"], 
                                  index=["عادي", "مهم", "عاجل"].index(mail_data.get('priority', 'عادي')))
            status = st.selectbox("الحالة", ["مسودة", "مرسل", "مؤرشف"], 
                                index=["مسودة", "مرسل", "مؤرشف"].index(mail_data.get('status', 'مسودة')))
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"], 
                                  index=["إداري", "مالي", "فني", "قانوني", "أخرى"].index(mail_data.get('category', 'إداري')))
            
            sent_date_val = mail_data.get('sent_date', date.today().strftime('%Y-%m-%d'))
            sent_date = st.date_input("تاريخ الإرسال", 
                                     value=datetime.strptime(sent_date_val, '%Y-%m-%d').date())
        
        content = st.text_area("محتوى الرسالة", value=mail_data.get('content', ''), height=200)
        notes = st.text_area("ملاحظات إضافية", value=mail_data.get('notes', ''), height=100)
        
        # عرض المرفقات الحالية
        current_attachments = get_attachment_list(mail_data.get('attachments'))
        if current_attachments:
            st.markdown("#### 📎 المرفقات الحالية")
            for attachment in current_attachments:
                st.markdown(f"- {attachment}")
        
        # إضافة مرفقات جديدة
        st.markdown("#### 📎 إضافة مرفقات جديدة")
        uploaded_files = st.file_uploader(
            "إرفاق مستندات جديدة", 
            type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
            accept_multiple_files=True,
            help="يمكنك رفع أكثر من ملف"
        )
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            save_changes = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.edit_mail_id = None
                st.session_state.edit_mail_type = None
                st.rerun()
        
        if save_changes:
            if not recipient_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            elif recipient_choice == "--- اختر من جهات الاتصال ---":
                st.error("الرجاء اختيار المستلم من قائمة جهات الاتصال")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    # حفظ المرفقات الجديدة
                    new_attachments = current_attachments.copy() if current_attachments else []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "outgoing")
                            if filepath:
                                new_attachments.append(os.path.basename(filepath))
                    
                    # التحقق إذا تم تغيير الحالة إلى "مرسل" وإنشاء بوردرية
                    bordereau_filename = mail_data.get('bordereau')
                    if status == "مرسل" and mail_data.get('status') != "مرسل" and recipient_id:
                        # إنشاء بوردرية جديدة
                        contact_info = get_contact_by_id(recipient_id)
                        mail_context = {
                            'reference_no': reference_no,
                            'sent_date': sent_date.strftime('%Y-%m-%d'),
                            'recipient_name': recipient_name,
                            'subject': subject,
                            'notes': notes
                        }
                        
                        buffer = generate_bordereau_for_mail(mail_context, contact_info)
                        
                        if buffer:
                            upload_dir = "uploads/bordereau"
                            os.makedirs(upload_dir, exist_ok=True)
                            bordereau_filename = f"بوردرية_{reference_no}.docx"
                            bordereau_path = os.path.join(upload_dir, bordereau_filename)
                            
                            with open(bordereau_path, "wb") as f:
                                f.write(buffer.getvalue())
                            st.success("✅ تم إنشاء بوردرية جديدة!")
                    
                    # تحديث البريد الصادر
                    cursor.execute('''
                    UPDATE outgoing_mail 
                    SET reference_no = ?, recipient_id = ?, recipient_name = ?, subject = ?, 
                        content = ?, priority = ?, status = ?, sent_date = ?, 
                        category = ?, attachments = ?, bordereau = ?, notes = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''', (
                        reference_no,
                        recipient_id,
                        recipient_name,
                        subject,
                        content,
                        priority,
                        status,
                        sent_date.strftime('%Y-%m-%d'),
                        category,
                        json.dumps(new_attachments) if new_attachments else None,
                        bordereau_filename,
                        notes,
                        mail_id
                    ))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تعديل بريد صادر", 
                               f"رقم المرجع: {reference_no}")
                    
                    st.success("✅ تم تحديث البريد الصادر بنجاح!")
                    st.rerun()
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً لبريد آخر!")
                except Exception as e:
                    st.error(f"❌ خطأ في التحديث: {str(e)}")
                finally:
                    conn.close()

def view_mail_details(mail_id, mail_type):
    """عرض تفاصيل البريد"""
    st.markdown('<div class="card"><h3>تفاصيل البريد</h3></div>', unsafe_allow_html=True)
    
    # جلب بيانات البريد
    mail_data = get_mail_by_id(mail_id, mail_type)
    
    if not mail_data:
        st.error("❌ لم يتم العثور على البريد المطلوب")
        st.button("← العودة", on_click=lambda: [setattr(st.session_state, 'view_mail_id', None), 
                                                 setattr(st.session_state, 'view_mail_type', None), 
                                                 st.rerun()])
        return
    
    # زر العودة
    if st.button("← العودة"):
        st.session_state.view_mail_id = None
        st.session_state.view_mail_type = None
        st.rerun()
    
    if mail_type == "incoming":
        display_incoming_details(mail_data)
    else:
        display_outgoing_details(mail_data)
    
    # زر التعديل (إذا كان لدى المستخدم الصلاحية)
    if check_permission('edit'):
        if st.button("✏️ تعديل", use_container_width=True):
            st.session_state.edit_mail_id = mail_id
            st.session_state.edit_mail_type = mail_type
            st.session_state.view_mail_id = None
            st.session_state.view_mail_type = None
            st.rerun()

def display_incoming_details(mail_data):
    """عرض تفاصيل البريد الوارد"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### المعلومات الأساسية")
        st.markdown(f"**رقم المرجع:** {mail_data.get('reference_no', 'غير محدد')}")
        st.markdown(f"**المرسل:** {mail_data.get('sender_name', 'غير محدد')}")
        st.markdown(f"**الموضوع:** {mail_data.get('subject', 'غير محدد')}")
        st.markdown(f"**تاريخ الاستلام:** {mail_data.get('received_date', 'غير محدد')}")
        
        if mail_data.get('due_date'):
            st.markdown(f"**تاريخ الاستحقاق:** {mail_data.get('due_date')}")
            try:
                due_date = datetime.strptime(mail_data['due_date'], '%Y-%m-%d').date()
                days_left = (due_date - date.today()).days
                if days_left < 0:
                    st.error(f"⏰ تجاوز تاريخ الاستحقاق ب {abs(days_left)} يوم")
                elif days_left <= 3:
                    st.warning(f"⏰ متبقي {days_left} يوم للاستحقاق")
            except:
                pass
    
    with col2:
        st.markdown("### المعلومات الإضافية")
        st.markdown(f"**الأولوية:** {mail_data.get('priority', 'غير محدد')}")
        st.markdown(f"**الحالة:** {mail_data.get('status', 'غير محدد')}")
        st.markdown(f"**التصنيف:** {mail_data.get('category', 'غير محدد')}")
        st.markdown(f"**مسجل بواسطة:** {mail_data.get('recorded_by', 'غير محدد')}")
    
    # المحتوى
    st.markdown("### محتوى الرسالة")
    st.markdown(f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>{mail_data.get('content', 'لا يوجد محتوى')}</div>", 
                unsafe_allow_html=True)
    
    if mail_data.get('notes'):
        st.markdown("### ملاحظات إضافية")
        st.markdown(f"<div style='background-color: #fff3cd; padding: 15px; border-radius: 5px;'>{mail_data.get('notes')}</div>", 
                    unsafe_allow_html=True)
    
    # المرفقات
    attachments = get_attachment_list(mail_data.get('attachments'))
    if attachments:
        st.markdown("### 📎 المرفقات")
        for attachment in attachments:
            st.markdown(f"- {attachment}")

def display_outgoing_details(mail_data):
    """عرض تفاصيل البريد الصادر"""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### المعلومات الأساسية")
        st.markdown(f"**رقم المرجع:** {mail_data.get('reference_no', 'غير محدد')}")
        st.markdown(f"**المستلم:** {mail_data.get('recipient_name', 'غير محدد')}")
        st.markdown(f"**الموضوع:** {mail_data.get('subject', 'غير محدد')}")
        st.markdown(f"**تاريخ الإرسال:** {mail_data.get('sent_date', 'غير محدد')}")
    
    with col2:
        st.markdown("### المعلومات الإضافية")
        st.markdown(f"**الأولوية:** {mail_data.get('priority', 'غير محدد')}")
        st.markdown(f"**الحالة:** {mail_data.get('status', 'غير محدد')}")
        st.markdown(f"**التصنيف:** {mail_data.get('category', 'غير محدد')}")
        st.markdown(f"**مرسل بواسطة:** {mail_data.get('sent_by', 'غير محدد')}")
    
    # المحتوى
    st.markdown("### محتوى الرسالة")
    st.markdown(f"<div style='background-color: #f8f9fa; padding: 15px; border-radius: 5px;'>{mail_data.get('content', 'لا يوجد محتوى')}</div>", 
                unsafe_allow_html=True)
    
    if mail_data.get('notes'):
        st.markdown("### ملاحظات إضافية")
        st.markdown(f"<div style='background-color: #fff3cd; padding: 15px; border-radius: 5px;'>{mail_data.get('notes')}</div>", 
                    unsafe_allow_html=True)
    
    # المرفقات
    attachments = get_attachment_list(mail_data.get('attachments'))
    if attachments:
        st.markdown("### 📎 المرفقات")
        for attachment in attachments:
            st.markdown(f"- {attachment}")
    
    # البوردرية
    if mail_data.get('bordereau'):
        st.markdown("### 📄 البوردرية")
        bordereau_path = f"uploads/bordereau/{mail_data['bordereau']}"
        if os.path.exists(bordereau_path):
            with open(bordereau_path, "rb") as f:
                bordereau_bytes = f.read()
            
            st.download_button(
                label="📥 تحميل البوردرية",
                data=bordereau_bytes,
                file_name=mail_data['bordereau'],
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        else:
            st.warning("ملف البوردرية غير موجود")

# --- وظيفة إنشاء البوردرية من صفحة مخصصة ---
def display_bordereau_generator():
    """عرض واجهة إنشاء البوردرية"""
    st.markdown('<div class="card"><h3>إنشاء بوردرية</h3></div>', unsafe_allow_html=True)
    
    # خيارات إنشاء البوردرية
    create_option = st.radio(
        "اختر طريقة إنشاء البوردرية:",
        ["إنشاء بوردرية جديدة", "إنشاء بوردرية من بريد صادر موجود"]
    )
    
    if create_option == "إنشاء بوردرية جديدة":
        create_new_bordereau()
    else:
        create_bordereau_from_existing_mail()

def create_new_bordereau():
    """إنشاء بوردرية جديدة من البيانات المدخلة"""
    st.markdown("### إنشاء بوردرية جديدة")
    
    with st.form("new_bordereau_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع *", placeholder="مثال: ص-0001-01-2024")
            sent_date = st.date_input("تاريخ الإرسال *", value=date.today())
            recipient_name = st.text_input("اسم المستلم *", placeholder="الاسم الكامل")
            organization = st.text_input("المؤسسة", placeholder="اسم المؤسسة")
        
        with col2:
            phone = st.text_input("الهاتف", placeholder="رقم الهاتف")
            email = st.text_input("البريد الإلكتروني", placeholder="example@domain.com")
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
        
        notes = st.text_area("ملاحظات", height=100, placeholder="ملاحظات إضافية...")
        
        submitted = st.form_submit_button("📄 إنشاء البوردرية", use_container_width=True)
        
        if submitted:
            if not reference_no or not recipient_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                # تحضير البيانات
                mail_data = {
                    'reference_no': reference_no,
                    'sent_date': sent_date.strftime('%Y-%m-%d'),
                    'recipient_name': recipient_name,
                    'subject': subject,
                    'notes': notes
                }
                
                contact_info = {
                    'organization': organization,
                    'phone': phone,
                    'email': email
                }
                
                # إنشاء البوردرية
                buffer = generate_bordereau_for_mail(mail_data, contact_info)
                
                if buffer:
                    st.session_state.bordereau_buffer = buffer
                    st.session_state.bordereau_data = {
                        'reference_no': reference_no,
                        'filename': f"بوردرية_{reference_no}.docx"
                    }
                    
                    st.success("✅ تم إنشاء البوردرية بنجاح!")
                    
                    # عرض زر التحميل
                    st.download_button(
                        label="📥 تحميل البوردرية",
                        data=buffer.getvalue(),
                        file_name=f"بوردرية_{reference_no}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                    
                    # زر حفظ في النظام
                    if st.button("💾 حفظ البوردرية في النظام", use_container_width=True):
                        save_bordereau_to_system(reference_no, buffer)

def create_bordereau_from_existing_mail():
    """إنشاء بوردرية من بريد صادر موجود"""
    st.markdown("### إنشاء بوردرية من بريد صادر")
    
    # جلب البريد الصادر
    conn = get_db_connection()
    try:
        outgoing_df = pd.read_sql("""
            SELECT id, reference_no, recipient_name, subject, sent_date, status
            FROM outgoing_mail 
            WHERE status IN ('مسودة', 'مرسل')
            ORDER BY sent_date DESC
        """, conn)
    except:
        outgoing_df = pd.DataFrame()
    finally:
        conn.close()
    
    if not outgoing_df.empty:
        # اختيار البريد
        mail_options = []
        for _, row in outgoing_df.iterrows():
            display_text = f"{row['reference_no']} - {row['recipient_name']} - {row['subject']}"
            if len(display_text) > 80:
                display_text = display_text[:77] + "..."
            mail_options.append((row['id'], display_text))
        
        selected_mail_display = st.selectbox(
            "اختر بريداً صادراً",
            options=[display for _, display in mail_options],
            format_func=lambda x: x
        )
        
        if selected_mail_display:
            # الحصول على ID المحدد
            selected_id = None
            for mail_id, display in mail_options:
                if display == selected_mail_display:
                    selected_id = mail_id
                    break
            
            if selected_id:
                mail_data = get_mail_by_id(selected_id, "outgoing")
                
                if mail_data:
                    st.markdown("#### معلومات البريد المحدد")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info(f"**رقم المرجع:** {mail_data.get('reference_no')}")
                        st.info(f"**المستلم:** {mail_data.get('recipient_name')}")
                        st.info(f"**الموضوع:** {mail_data.get('subject')}")
                    
                    with col2:
                        st.info(f"**تاريخ الإرسال:** {mail_data.get('sent_date')}")
                        st.info(f"**الحالة:** {mail_data.get('status')}")
                    
                    # جلب معلومات جهة الاتصال
                    contact_info = None
                    if mail_data.get('recipient_id'):
                        contact_info = get_contact_by_id(mail_data['recipient_id'])
                    
                    if st.button("📄 إنشاء بوردرية", use_container_width=True):
                        buffer = generate_bordereau_for_mail(mail_data, contact_info)
                        
                        if buffer:
                            st.session_state.bordereau_buffer = buffer
                            st.session_state.bordereau_data = {
                                'reference_no': mail_data.get('reference_no'),
                                'filename': f"بوردرية_{mail_data.get('reference_no')}.docx"
                            }
                            
                            st.success("✅ تم إنشاء البوردرية بنجاح!")
                            
                            # عرض زر التحميل
                            st.download_button(
                                label="📥 تحميل البوردرية",
                                data=buffer.getvalue(),
                                file_name=f"بوردرية_{mail_data.get('reference_no')}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                use_container_width=True
                            )
                            
                            # تحديث البريد الصادر بملف البوردرية
                            if st.button("💾 تحديث البريد بالبوردرية", use_container_width=True):
                                conn = get_db_connection()
                                cursor = conn.cursor()
                                
                                bordereau_filename = f"بوردرية_{mail_data.get('reference_no')}.docx"
                                upload_dir = "uploads/bordereau"
                                os.makedirs(upload_dir, exist_ok=True)
                                bordereau_path = os.path.join(upload_dir, bordereau_filename)
                                
                                with open(bordereau_path, "wb") as f:
                                    f.write(buffer.getvalue())
                                
                                cursor.execute('''
                                UPDATE outgoing_mail 
                                SET bordereau = ?
                                WHERE id = ?
                                ''', (bordereau_filename, selected_id))
                                
                                conn.commit()
                                conn.close()
                                
                                log_activity(st.session_state.user['id'], "إضافة بوردرية", 
                                           f"للبريد الصادر: {mail_data.get('reference_no')}")
                                
                                st.success("✅ تم تحديث البريد بملف البوردرية!")
                else:
                    st.warning("❌ لم يتم العثور على بيانات البريد المحدد")
    else:
        st.info("📭 لا توجد بريد صادر متاح لإنشاء بوردرية")

def save_bordereau_to_system(reference_no, buffer):
    """حفظ البوردرية في النظام"""
    upload_dir = "uploads/bordereau"
    os.makedirs(upload_dir, exist_ok=True)
    
    filename = f"بوردرية_{reference_no}.docx"
    filepath = os.path.join(upload_dir, filename)
    
    try:
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())
        
        log_activity(st.session_state.user['id'], "حفظ بوردرية", 
                   f"البوردرية: {filename}")
        
        st.success(f"✅ تم حفظ البوردرية في: {filepath}")
    except Exception as e:
        st.error(f"❌ خطأ في حفظ البوردرية: {str(e)}")

def show_incoming_stats():
    """عرض إحصائيات البريد الوارد"""
    conn = get_db_connection()
    
    try:
        # إحصائيات حسب الحالة
        status_stats = pd.read_sql("""
            SELECT status as 'الحالة', COUNT(*) as 'العدد'
            FROM incoming_mail
            GROUP BY status
            ORDER BY COUNT(*) DESC
        """, conn)
        
        # إحصائيات حسب الأولوية
        priority_stats = pd.read_sql("""
            SELECT priority as 'الأولوية', COUNT(*) as 'العدد'
            FROM incoming_mail
            GROUP BY priority
            ORDER BY COUNT(*) DESC
        """, conn)
        
        # إحصائيات حسب التصنيف
        category_stats = pd.read_sql("""
            SELECT category as 'التصنيف', COUNT(*) as 'العدد'
            FROM incoming_mail
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """, conn)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("##### حسب الحالة")
            st.dataframe(status_stats, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("##### حسب الأولوية")
            st.dataframe(priority_stats, use_container_width=True, hide_index=True)
        
        with col3:
            st.markdown("##### حسب التصنيف")
            st.dataframe(category_stats, use_container_width=True, hide_index=True)
        
        # إحصائيات شهرية
        monthly_stats = pd.read_sql("""
            SELECT strftime('%Y-%m', received_date) as 'الشهر', COUNT(*) as 'عدد الرسائل'
            FROM incoming_mail
            GROUP BY strftime('%Y-%m', received_date)
            ORDER BY strftime('%Y-%m', received_date) DESC
            LIMIT 6
        """, conn)
        
        if not monthly_stats.empty:
            st.markdown("##### الإحصائيات الشهرية (آخر 6 أشهر)")
            st.dataframe(monthly_stats, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"خطأ في جلب الإحصائيات: {str(e)}")
    finally:
        conn.close()

# --- وظائف تصدير إلى Excel ---
def export_incoming_to_excel():
    """تصدير البريد الوارد إلى Excel"""
    if not check_permission('export'):
        return None
    
    conn = get_db_connection()
    
    query = """
    SELECT 
        reference_no as 'رقم المرجع',
        sender_name as 'المرسل',
        received_date as 'تاريخ الاستلام',
        subject as 'الموضوع',
        priority as 'الأولوية',
        status as 'الحالة',
        category as 'التصنيف',
        due_date as 'تاريخ الاستحقاق',
        notes as 'ملاحظات'
    FROM incoming_mail
    ORDER BY received_date DESC
    """
    
    try:
        df = pd.read_sql(query, conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    
    if not df.empty:
        # إنشاء ملف Excel في الذاكرة
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='البريد الوارد')
            
            # تحسين عرض الأعمدة
            worksheet = writer.sheets['البريد الوارد']
            for idx, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(column_width, 50)
        
        output.seek(0)
        return output
    else:
        return None

def export_outgoing_to_excel():
    """تصدير البريد الصادر إلى Excel"""
    if not check_permission('export'):
        return None
    
    conn = get_db_connection()
    
    query = """
    SELECT 
        reference_no as 'رقم المرجع',
        recipient_name as 'المستلم',
        sent_date as 'تاريخ الإرسال',
        subject as 'الموضوع',
        priority as 'الأولوية',
        status as 'الحالة',
        category as 'التصنيف',
        notes as 'ملاحظات'
    FROM outgoing_mail
    ORDER BY sent_date DESC
    """
    
    try:
        df = pd.read_sql(query, conn)
    except:
        df = pd.DataFrame()
    finally:
        conn.close()
    
    if not df.empty:
        # إنشاء ملف Excel في الذاكرة
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='البريد الصادر')
            
            # تحسين عرض الأعمدة
            worksheet = writer.sheets['البريد الصادر']
            for idx, col in enumerate(df.columns):
                column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(column_width, 50)
        
        output.seek(0)
        return output
    else:
        return None

# --- شاشة تسجيل الدخول ---
def login_screen():
    """عرض واجهة تسجيل الدخول"""
    st.markdown("""
    <style>
    .login-container {
        max-width: 500px;
        margin: 100px auto;
        padding: 30px;
        border-radius: 10px;
        background-color: #f8f9fa;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .institution-title {
        font-size: 24px;
        font-weight: bold;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 10px;
    }
    .system-title {
        font-size: 20px;
        color: #3498db;
        text-align: center;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="institution-title">المدرسة الإعدادية حي الأمل   </div>', unsafe_allow_html=True)
        st.markdown('<div class="system-title">مكتب الضبط  </div>', unsafe_allow_html=True)
        
        st.markdown('<p style="text-align: center; color: #666; margin-bottom: 30px;">الرجاء تسجيل الدخول للوصول إلى النظام</p>', unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("اسم المستخدم", placeholder="أدخل اسم المستخدم")
            password = st.text_input("كلمة المرور", type="password", placeholder="أدخل كلمة المرور")
            submit = st.form_submit_button("تسجيل الدخول", use_container_width=True)
            
            if submit:
                if authenticate_user(username, password):
                    st.success(f"مرحباً {st.session_state.user['full_name']}!")
                    st.rerun()
                else:
                    st.error("اسم المستخدم أو كلمة المرور غير صحيحة")

# --- واجهة إدارة المستخدمين ---
def display_user_management():
    """عرض واجهة إدارة المستخدمين"""
    st.markdown('<div class="card"><h3>إدارة المستخدمين</h3></div>', unsafe_allow_html=True)
    
    if not check_permission('manage_users'):
        st.warning("⚠️ ليس لديك الصلاحية للوصول إلى إدارة المستخدمين")
        return
    
    # أزرار التنقل بين أنماط الإدارة
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("👁️ عرض المستخدمين", use_container_width=True, key="view_users_btn"):
            st.session_state.manage_users_mode = "view"
            st.rerun()
    
    with col2:
        if st.button("➕ إضافة مستخدم جديد", use_container_width=True, key="add_user_btn"):
            st.session_state.manage_users_mode = "add"
            st.rerun()
    
    with col3:
        if st.button("🔐 تغيير كلمة المرور", use_container_width=True, key="change_pass_btn"):
            st.session_state.manage_users_mode = "change_password"
            st.rerun()
    
    st.markdown("---")
    
    # عرض المحتوى حسب النمط المختار
    if st.session_state.manage_users_mode == "view":
        display_users_list()
    elif st.session_state.manage_users_mode == "add":
        display_add_user_form()
    elif st.session_state.manage_users_mode == "change_password":
        display_change_password_form()

def display_users_list():
    """عرض قائمة المستخدمين"""
    st.markdown("### قائمة المستخدمين")
    
    users_df = get_all_users()
    
    if not users_df.empty:
        # إضافة أعمدة عرض
        users_df['الحالة'] = users_df['is_active'].apply(lambda x: '✅ نشط' if x == 1 else '❌ غير نشط')
        
        # البحث والتصفية
        search_col1, search_col2, search_col3 = st.columns(3)
        
        with search_col1:
            search_name = st.text_input("🔍 البحث بالاسم")
        
        with search_col2:
            search_username = st.text_input("🔍 البحث باسم المستخدم")
        
        with search_col3:
            search_role = st.selectbox("🔍 التصفية بالدور", ["الكل", "مشرف", "مستخدم", "مستشار"])
        
        # تطبيق البحث والتصفية
        filtered_df = users_df.copy()
        
        if search_name:
            filtered_df = filtered_df[filtered_df['full_name'].str.contains(search_name, case=False, na=False)]
        
        if search_username:
            filtered_df = filtered_df[filtered_df['username'].str.contains(search_username, case=False, na=False)]
        
        if search_role != "الكل":
            filtered_df = filtered_df[filtered_df['role_display'] == search_role]
        
        # عرض البيانات
        display_cols = ['username', 'full_name', 'email', 'role_display', 'الحالة', 'created_at']
        
        if not filtered_df.empty:
            st.dataframe(
                filtered_df[display_cols].rename(columns={
                    'username': 'اسم المستخدم',
                    'full_name': 'الاسم الكامل',
                    'email': 'البريد الإلكتروني',
                    'role_display': 'الدور',
                    'created_at': 'تاريخ الإنشاء'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # خيارات إدارة لكل مستخدم
            st.markdown("### إدارة المستخدم المحدد")
            
            selected_user = st.selectbox(
                "اختر مستخدم لإدارته",
                filtered_df['full_name'].tolist()
            )
            
            if selected_user:
                user_data = filtered_df[filtered_df['full_name'] == selected_user].iloc[0]
                
                col_edit, col_reset, col_delete = st.columns(3)
                
                with col_edit:
                    if st.button("✏️ تعديل البيانات", use_container_width=True, key=f"edit_{user_data['id']}"):
                        display_edit_user_form(user_data)
                
                with col_reset:
                    if st.button("🔄 إعادة تعيين كلمة المرور", use_container_width=True, key=f"reset_{user_data['id']}"):
                        success, result = reset_user_password(user_data['id'])
                        if success:
                            st.success(f"✅ تم إعادة تعيين كلمة المرور بنجاح!")
                            st.info(f"**كلمة المرور الجديدة:** {result}")
                            st.warning("⚠️ الرجاء إبلاغ المستخدم بكلمة المرور الجديدة")
                        else:
                            st.error(result)
                
                with col_delete:
                    if st.button("🗑️ حذف المستخدم", use_container_width=True, key=f"delete_{user_data['id']}"):
                        if st.checkbox(f"⚠️ تأكيد حذف المستخدم: {selected_user}"):
                            success, message = delete_user(user_data['id'])
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            
            # إحصائيات
            st.markdown("---")
            col_stats1, col_stats2, col_stats3 = st.columns(3)
            
            with col_stats1:
                active_count = users_df['is_active'].sum()
                st.metric("المستخدمين النشطين", active_count)
            
            with col_stats2:
                admin_count = len(users_df[users_df['role'] == 'admin'])
                st.metric("المشرفين", admin_count)
            
            with col_stats3:
                viewer_count = len(users_df[users_df['role'] == 'viewer'])
                st.metric("المستشارين", viewer_count)
        
        else:
            st.info("لم يتم العثور على مستخدمين مطابقين للبحث")
    
    else:
        st.info("لا توجد مستخدمين مسجلين في النظام")

def display_add_user_form():
    """عرض نموذج إضافة مستخدم جديد"""
    st.markdown("### إضافة مستخدم جديد")
    
    with st.form("add_user_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            username = st.text_input("اسم المستخدم *", placeholder="يجب أن يكون فريداً")
            full_name = st.text_input("الاسم الكامل *", placeholder="الاسم الثلاثي")
            email = st.text_input("البريد الإلكتروني", placeholder="example@domain.com")
        
        with col2:
            role = st.selectbox("الدور *", ["admin", "user", "viewer"], 
                              format_func=lambda x: {
                                  'admin': 'مشرف (صلاحيات كاملة)',
                                  'user': 'مستخدم (يمكنه الإضافة والتعديل)',
                                  'viewer': 'مستشار (يمكنه الاستعلام فقط)'
                              }[x])
            
            password_option = st.radio("خيارات كلمة المرور", 
                                      ["توليد كلمة مرور تلقائياً", "تحديد كلمة مرور يدوياً"])
            
            if password_option == "تحديد كلمة مرور يدوياً":
                custom_password = st.text_input("كلمة المرور المخصصة", type="password")
            else:
                custom_password = None
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("💾 إضافة المستخدم", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.manage_users_mode = "view"
                st.rerun()
        
        if submitted:
            if not username or not full_name:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                success, result = create_user(username, full_name, email, role, custom_password)
                
                if success:
                    st.success(f"✅ تم إنشاء المستخدم {full_name} بنجاح!")
                    
                    if not custom_password:
                        st.info(f"**تم توليد كلمة المرور تلقائياً:** {result}")
                        st.warning("⚠️ الرجاء إبلاغ المستخدم بكلمة المرور الجديدة")
                    
                    # إعادة تعيين النموذج
                    st.session_state.manage_users_mode = "view"
                    st.rerun()
                else:
                    st.error(f"❌ {result}")

def display_edit_user_form(user_data):
    """عرض نموذج تعديل بيانات المستخدم"""
    st.markdown(f"### تعديل بيانات المستخدم: {user_data['full_name']}")
    
    with st.form("edit_user_form"):
        full_name = st.text_input("الاسم الكامل *", value=user_data['full_name'])
        email = st.text_input("البريد الإلكتروني", value=user_data['email'])
        
        # للتحقق من صلاحيات التعديل
        can_change_role = check_permission('manage_users')
        
        if can_change_role:
            role = st.selectbox("الدور *", ["admin", "user", "viewer"], 
                              index=["admin", "user", "viewer"].index(user_data['role']),
                              format_func=lambda x: {
                                  'admin': 'مشرف (صلاحيات كاملة)',
                                  'user': 'مستخدم (يمكنه الإضافة والتعديل)',
                                  'viewer': 'مستشار (يمكنه الاستعلام فقط)'
                              }[x])
        else:
            role = user_data['role']
            st.info(f"الدور: {user_data['role_display']} (لا يمكن تغيير الدور)")
        
        is_active = st.checkbox("المستخدم نشط", value=bool(user_data['is_active']))
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.rerun()
        
        if submitted:
            if not full_name:
                st.error("الرجاء إدخال الاسم الكامل")
            else:
                success, message = update_user(
                    user_data['id'],
                    full_name=full_name,
                    email=email,
                    role=role if can_change_role else None,
                    is_active=is_active
                )
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

def display_change_password_form():
    """عرض نموذج تغيير كلمة مرور المستخدم الحالي"""
    st.markdown("### تغيير كلمة المرور")
    
    with st.form("change_password_form"):
        st.markdown("#### تغيير كلمة مرورك الخاصة")
        
        old_password = st.text_input("كلمة المرور الحالية *", type="password")
        new_password = st.text_input("كلمة المرور الجديدة *", type="password")
        confirm_password = st.text_input("تأكيد كلمة المرور الجديدة *", type="password")
        
        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("🔄 تغيير كلمة المرور", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.manage_users_mode = "view"
                st.rerun()
        
        if submitted:
            if not old_password or not new_password or not confirm_password:
                st.error("الرجاء ملء جميع الحقول")
            elif new_password != confirm_password:
                st.error("كلمتا المرور غير متطابقتين")
            elif len(new_password) < 6:
                st.error("كلمة المرور يجب أن تكون 6 أحرف على الأقل")
            else:
                success, message = change_own_password(old_password, new_password)
                
                if success:
                    st.success(message)
                    st.session_state.manage_users_mode = "view"
                    st.rerun()
                else:
                    st.error(message)

# --- وظائف عرض الصفحات (المحدثة مع الصلاحيات) ---
def display_dashboard():
    """عرض لوحة القيادة"""
    conn = get_db_connection()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        try:
            new_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status = 'جديد'", conn).iloc[0,0]
            st.metric("بريد وارد جديد", new_mail)
        except:
            st.metric("بريد وارد جديد", 0)
    
    with col2:
        try:
            pending_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status = 'قيد المعالجة'", conn).iloc[0,0]
            st.metric("قيد المعالجة", pending_mail)
        except:
            st.metric("قيد المعالجة", 0)
    
    with col3:
        try:
            total_contacts = pd.read_sql("SELECT COUNT(*) FROM contacts", conn).iloc[0,0]
            st.metric("جهات اتصال", total_contacts)
        except:
            st.metric("جهات اتصال", 0)
    
    with col4:
        try:
            total_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail", conn).iloc[0,0]
            st.metric("إجمالي البريد", total_mail)
        except:
            st.metric("إجمالي البريد", 0)
    
    # البريد القريب من تاريخ الاستحقاق
    st.markdown("### البريد القريب من تاريخ الاستحقاق")
    today = date.today()
    next_week = today + timedelta(days=7)
    
    try:
        due_mail = pd.read_sql('''
        SELECT reference_no, sender_name, subject, received_date, due_date, status 
        FROM incoming_mail 
        WHERE due_date IS NOT NULL 
        AND due_date BETWEEN ? AND ?
        AND status NOT IN ('مكتمل', 'ملغي')
        ORDER BY due_date
        ''', conn, params=(today.strftime('%Y-%m-%d'), next_week.strftime('%Y-%m-%d')))
        
        if not due_mail.empty:
            st.dataframe(due_mail, use_container_width=True, hide_index=True)
        else:
            st.info("لا يوجد بريد قريب من تاريخ الاستحقاق")
    except:
        st.info("لا يوجد بريد قريب من تاريخ الاستحقاق")
    
    # آخر البريد الوارد
    st.markdown("### آخر البريد الوارد")
    try:
        recent_mail = pd.read_sql('''
        SELECT reference_no, sender_name, subject, received_date, priority, status 
        FROM incoming_mail 
        ORDER BY received_date DESC LIMIT 10
        ''', conn)
        
        if not recent_mail.empty:
            st.dataframe(recent_mail, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد رسائل واردة حالياً")
    except:
        st.info("لا توجد رسائل واردة حالياً")
    
    conn.close()

def display_incoming_mail():
    """عرض البريد الوارد"""
    if not check_permission('view'):
        st.warning("⚠️ ليس لديك صلاحية لعرض البريد الوارد")
        return
    
    conn = get_db_connection()
    
    st.markdown('<div class="card"><h3>إدارة البريد الوارد</h3></div>', unsafe_allow_html=True)
    
    # أزرار التصفية
    col_filters = st.columns([2, 1, 1, 1, 1, 1, 1])
    filters = ["الكل", "جديد", "قيد المعالجة", "مكتمل", "مهم", "عاجل", "قريب من الاستحقاق"]
    
    for i, filter_name in enumerate(filters):
        with col_filters[i]:
            if st.button(filter_name, key=f"filter_{filter_name}", use_container_width=True):
                st.session_state.mail_filter = filter_name
    
    # أزرار التصدير والإحصائيات
    col_export, col_stats = st.columns([1, 1])
    with col_export:
        if st.button("📊 إحصائيات", use_container_width=True):
            show_incoming_stats()
    
    with col_stats:
        if check_permission('export'):
            excel_data = export_incoming_to_excel()
            if excel_data:
                st.download_button(
                    label="📥 تصدير إلى Excel",
                    data=excel_data,
                    file_name=f"البريد_الوارد_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
    
    # تطبيق التصفية
    if st.session_state.mail_filter == "الكل":
        query = "SELECT * FROM incoming_mail ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "جديد":
        query = "SELECT * FROM incoming_mail WHERE status = 'جديد' ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "قيد المعالجة":
        query = "SELECT * FROM incoming_mail WHERE status = 'قيد المعالجة' ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "مكتمل":
        query = "SELECT * FROM incoming_mail WHERE status = 'مكتمل' ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "مهم":
        query = "SELECT * FROM incoming_mail WHERE priority = 'مهم' ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "عاجل":
        query = "SELECT * FROM incoming_mail WHERE priority = 'عاجل' ORDER BY received_date DESC"
    elif st.session_state.mail_filter == "قريب من الاستحقاق":
        today = date.today()
        next_week = today + timedelta(days=7)
        query = f"""
        SELECT * FROM incoming_mail 
        WHERE due_date IS NOT NULL 
        AND due_date BETWEEN '{today}' AND '{next_week}'
        AND status NOT IN ('مكتمل', 'ملغي')
        ORDER BY due_date
        """
    
    try:
        df = pd.read_sql(query, conn)
    except:
        df = pd.DataFrame()
    
    if not df.empty:
        # البحث
        search_col1, search_col2, search_col3 = st.columns(3)
        with search_col1:
            search_ref = st.text_input("🔍 البحث برقم المرجع")
        with search_col2:
            search_sender = st.text_input("🔍 البحث بالمرسل")
        with search_col3:
            search_subject = st.text_input("🔍 البحث بالموضوع")
        
        if search_ref:
            df = df[df['reference_no'].str.contains(search_ref, case=False, na=False)]
        if search_sender:
            df = df[df['sender_name'].str.contains(search_sender, case=False, na=False)]
        if search_subject:
            df = df[df['subject'].str.contains(search_subject, case=False, na=False)]
        
        # عرض البيانات
        for idx, row in df.iterrows():
            with st.container():
                col_info, col_actions = st.columns([4, 1])
                
                with col_info:
                    # بطاقة عرض مختصرة
                    st.markdown(f"""
                    <div class="mail-card">
                        <div class="mail-header">
                            <span class="mail-ref">{row['reference_no']}</span>
                            <span class="mail-priority {row['priority']}">{row['priority']}</span>
                            <span class="mail-status {row['status']}">{row['status']}</span>
                        </div>
                        <div class="mail-body">
                            <strong>{row['subject']}</strong><br>
                            <small>المرسل: {row['sender_name']} | التاريخ: {row['received_date']}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # عرض تاريخ الاستحقاق إذا كان موجوداً
                    if row['due_date']:
                        try:
                            due_date = datetime.strptime(row['due_date'], '%Y-%m-%d').date()
                            days_left = (due_date - date.today()).days
                            if days_left < 0:
                                st.error(f"⏰ تجاوز تاريخ الاستحقاق ب {abs(days_left)} يوم")
                            elif days_left <= 3:
                                st.warning(f"⏰ تاريخ الاستحقاق: {row['due_date']} (متبقي {days_left} يوم)")
                            else:
                                st.info(f"⏰ تاريخ الاستحقاق: {row['due_date']} (متبقي {days_left} يوم)")
                        except:
                            pass
                
                with col_actions:
                    # أزرار الإجراءات
                    col_view, col_edit, col_delete = st.columns(3)
                    
                    with col_view:
                        if st.button("👁️", key=f"view_{row['id']}", help="عرض التفاصيل"):
                            st.session_state.view_mail_id = row['id']
                            st.session_state.view_mail_type = "incoming"
                            st.rerun()
                    
                    with col_edit:
                        if check_permission('edit'):
                            if st.button("✏️", key=f"edit_{row['id']}", help="تعديل"):
                                st.session_state.edit_mail_id = row['id']
                                st.session_state.edit_mail_type = "incoming"
                                st.rerun()
                        else:
                            st.button("✏️", key=f"edit_{row['id']}", help="تعديل", disabled=True)
                    
                    with col_delete:
                        if check_permission('delete'):
                            if st.button("🗑️", key=f"delete_{row['id']}", help="حذف"):
                                if st.button(f"⚠️ تأكيد حذف {row['reference_no']}", key=f"confirm_delete_{row['id']}"):
                                    cursor = conn.cursor()
                                    cursor.execute("DELETE FROM incoming_mail WHERE id = ?", (row['id'],))
                                    conn.commit()
                                    log_activity(st.session_state.user['id'], "حذف بريد وارد", 
                                               f"{row['reference_no']}")
                                    st.success("تم حذف البريد الوارد")
                                    st.rerun()
                        else:
                            st.button("🗑️", key=f"delete_{row['id']}", help="حذف", disabled=True)
                
                st.divider()
        
        # عرض ملخص
        st.markdown(f"**عدد النتائج:** {len(df)} بريد")
        
    else:
        st.info("لا توجد رسائل واردة")
    
    conn.close()

def register_incoming_mail():
    """تسجيل بريد وارد جديد"""
    if not check_permission('add'):
        st.warning("⚠️ ليس لديك صلاحية لتسجيل بريد وارد جديد")
        return
    
    st.markdown('<div class="card"><h3>تسجيل بريد وارد جديد</h3></div>', unsafe_allow_html=True)
    
    # جلب قائمة جهات الاتصال
    contacts_df = get_contacts()
    
    # تحضير قائمة جهات الاتصال للـ selectbox
    if not contacts_df.empty:
        # إنشاء قائمة بعرض أكثر تفصيلاً
        contact_options = ["--- اختر من جهات الاتصال ---"]
        contact_display = []
        
        for _, row in contacts_df.iterrows():
            display_text = f"{row['name']}"
            if row['organization']:
                display_text += f" - {row['organization']}"
            contact_display.append(display_text)
            contact_options.append(display_text)
    else:
        contact_display = []
        contact_options = ["--- لا توجد جهات اتصال مسجلة ---"]
    
    with st.form("incoming_mail_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no("incoming"))
            
            # استخدام selectbox بدلاً من text input
            contact_choice = st.selectbox(
                "المرسل *", 
                options=contact_options,
                help="اختر المرسل من قائمة جهات الاتصال المسجلة"
            )
            
            # استخراج اسم المرسل من الاختيار
            if contact_choice == "--- اختر من جهات الاتصال ---":
                st.warning("الرجاء اختيار المرسل من القائمة")
                sender_name = ""
                sender_id = None
            elif contact_choice == "--- لا توجد جهات اتصال مسجلة ---":
                st.error("❌ لا توجد جهات اتصال مسجلة. الرجاء إضافة جهات اتصال أولاً.")
                sender_name = ""
                sender_id = None
            else:
                # الحصول على ID واسم المرسل
                contact_index = contact_display.index(contact_choice)
                sender_row = contacts_df.iloc[contact_index]
                sender_name = sender_row['name']
                sender_id = sender_row['id']
                
                # عرض معلومات إضافية عن المرسل
                with st.expander("معلومات المرسل", expanded=False):
                    st.info(f"""
                    **معلومات الجهة:**
                    - **المؤسسة:** {sender_row.get('organization', 'غير محدد')}
                    - **الهاتف:** {sender_row.get('phone', 'غير محدد')}
                    - **البريد الإلكتروني:** {sender_row.get('email', 'غير محدد')}
                    """)
            
            # خيار لإضافة مرسل جديد (ليس في القائمة)
            add_new_sender = st.checkbox("إضافة مرسل جديد (غير موجود في القائمة)")
            
            if add_new_sender:
                new_sender_name = st.text_input("اسم المرسل الجديد *", placeholder="أدخل اسم المرسل الجديد")
                if new_sender_name:
                    sender_name = new_sender_name
                    sender_id = None
                    st.success(f"✅ سيتم تسجيل المرسل الجديد: {new_sender_name}")
        
        with col2:
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
            received_date = st.date_input("تاريخ الاستلام", value=date.today())
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
        
        # حقل تاريخ الاستحقاق
        col_due1, col_due2 = st.columns([1, 2])
        with col_due1:
            has_due_date = st.checkbox("تحديد تاريخ استحقاق")
        
        with col_due2:
            if has_due_date:
                due_date = st.date_input("تاريخ الاستحقاق", value=date.today() + timedelta(days=7))
            else:
                due_date = None
        
        content = st.text_area("محتوى الرسالة", height=150, placeholder="أدخل محتوى الرسالة...")
        notes = st.text_area("ملاحظات إضافية", height=100, placeholder="ملاحظات إضافية...")
        
        # المرفقات
        st.markdown("#### 📎 المرفقات")
        uploaded_files = st.file_uploader(
            "إرفاق مستندات", 
            type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt'],
            accept_multiple_files=True,
            help="يمكنك رفع أكثر من ملف"
        )
        
        # ملخص الملفات المرفوعة
        if uploaded_files:
            st.markdown("**الملفات المرفوعة:**")
            for i, file in enumerate(uploaded_files):
                st.markdown(f"- {file.name} ({file.size:,} بايت)")
        
        # زر التسجيل
        submitted = st.form_submit_button("💾 تسجيل البريد الوارد", use_container_width=True)
        
        if submitted:
            # التحقق من صحة البيانات
            validation_errors = []
            
            if not sender_name:
                validation_errors.append("اسم المرسل مطلوب")
            
            if not subject:
                validation_errors.append("الموضوع مطلوب")
            
            if contact_choice == "--- اختر من جهات الاتصال ---" and not add_new_sender:
                validation_errors.append("الرجاء اختيار المرسل من القائمة أو تفعيل خيار 'إضافة مرسل جديد'")
            
            if validation_errors:
                for error in validation_errors:
                    st.error(f"❌ {error}")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    # حفظ المرفقات
                    attachments = []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "incoming")
                            if filepath:
                                attachments.append(os.path.basename(filepath))
                    
                    # تسجيل البريد الوارد
                    cursor.execute('''
                    INSERT INTO incoming_mail 
                    (reference_no, sender_id, sender_name, subject, content, received_date, 
                     priority, status, category, due_date, attachments, notes, recorded_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        reference_no,
                        sender_id,  # يمكن أن يكون NULL إذا كان مرسل جديد
                        sender_name,
                        subject,
                        content,
                        received_date.strftime('%Y-%m-%d'),
                        priority,
                        "جديد",  # الحالة الافتراضية
                        category,
                        due_date.strftime('%Y-%m-%d') if due_date else None,
                        json.dumps(attachments) if attachments else None,
                        notes,
                        st.session_state.user['id']
                    ))
                    
                    conn.commit()
                    
                    # إذا كان مرسلاً جديداً، عرض خيار لإضافته لجهات الاتصال
                    if add_new_sender and sender_id is None:
                        st.info(f"👤 المرسل '{sender_name}' ليس في قاعدة جهات الاتصال.")
                        
                        col_add, col_skip = st.columns(2)
                        with col_add:
                            if st.button("➕ إضافة لجهات الاتصال", key="add_to_contacts"):
                                # توليد كود تلقائي
                                cursor.execute("SELECT MAX(CAST(SUBSTR(code, 2) AS INTEGER)) FROM contacts WHERE code LIKE 'C%'")
                                result = cursor.fetchone()[0]
                                next_code = f"C{(result or 0) + 1:03d}"
                                
                                cursor.execute('''
                                INSERT INTO contacts (code, name)
                                VALUES (?, ?)
                                ''', (next_code, sender_name))
                                
                                conn.commit()
                                st.success(f"✅ تمت إضافة '{sender_name}' لجهات الاتصال بالكود: {next_code}")
                        
                        with col_skip:
                            if st.button("تخطي", key="skip_add_contact"):
                                st.info("تم تخطي إضافة المرسل لجهات الاتصال")
                    
                    log_activity(st.session_state.user['id'], "تسجيل بريد وارد", 
                               f"رقم المرجع: {reference_no} - المرسل: {sender_name}")
                    
                    st.success(f"✅ تم تسجيل البريد الوارد بنجاح!")
                    st.balloons()
                    
                    # عرض ملخص البريد المسجل
                    with st.expander("📋 ملخص البريد المسجل", expanded=True):
                        summary_data = {
                            "رقم المرجع": reference_no,
                            "المرسل": sender_name,
                            "الموضوع": subject,
                            "تاريخ الاستلام": received_date.strftime('%Y-%m-%d'),
                            "الأولوية": priority,
                            "التصنيف": category,
                            "تاريخ الاستحقاق": due_date.strftime('%Y-%m-%d') if due_date else "غير محدد",
                            "عدد المرفقات": len(attachments)
                        }
                        
                        for key, value in summary_data.items():
                            st.markdown(f"**{key}:** {value}")
                    
                    # إعادة تعيين النموذج
                    st.rerun()
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً!")
                except Exception as e:
                    st.error(f"❌ خطأ في التسجيل: {str(e)}")
                    st.exception(e)
                finally:
                    conn.close()

def display_outgoing_mail():
    """عرض البريد الصادر"""
    if not check_permission('view'):
        st.warning("⚠️ ليس لديك صلاحية لعرض البريد الصادر")
        return
    
    conn = get_db_connection()
    
    st.markdown('<div class="card"><h3>إدارة البريد الصادر</h3></div>', unsafe_allow_html=True)
    
    # أزرار التصفية
    col_filters = st.columns([2, 1, 1, 1, 1])
    filters = ["الكل", "مسودة", "مرسل", "مؤرشف", "عاجل"]
    
    for i, filter_name in enumerate(filters):
        with col_filters[i]:
            if st.button(filter_name, key=f"filter_out_{filter_name}", use_container_width=True):
                st.session_state.mail_filter = filter_name
    
    # زر التصدير إلى Excel
    if check_permission('export'):
        excel_data = export_outgoing_to_excel()
        if excel_data:
            st.download_button(
                label="📥 تصدير إلى Excel",
                data=excel_data,
                file_name=f"البريد_الصادر_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="export_outgoing_excel"
            )
    
    # تطبيق التصفية
    if st.session_state.mail_filter == "الكل":
        query = "SELECT * FROM outgoing_mail ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "مسودة":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مسودة' ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "مرسل":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مرسل' ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "مؤرشف":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مؤرشف' ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "عاجل":
        query = "SELECT * FROM outgoing_mail WHERE priority = 'عاجل' ORDER BY sent_date DESC"
    
    try:
        df = pd.read_sql(query, conn)
    except:
        df = pd.DataFrame()
    
    if not df.empty:
        # البحث
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            search_ref = st.text_input("🔍 البحث برقم المرجع")
        with search_col2:
            search_recipient = st.text_input("🔍 البحث بالمستلم")
        
        if search_ref:
            df = df[df['reference_no'].str.contains(search_ref, case=False, na=False)]
        if search_recipient:
            df = df[df['recipient_name'].str.contains(search_recipient, case=False, na=False)]
        
        # عرض البيانات
        for idx, row in df.iterrows():
            with st.container():
                col_info, col_actions = st.columns([4, 1])
                
                with col_info:
                    st.markdown(f"""
                    <div class="mail-card">
                        <div class="mail-header">
                            <span class="mail-ref">{row['reference_no']}</span>
                            <span class="mail-priority {row['priority']}">{row['priority']}</span>
                            <span class="mail-status {row['status']}">{row['status']}</span>
                        </div>
                        <div class="mail-body">
                            <strong>{row['subject']}</strong><br>
                            <small>المستلم: {row['recipient_name']} | التاريخ: {row['sent_date']}</small>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col_actions:
                    col_view, col_edit = st.columns(2)
                    
                    with col_view:
                        if st.button("👁️", key=f"view_out_{row['id']}", help="عرض التفاصيل"):
                            st.session_state.view_mail_id = row['id']
                            st.session_state.view_mail_type = "outgoing"
                            st.rerun()
                    
                    with col_edit:
                        if check_permission('edit'):
                            if st.button("✏️", key=f"edit_out_{row['id']}", help="تعديل"):
                                st.session_state.edit_mail_id = row['id']
                                st.session_state.edit_mail_type = "outgoing"
                                st.rerun()
                        else:
                            st.button("✏️", key=f"edit_out_{row['id']}", help="تعديل", disabled=True)
                
                st.divider()
        
        st.markdown(f"**عدد النتائج:** {len(df)} بريد")
    else:
        st.info("لا توجد رسائل صادرة")
    
    if conn:
        conn.close()

def create_outgoing_mail():
    """إنشاء بريد صادر جديد"""
    if not check_permission('add'):
        st.warning("⚠️ ليس لديك صلاحية لإنشاء بريد صادر جديد")
        return
    
    st.markdown('<div class="card"><h3>إنشاء بريد صادر جديد</h3></div>', unsafe_allow_html=True)
    
    contacts_df = get_contacts()
    contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
    
    with st.form("outgoing_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no("outgoing"))
            
            recipient_choice = st.selectbox("اختر المستلم", contact_names)
            
            if recipient_choice == "--- اختر من جهات الاتصال ---":
                st.warning("الرجاء إضافة جهة اتصال أولاً من صفحة 'جهات الاتصال'")
                recipient_name = ""
                recipient_id = None
            else:
                recipient_name = recipient_choice
                recipient_id = contacts_df[contacts_df['name'] == recipient_choice].iloc[0]['id'] if not contacts_df.empty else None
                if recipient_id:
                    contact_info = get_contact_by_id(recipient_id)
                    if contact_info:
                        st.info(f"المؤسسة: {contact_info['organization']} | الهاتف: {contact_info['phone']} | البريد: {contact_info['email']}")
            
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
            status = st.selectbox("الحالة", ["مسودة", "مرسل"])
            sent_date = st.date_input("تاريخ الإرسال", value=date.today())
        
        content = st.text_area("محتوى الرسالة", height=200, placeholder="أدخل محتوى الرسالة...")
        notes = st.text_area("ملاحظات إضافية", height=100, placeholder="ملاحظات إضافية...")
        
        uploaded_files = st.file_uploader("إرفاق مستندات", 
                                        type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                        accept_multiple_files=True,
                                        help="يمكنك رفع أكثر من ملف")
        
        col_save, col_send = st.columns(2)
        with col_save:
            save_draft = st.form_submit_button("💾 حفظ مسودة", use_container_width=True)
        
        with col_send:
            send_mail = st.form_submit_button("📤 إرسال البريد", use_container_width=True)
        
        if save_draft or send_mail:
            if not subject or not recipient_name:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            elif recipient_choice == "--- اختر من جهات الاتصال ---":
                st.error("الرجاء اختيار المستلم من قائمة جهات الاتصال")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                final_status = "مرسل" if send_mail else "مسودة"
                bordereau_filename = None
                
                try:
                    attachments = []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "outgoing")
                            if filepath:
                                attachments.append(os.path.basename(filepath))
                    
                    # إنشاء البوردرية إذا كان البريد مرسلاً
                    if send_mail and recipient_id:
                        contact_info = get_contact_by_id(recipient_id)
                        mail_context = {
                            'reference_no': reference_no,
                            'sent_date': sent_date.strftime('%Y-%m-%d'),
                            'recipient_name': recipient_name,
                            'subject': subject,
                            'notes': notes
                        }
                        
                        buffer = generate_bordereau_for_mail(mail_context, contact_info)
                        
                        if buffer:
                            upload_dir = "uploads/bordereau"
                            os.makedirs(upload_dir, exist_ok=True)
                            bordereau_filename = f"بوردرية_{reference_no}.docx"
                            bordereau_path = os.path.join(upload_dir, bordereau_filename)
                            
                            with open(bordereau_path, "wb") as f:
                                f.write(buffer.getvalue())
                    
                    cursor.execute('''
                    INSERT INTO outgoing_mail 
                    (reference_no, recipient_id, recipient_name, subject, content, priority, 
                     status, sent_date, sent_by, category, attachments, bordereau, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, recipient_id, recipient_name, subject, content, priority,
                          final_status, sent_date.strftime('%Y-%m-%d'), 
                          st.session_state.user['id'], category, 
                          json.dumps(attachments) if attachments else None,
                          bordereau_filename, notes))
                    
                    conn.commit()
                    action = "إرسال بريد صادر" if send_mail else "حفظ مسودة بريد صادر"
                    log_activity(st.session_state.user['id'], action, f"رقم المرجع: {reference_no}")
                    
                    st.success(f"✅ تم {action} بنجاح!")
                    if send_mail:
                        st.balloons()
                    
                    st.markdown("#### ملخص البريد المسجل")
                    summary_data = {
                        "رقم المرجع": reference_no,
                        "المستلم": recipient_name,
                        "الموضوع": subject,
                        "تاريخ الإرسال": sent_date.strftime('%Y-%m-%d'),
                        "الحالة": final_status
                    }
                    if send_mail:
                        summary_data["البوردرية"] = "تم إنشاؤها تلقائياً"
                    st.json(summary_data)
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً!")
                finally:
                    conn.close()

def display_contacts():
    """عرض وإدارة جهات الاتصال"""
    st.markdown('<div class="card"><h3>إدارة جهات الاتصال</h3></div>', unsafe_allow_html=True)
    
    if st.button("➕ إضافة جهة اتصال جديدة", use_container_width=True, key="add_contact_btn"):
        st.session_state.show_contact_form = True
    
    if st.session_state.get('show_contact_form', False):
        with st.form("add_contact_form", clear_on_submit=True):
            st.markdown("### إضافة جهة اتصال جديدة")
            
            col1, col2 = st.columns(2)
            
            with col1:
                code = st.text_input("الكود *", key="contact_code", placeholder="مثال: C001")
                name = st.text_input("الاسم *", key="contact_name", placeholder="الاسم الكامل")
                organization = st.text_input("المؤسسة", key="contact_org", placeholder="اسم المؤسسة")
            
            with col2:
                phone = st.text_input("الهاتف", key="contact_phone", placeholder="رقم الهاتف")
                email = st.text_input("البريد الإلكتروني", key="contact_email", placeholder="example@domain.com")
            
            col_submit, col_cancel = st.columns(2)
            with col_submit:
                submitted = st.form_submit_button("💾 إضافة جهة اتصال", use_container_width=True)
            
            with col_cancel:
                if st.form_submit_button("إلغاء", use_container_width=True):
                    st.session_state.show_contact_form = False
                    st.rerun()
            
            if submitted:
                if code and name:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                        INSERT INTO contacts (code, name, organization, phone, email)
                        VALUES (?, ?, ?, ?, ?)
                        ''', (code, name, organization, phone, email))
                        
                        conn.commit()
                        st.success(f"✅ تم إضافة جهة الاتصال {name} بنجاح")
                        st.session_state.show_contact_form = False
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(f"❌ الكود '{code}' موجود مسبقاً!")
                    except Exception as e:
                        st.error(f"❌ خطأ في إضافة جهة الاتصال: {str(e)}")
                    finally:
                        conn.close()
                else:
                    st.error("❌ الرجاء إدخال الكود والاسم")
    
    search_term = st.text_input("🔍 بحث في الجهات...", placeholder="كود، اسم، مؤسسة...")
    
    contacts_df = get_contacts()
    
    if not contacts_df.empty:
        if not search_term:
            filtered_contacts = contacts_df
        else:
            filtered_contacts = contacts_df[
                contacts_df['code'].str.contains(search_term, case=False, na=False) |
                contacts_df['name'].str.contains(search_term, case=False, na=False) |
                contacts_df['organization'].str.contains(search_term, case=False, na=False) |
                contacts_df['email'].str.contains(search_term, case=False, na=False)
            ]
        
        if not filtered_contacts.empty:
            st.dataframe(filtered_contacts, use_container_width=True, hide_index=True)
            
            with st.expander("خيارات متقدمة"):
                selected_contact = st.selectbox("اختر جهة اتصال", filtered_contacts['name'].tolist(), key="contact_select")
                if selected_contact:
                    contact_id = filtered_contacts[filtered_contacts['name'] == selected_contact].iloc[0]['id']
                    
                    col_del, col_edit = st.columns(2)
                    with col_del:
                        if st.button("🗑️ حذف الجهة", use_container_width=True, key="delete_contact"):
                            conn = get_db_connection()
                            try:
                                cursor = conn.cursor()
                                cursor.execute("SELECT COUNT(*) FROM incoming_mail WHERE sender_id = ?", (contact_id,))
                                mail_incoming = cursor.fetchone()[0]
                                cursor.execute("SELECT COUNT(*) FROM outgoing_mail WHERE recipient_id = ?", (contact_id,))
                                mail_outgoing = cursor.fetchone()[0]
                                
                                if mail_incoming > 0 or mail_outgoing > 0:
                                    st.warning(f"⚠️ لا يمكن حذف الجهة لأنها مستخدمة في {mail_incoming + mail_outgoing} بريد")
                                else:
                                    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
                                    conn.commit()
                                    st.success("✅ تم حذف الجهة بنجاح")
                                    st.rerun()
                            finally:
                                conn.close()
    else:
        st.info("📭 لا توجد جهات اتصال مسجلة")

# --- الواجهة الرئيسية ---
def main_interface():
    """الواجهة الرئيسية بعد تسجيل الدخول"""
    
    # --- القائمة الجانبية (العمود الأيمن) ---
    with st.sidebar:
        st.markdown("""
        <style>
        .sidebar-container {
            padding: 20px;
        }
        .sidebar-title {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }
        .sidebar-subtitle {
            font-size: 14px;
            color: #3498db;
            margin-bottom: 20px;
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-title">المدرسة الإعدادية حي الأمل </div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-subtitle">مكتب الضبط </div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # القائمة الرئيسية
        menu_options = {
            "📊 لوحة القيادة": "لوحة القيادة",
            "📥 البريد الوارد": "البريد الوارد",
            "📤 البريد الصادر": "البريد الصادر",
            "📇 جهات الاتصال": "جهات الاتصال",
            "📄 إنشاء بوردرية": "إنشاء بوردرية"
        }
        
        # إضافة خيارات حسب الصلاحيات
        if check_permission('add'):
            menu_options["➕ تسجيل بريد وارد"] = "تسجيل بريد وارد"
            menu_options["✏️ إنشاء بريد صادر"] = "إنشاء بريد صادر"
        
        if check_permission('manage_users'):
            menu_options["👥 إدارة المستخدمين"] = "إدارة المستخدمين"
        
        for icon_text, page_name in menu_options.items():
            if st.button(icon_text, key=f"menu_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.session_state.edit_mail_id = None
                st.session_state.edit_mail_type = None
                st.session_state.view_mail_id = None
                st.session_state.view_mail_type = None
                st.rerun()
        
        st.markdown("---")
        
        if st.session_state.user:
            st.markdown(f"**المستخدم:** {st.session_state.user['full_name']}")
            st.markdown(f"**الدور:** {st.session_state.user['role']}")
        
        st.markdown("---")
        
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout_user()
    
    # --- المحتوى الرئيسي ---
    col_user, col_date = st.columns([2, 1])
    with col_user:
        if st.session_state.user:
            st.markdown(f'<div style="font-size: 18px; font-weight: bold;">مرحباً {st.session_state.user["full_name"]}</div>', unsafe_allow_html=True)
    
    with col_date:
        today = datetime.now().strftime("%Y-%m-%d %H:%M")
        st.markdown(f'<div style="text-align: right; color: #666;">{today}</div>', unsafe_allow_html=True)
    
    # التحقق من تواريخ الاستحقاق القريبة
    if check_permission('view'):
        reminders = check_due_date_reminders()
        if not reminders.empty:
            with st.expander("📢 تنبيه: بريد وارد قريب من تاريخ الاستحقاق", expanded=True):
                for idx, row in reminders.iterrows():
                    days_left = (datetime.strptime(row['due_date'], '%Y-%m-%d').date() - date.today()).days
                    if days_left < 0:
                        st.error(f"**{row['reference_no']}** - {row['subject']} - تجاوز الاستحقاق ب {abs(days_left)} يوم")
                    else:
                        st.warning(f"**{row['reference_no']}** - {row['subject']} - متبقي {days_left} يوم للاستحقاق")
    
    st.markdown(f'<h1>{st.session_state.page}</h1>', unsafe_allow_html=True)
    
    # توجيه إلى الصفحة المحددة
    if st.session_state.page == "لوحة القيادة":
        display_dashboard()
    elif st.session_state.page == "البريد الوارد":
        if st.session_state.view_mail_id and st.session_state.view_mail_type == "incoming":
            view_mail_details(st.session_state.view_mail_id, "incoming")
        elif st.session_state.edit_mail_id and st.session_state.edit_mail_type == "incoming":
            edit_incoming_mail(st.session_state.edit_mail_id)
        else:
            display_incoming_mail()
    elif st.session_state.page == "تسجيل بريد وارد":
        register_incoming_mail()
    elif st.session_state.page == "البريد الصادر":
        if st.session_state.view_mail_id and st.session_state.view_mail_type == "outgoing":
            view_mail_details(st.session_state.view_mail_id, "outgoing")
        elif st.session_state.edit_mail_id and st.session_state.edit_mail_type == "outgoing":
            edit_outgoing_mail(st.session_state.edit_mail_id)
        else:
            display_outgoing_mail()
    elif st.session_state.page == "إنشاء بريد صادر":
        create_outgoing_mail()
    elif st.session_state.page == "جهات الاتصال":
        display_contacts()
    elif st.session_state.page == "إنشاء بوردرية":
        display_bordereau_generator()
    elif st.session_state.page == "إدارة المستخدمين":
        display_user_management()

# --- التطبيق الرئيسي ---
def main():
    """الدالة الرئيسية للتطبيق"""
    
    if st.session_state.user is None:
        login_screen()
    else:
        main_interface()

if __name__ == "__main__":
    main()