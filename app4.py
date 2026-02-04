# app.py - مع سكربت إنشاء البوردرية المحدث
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
from datetime import datetime, date, timedelta
import json
import tempfile
import io
from database import get_db_connection, log_activity
from docxtpl import DocxTemplate
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(
    page_title="نظام مكتب النظام - معهد حي الأمل بقابس",
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

# --- نظام المصادقة ---
def authenticate_user(username, password):
    """مصادقة المستخدم"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    SELECT id, username, full_name, role, email FROM users 
    WHERE username = ? AND password = ? AND is_active = 1
    ''', (username, password))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        st.session_state.user = {
            'id': user[0],
            'username': user[1],
            'full_name': user[2],
            'role': user[3],
            'email': user[4]
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
    """جلب جميع المستخدمين"""
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

# --- وظائف تصدير إلى Excel ---
def export_incoming_to_excel():
    """تصدير البريد الوارد إلى Excel"""
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
        st.markdown('<div class="institution-title">معهد حي الأمل بقابس</div>', unsafe_allow_html=True)
        st.markdown('<div class="system-title">نظام مكتب النظام</div>', unsafe_allow_html=True)
        
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

# --- وظائف عرض الصفحات ---
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
                        if st.button("✏️", key=f"edit_{row['id']}", help="تعديل"):
                            st.session_state.edit_mail_id = row['id']
                            st.session_state.edit_mail_type = "incoming"
                            st.rerun()
                    
                    with col_delete:
                        if st.button("🗑️", key=f"delete_{row['id']}", help="حذف"):
                            if st.button(f"⚠️ تأكيد حذف {row['reference_no']}", key=f"confirm_delete_{row['id']}"):
                                cursor = conn.cursor()
                                cursor.execute("DELETE FROM incoming_mail WHERE id = ?", (row['id'],))
                                conn.commit()
                                log_activity(st.session_state.user['id'], "حذف بريد وارد", 
                                           f"{row['reference_no']}")
                                st.success("تم حذف البريد الوارد")
                                st.rerun()
                
                st.divider()
        
        # عرض ملخص
        st.markdown(f"**عدد النتائج:** {len(df)} بريد")
        
    else:
        st.info("لا توجد رسائل واردة")
    
    conn.close()

def show_incoming_stats():
    """عرض إحصائيات البريد الوارد"""
    conn = get_db_connection()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        try:
            total = pd.read_sql("SELECT COUNT(*) FROM incoming_mail", conn).iloc[0,0]
            st.metric("إجمالي البريد", total)
        except:
            st.metric("إجمالي البريد", 0)
    
    with col2:
        try:
            new = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status = 'جديد'", conn).iloc[0,0]
            st.metric("جديد", new)
        except:
            st.metric("جديد", 0)
    
    with col3:
        try:
            urgent = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE priority = 'عاجل'", conn).iloc[0,0]
            st.metric("عاجل", urgent)
        except:
            st.metric("عاجل", 0)
    
    # مخطط توزيع الحالات
    try:
        status_dist = pd.read_sql("SELECT status, COUNT(*) as count FROM incoming_mail GROUP BY status", conn)
        if not status_dist.empty:
            st.markdown("### توزيع الحالات")
            st.bar_chart(status_dist.set_index('status'))
    except:
        pass
    
    conn.close()

def register_incoming_mail():
    """تسجيل بريد وارد جديد"""
    st.markdown('<div class="card"><h3>تسجيل بريد وارد جديد</h3></div>', unsafe_allow_html=True)
    
    with st.form("incoming_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no("incoming"))
            sender_name = st.text_input("اسم المرسل *", placeholder="اسم المرسل أو المؤسسة")
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
            received_date = st.date_input("تاريخ الاستلام", value=date.today())
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
            due_date = st.date_input("تاريخ الاستحقاق (اختياري)", value=None)
        
        content = st.text_area("محتوى الرسالة", height=150, placeholder="أدخل محتوى الرسالة...")
        notes = st.text_area("ملاحظات إضافية", height=100, placeholder="ملاحظات إضافية...")
        
        uploaded_files = st.file_uploader("إرفاق مستندات", 
                                        type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                        accept_multiple_files=True)
        
        submitted = st.form_submit_button("💾 تسجيل البريد الوارد")
        
        if submitted:
            if not sender_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                try:
                    attachments = []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "incoming")
                            if filepath:
                                attachments.append(os.path.basename(filepath))
                    
                    cursor.execute('''
                    INSERT INTO incoming_mail 
                    (reference_no, sender_name, subject, content, received_date, 
                     priority, status, category, due_date, attachments, notes, recorded_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, sender_name, subject, content, received_date.strftime('%Y-%m-%d'),
                          priority, "جديد", category, 
                          due_date.strftime('%Y-%m-%d') if due_date else None,
                          json.dumps(attachments) if attachments else None,
                          notes, st.session_state.user['id']))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تسجيل بريد وارد", 
                               f"رقم المرجع: {reference_no}")
                    st.success(f"✅ تم تسجيل البريد الوارد بنجاح!")
                    st.balloons()
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً!")
                except Exception as e:
                    st.error(f"❌ خطأ في التسجيل: {str(e)}")
                finally:
                    conn.close()

def display_outgoing_mail():
    """عرض البريد الصادر"""
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
                        if st.button("✏️", key=f"edit_out_{row['id']}", help="تعديل"):
                            st.session_state.edit_mail_id = row['id']
                            st.session_state.edit_mail_type = "outgoing"
                            st.rerun()
                
                st.divider()
        
        st.markdown(f"**عدد النتائج:** {len(df)} بريد")
    else:
        st.info("لا توجد رسائل صادرة")
    
    if conn:
        conn.close()

def create_outgoing_mail():
    """إنشاء بريد صادر جديد"""
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

def edit_incoming_mail(mail_id):
    """تعديل البريد الوارد مع إمكانية إزالة تاريخ الاستحقاق عند المعالجة"""
    st.markdown('<div class="card"><h3>تعديل البريد الوارد</h3></div>', unsafe_allow_html=True)
    
    mail_data = get_mail_by_id(mail_id, "incoming")
    
    if not mail_data:
        st.error("البريد غير موجود")
        st.session_state.edit_mail_id = None
        st.session_state.edit_mail_type = None
        return
    
    with st.form("edit_incoming_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع", value=mail_data['reference_no'], disabled=True)
            sender_name = st.text_input("اسم المرسل *", value=mail_data['sender_name'])
            subject = st.text_input("الموضوع *", value=mail_data['subject'])
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"], 
                                  index=["عادي", "مهم", "عاجل"].index(mail_data['priority']))
            status = st.selectbox("الحالة", ["جديد", "قيد المعالجة", "مكتمل", "ملغي"], 
                                index=["جديد", "قيد المعالجة", "مكتمل", "ملغي"].index(mail_data['status']))
            
            received_date = st.date_input("تاريخ الاستلام", 
                                        value=datetime.strptime(mail_data['received_date'], '%Y-%m-%d').date())
        
        # تاريخ الاستحقاق - يمكن إزالته إذا كانت الحالة "مكتمل"
        col_due1, col_due2 = st.columns(2)
        with col_due1:
            show_due_date = st.checkbox("تعديل تاريخ الاستحقاق", value=mail_data['due_date'] is not None)
        
        with col_due2:
            if show_due_date:
                due_date = st.date_input("تاريخ الاستحقاق", 
                                       value=datetime.strptime(mail_data['due_date'], '%Y-%m-%d').date() if mail_data['due_date'] else date.today())
            else:
                due_date = None
        
        # إذا كانت الحالة "مكتمل" أو "ملغي"، يمكن إزالة تاريخ الاستحقاق
        if status in ["مكتمل", "ملغي"]:
            st.info("⚠️ تمت معالجة البريد، يمكن إزالة تاريخ الاستحقاق")
            remove_due_date = st.checkbox("إزالة تاريخ الاستحقاق (لأن البريد تمت معالجته)")
            if remove_due_date:
                due_date = None
        
        content = st.text_area("محتوى الرسالة", value=mail_data['content'] or "", height=150)
        notes = st.text_area("ملاحظات إضافية", value=mail_data['notes'] or "", height=100)
        
        current_attachments = get_attachment_list(mail_data['attachments'])
        if current_attachments:
            st.markdown("**المرفقات الحالية:**")
            for att in current_attachments:
                st.markdown(f"- {att}")
        
        new_files = st.file_uploader("إرفاق مستندات جديدة", 
                                    type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                    accept_multiple_files=True)
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.edit_mail_id = None
                st.session_state.edit_mail_type = None
                st.rerun()
        
        if submitted:
            if not sender_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    new_attachments = []
                    if new_files:
                        for file in new_files:
                            filepath = save_uploaded_file(file, "incoming")
                            if filepath:
                                new_attachments.append(os.path.basename(filepath))
                    
                    all_attachments = current_attachments + new_attachments
                    
                    cursor.execute('''
                    UPDATE incoming_mail SET 
                    sender_name = ?, subject = ?, content = ?, priority = ?, 
                    status = ?, received_date = ?, due_date = ?, attachments = ?, notes = ?
                    WHERE id = ?
                    ''', (sender_name, subject, content, priority, status,
                          received_date.strftime('%Y-%m-%d'),
                          due_date.strftime('%Y-%m-%d') if due_date else None,
                          json.dumps(all_attachments) if all_attachments else None,
                          notes, mail_id))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تعديل بريد وارد", 
                               f"تم تعديل بريد: {reference_no}")
                    st.success("✅ تم تحديث البريد الوارد بنجاح!")
                    
                    st.session_state.edit_mail_id = None
                    st.session_state.edit_mail_type = None
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ خطأ في التحديث: {str(e)}")
                finally:
                    conn.close()

def edit_outgoing_mail(mail_id):
    """تعديل البريد الصادر"""
    st.markdown('<div class="card"><h3>تعديل البريد الصادر</h3></div>', unsafe_allow_html=True)
    
    mail_data = get_mail_by_id(mail_id, "outgoing")
    
    if not mail_data:
        st.error("البريد غير موجود")
        st.session_state.edit_mail_id = None
        st.session_state.edit_mail_type = None
        return
    
    contacts_df = get_contacts()
    contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
    
    with st.form("edit_outgoing_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            reference_no = st.text_input("رقم المرجع", value=mail_data['reference_no'], disabled=True)
            
            current_recipient = mail_data['recipient_name']
            recipient_index = contact_names.index(current_recipient) if current_recipient in contact_names else 0
            recipient_choice = st.selectbox("اختر المستلم", contact_names, index=recipient_index)
            
            if recipient_choice == "--- اختر من جهات الاتصال ---":
                st.warning("الرجاء اختيار المستلم من قائمة جهات الاتصال")
                recipient_name = ""
                recipient_id = None
            else:
                recipient_name = recipient_choice
                recipient_id = contacts_df[contacts_df['name'] == recipient_choice].iloc[0]['id'] if not contacts_df.empty else None
            
            subject = st.text_input("الموضوع *", value=mail_data['subject'])
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"], 
                                  index=["عادي", "مهم", "عاجل"].index(mail_data['priority']))
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"], 
                                  index=["إداري", "مالي", "فني", "قانوني", "أخرى"].index(mail_data['category']) if mail_data['category'] in ["إداري", "مالي", "فني", "قانوني", "أخرى"] else 0)
            
            status = st.selectbox("الحالة", ["مسودة", "مرسل", "مؤرشف"], 
                                index=["مسودة", "مرسل", "مؤرشف"].index(mail_data['status']))
            
            sent_date = st.date_input("تاريخ الإرسال", 
                                    value=datetime.strptime(mail_data['sent_date'], '%Y-%m-%d').date() if mail_data['sent_date'] else date.today())
        
        content = st.text_area("محتوى الرسالة", value=mail_data['content'] or "", height=150)
        notes = st.text_area("ملاحظات إضافية", value=mail_data['notes'] or "", height=100)
        
        current_attachments = get_attachment_list(mail_data['attachments'])
        if current_attachments:
            st.markdown("**المرفقات الحالية:**")
            for att in current_attachments:
                st.markdown(f"- {att}")
        
        new_files = st.file_uploader("إرفاق مستندات جديدة", 
                                    type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                    accept_multiple_files=True)
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("💾 حفظ التعديلات", use_container_width=True)
        
        with col_cancel:
            if st.form_submit_button("إلغاء", use_container_width=True):
                st.session_state.edit_mail_id = None
                st.session_state.edit_mail_type = None
                st.rerun()
        
        if submitted:
            if not recipient_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    new_attachments = []
                    if new_files:
                        for file in new_files:
                            filepath = save_uploaded_file(file, "outgoing")
                            if filepath:
                                new_attachments.append(os.path.basename(filepath))
                    
                    all_attachments = current_attachments + new_attachments
                    
                    cursor.execute('''
                    UPDATE outgoing_mail SET 
                    recipient_id = ?, recipient_name = ?, subject = ?, content = ?, 
                    priority = ?, category = ?, status = ?, sent_date = ?,
                    attachments = ?, notes = ?
                    WHERE id = ?
                    ''', (recipient_id, recipient_name, subject, content, priority, 
                          category, status, sent_date.strftime('%Y-%m-%d'),
                          json.dumps(all_attachments) if all_attachments else None,
                          notes, mail_id))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تعديل بريد صادر", 
                               f"تم تعديل بريد: {reference_no}")
                    st.success("✅ تم تحديث البريد الصادر بنجاح!")
                    
                    st.session_state.edit_mail_id = None
                    st.session_state.edit_mail_type = None
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ خطأ في التحديث: {str(e)}")
                finally:
                    conn.close()

def view_mail_details(mail_id, mail_type):
    """عرض تفاصيل البريد في صفحة كاملة"""
    st.markdown('<div class="card"><h3>تفاصيل البريد</h3></div>', unsafe_allow_html=True)
    
    mail_data = get_mail_by_id(mail_id, mail_type)
    
    if not mail_data:
        st.error("البريد غير موجود")
        st.session_state.view_mail_id = None
        st.session_state.view_mail_type = None
        return
    
    # أزرار الإجراءات
    col_back, col_export = st.columns([1, 1])
    with col_back:
        if st.button("⬅️ العودة", use_container_width=True):
            st.session_state.view_mail_id = None
            st.session_state.view_mail_type = None
            st.rerun()
    
    # عرض التفاصيل
    if mail_type == "incoming":
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 معلومات أساسية")
            st.markdown(f"**رقم المرجع:** {mail_data['reference_no']}")
            st.markdown(f"**المرسل:** {mail_data['sender_name']}")
            st.markdown(f"**تاريخ الاستلام:** {mail_data['received_date']}")
            st.markdown(f"**تاريخ الاستحقاق:** {mail_data['due_date'] or 'غير محدد'}")
            
            if mail_data['due_date']:
                try:
                    due_date = datetime.strptime(mail_data['due_date'], '%Y-%m-%d').date()
                    days_left = (due_date - date.today()).days
                    if days_left < 0:
                        st.error(f"⏰ تجاوز تاريخ الاستحقاق ب {abs(days_left)} يوم")
                    elif days_left <= 3:
                        st.warning(f"⏰ متبقي {days_left} يوم للاستحقاق")
                    else:
                        st.info(f"⏰ متبقي {days_left} يوم للاستحقاق")
                except:
                    pass
        
        with col2:
            st.markdown("### 📊 معلومات إضافية")
            st.markdown(f"**الأولوية:** {mail_data['priority']}")
            st.markdown(f"**الحالة:** {mail_data['status']}")
            st.markdown(f"**التصنيف:** {mail_data.get('category', 'غير محدد')}")
            st.markdown(f"**تاريخ الإنشاء:** {mail_data.get('created_at', 'غير معروف')}")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📋 معلومات أساسية")
            st.markdown(f"**رقم المرجع:** {mail_data['reference_no']}")
            st.markdown(f"**المستلم:** {mail_data['recipient_name']}")
            st.markdown(f"**تاريخ الإرسال:** {mail_data['sent_date']}")
            st.markdown(f"**الحالة:** {mail_data['status']}")
        
        with col2:
            st.markdown("### 📊 معلومات إضافية")
            st.markdown(f"**الأولوية:** {mail_data['priority']}")
            st.markdown(f"**التصنيف:** {mail_data.get('category', 'غير محدد')}")
            st.markdown(f"**تاريخ الإنشاء:** {mail_data.get('created_at', 'غير معروف')}")
            
            if mail_data.get('bordereau'):
                st.markdown(f"**البوردرية:** {mail_data['bordereau']}")
    
    st.markdown("---")
    st.markdown(f"### 📝 الموضوع")
    st.markdown(f"**{mail_data['subject']}**")
    
    if mail_data.get('content'):
        st.markdown(f"### 📄 المحتوى")
        st.markdown(mail_data['content'])
    
    if mail_data.get('notes'):
        st.markdown(f"### 📌 ملاحظات")
        st.markdown(mail_data['notes'])
    
    # عرض المرفقات
    attachments = get_attachment_list(mail_data.get('attachments'))
    if attachments:
        st.markdown("---")
        st.markdown("### 📎 المرفقات")
        
        if mail_type == "incoming":
            upload_dir = "uploads/incoming"
        else:
            upload_dir = "uploads/outgoing"
        
        for att in attachments:
            file_path = os.path.join(upload_dir, att)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    st.download_button(
                        label=f"تحميل {att}",
                        data=f,
                        file_name=att,
                        mime="application/octet-stream",
                        key=f"download_{att}_{mail_id}"
                    )
            else:
                st.warning(f"الملف {att} غير موجود")

def display_bordereau_generator():
    """عرض واجهة إنشاء البوردرية"""
    st.markdown('<div class="card"><h3>منشئ البوردرية</h3></div>', unsafe_allow_html=True)
    
    # خياران: إنشاء بوردرية جديدة أو لبريد محدد
    option = st.radio(
        "اختر الخيار:",
        ["إنشاء بوردرية جديدة", "إنشاء بوردرية لبريد صادر محدد"],
        horizontal=True
    )
    
    if option == "إنشاء بوردرية لبريد صادر محدد":
        # جلب قائمة البريد الصادر
        conn = get_db_connection()
        outgoing_mails = pd.read_sql("SELECT id, reference_no, recipient_name, subject FROM outgoing_mail ORDER BY sent_date DESC", conn)
        conn.close()
        
        if not outgoing_mails.empty:
            mail_options = {f"{row['reference_no']} - {row['recipient_name']}": row['id'] 
                          for _, row in outgoing_mails.iterrows()}
            
            mail_list = list(mail_options.keys())
            selected_mail = st.selectbox(
                "اختر البريد الصادر:",
                options=mail_list
            )
            
            if selected_mail:
                mail_id = mail_options[selected_mail]
                show_bordereau_generator(mail_id)
        else:
            st.info("لا توجد بريد صادر. يمكنك إنشاء بوردرية جديدة.")
            show_bordereau_generator()
    else:
        show_bordereau_generator()

def show_bordereau_generator(mail_id=None):
    """
    عرض واجهة إنشاء البوردرية
    
    Args:
        mail_id (int): ID البريد الصادر (اختياري)
    """
    st.markdown("### 📄 إنشاء بوردرية للبريد الصادر")
    
    # قسم معلومات القالب
    st.markdown("#### 1. معلومات القالب")
    if not os.path.exists("templates/bordereau_template.docx"):
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
        return
    
    st.success("✅ تم العثور على قالب البوردرية في templates/bordereau_template.docx")
    
    # قسم إدخال البيانات
    st.markdown("#### 2. إدخال بيانات البريد")
    
    if mail_id:
        # إذا كان هناك بريد محدد، جلب بياناته
        mail_data = get_mail_by_id(mail_id, "outgoing")
        if mail_data:
            recipient_id = mail_data.get('recipient_id')
            contact_info = get_contact_by_id(recipient_id) if recipient_id else None
        else:
            mail_data = {}
            contact_info = None
    else:
        mail_data = {}
        contact_info = None
    
    # إعداد حقول الإدخال
    col1, col2 = st.columns(2)
    
    with col1:
        reference_no = st.text_input(
            "رقم المرجع *",
            value=mail_data.get('reference_no', generate_ref_no("outgoing")),
            placeholder="مثال: ص-0001-01-2024",
            key="bordereau_ref"
        )
        
        # جلب قائمة جهات الاتصال
        contacts_df = get_contacts()
        contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
        
        current_recipient = mail_data.get('recipient_name', '')
        recipient_index = contact_names.index(current_recipient) if current_recipient in contact_names else 0
        recipient_choice = st.selectbox(
            "اختر المستلم *",
            contact_names,
            index=recipient_index,
            key="bordereau_recipient"
        )
        
        if recipient_choice == "--- اختر من جهات الاتصال ---":
            st.warning("الرجاء اختيار المستلم من قائمة جهات الاتصال")
            recipient_name = ""
            recipient_id = None
        else:
            recipient_name = recipient_choice
            recipient_id = contacts_df[contacts_df['name'] == recipient_choice].iloc[0]['id'] if not contacts_df.empty else None
            
            # عرض معلومات جهة الاتصال
            if recipient_id and not contact_info:
                contact_info = get_contact_by_id(recipient_id)
        
        subject = st.text_input(
            "الموضوع *",
            value=mail_data.get('subject', ''),
            placeholder="موضوع البريد",
            key="bordereau_subject"
        )
    
    with col2:
        sent_date = st.date_input(
            "تاريخ الإرسال *",
            value=datetime.strptime(mail_data.get('sent_date', date.today().strftime('%Y-%m-%d')), '%Y-%m-%d').date() if mail_data.get('sent_date') else date.today(),
            key="bordereau_date"
        )
        
        # عرض معلومات جهة الاتصال إذا كانت متوفرة
        if contact_info:
            st.info(f"""
            **معلومات المستلم:**
            - المؤسسة: {contact_info.get('organization', 'غير محدد')}
            - الهاتف: {contact_info.get('phone', 'غير محدد')}
            - البريد: {contact_info.get('email', 'غير محدد')}
            """)
    
    notes = st.text_area(
        "ملاحظات",
        value=mail_data.get('notes', ''),
        placeholder="أي ملاحظات إضافية...",
        height=100,
        key="bordereau_notes"
    )
    
    # زر إنشاء البوردرية (خارج النموذج)
    if st.button("🔄 إنشاء البوردرية", key="generate_bordereau_btn"):
        if not reference_no or not recipient_name or not subject:
            st.error("❌ الرجاء ملء جميع الحقول الإلزامية (*)")
        elif recipient_choice == "--- اختر من جهات الاتصال ---":
            st.error("❌ الرجاء اختيار المستلم من قائمة جهات الاتصال")
        else:
            # إعداد بيانات البريد
            mail_context = {
                'reference_no': reference_no,
                'sent_date': sent_date.strftime('%Y-%m-%d'),
                'recipient_name': recipient_name,
                'subject': subject,
                'notes': notes
            }
            
            # إنشاء البوردرية
            buffer = generate_bordereau_for_mail(mail_context, contact_info)
            
            if buffer:
                # حفظ البوردرية في حالة الجلسة
                st.session_state.bordereau_buffer = buffer
                st.session_state.bordereau_data = {
                    'reference_no': reference_no,
                    'sent_date': sent_date.strftime('%Y-%m-%d'),
                    'recipient_name': recipient_name,
                    'subject': subject,
                    'notes': notes,
                    'mail_id': mail_id,
                    'recipient_id': recipient_id
                }
                st.success("✅ تم إنشاء البوردرية بنجاح!")
    
    # عرض زر التحميل إذا كان هناك بوردرية جاهزة
    if st.session_state.bordereau_buffer:
        st.markdown("---")
        st.markdown("#### 3. تحميل البوردرية")
        
        bordereau_data = st.session_state.bordereau_data
        if bordereau_data:
            st.download_button(
                label="📥 تحميل البوردرية",
                data=st.session_state.bordereau_buffer,
                file_name=f"بوردرية_{bordereau_data['reference_no']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="download_bordereau"
            )
            
            # إذا كان هناك بريد محدد، حفظ البوردرية في قاعدة البيانات
            if bordereau_data['mail_id'] and bordereau_data['recipient_id']:
                if st.button("💾 حفظ البوردرية للسجلات", key="save_bordereau_record"):
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    
                    # حفظ البوردرية
                    upload_dir = "uploads/bordereau"
                    os.makedirs(upload_dir, exist_ok=True)
                    bordereau_filename = f"بوردرية_{bordereau_data['reference_no']}.docx"
                    bordereau_path = os.path.join(upload_dir, bordereau_filename)
                    
                    with open(bordereau_path, "wb") as f:
                        f.write(st.session_state.bordereau_buffer.getvalue())
                    
                    # تحديث قاعدة البيانات
                    cursor.execute(
                        "UPDATE outgoing_mail SET bordereau = ? WHERE id = ?",
                        (bordereau_filename, bordereau_data['mail_id'])
                    )
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ تم حفظ البوردرية للسجلات: {bordereau_filename}")
                    
                    # إعادة تعيين الحالة
                    st.session_state.bordereau_buffer = None
                    st.session_state.bordereau_data = None
                    st.rerun()

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

# --- واجهة التطبيق الرئيسية ---
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
        
        st.markdown('<div class="sidebar-title">معهد حي الأمل بقابس</div>', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-subtitle">نظام مكتب النظام</div>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # القائمة الرئيسية
        menu_options = {
            "📊 لوحة القيادة": "لوحة القيادة",
            "📥 البريد الوارد": "البريد الوارد",
            "➕ تسجيل بريد وارد": "تسجيل بريد وارد",
            "📤 البريد الصادر": "البريد الصادر",
            "✏️ إنشاء بريد صادر": "إنشاء بريد صادر",
            "📇 جهات الاتصال": "جهات الاتصال",
            "📄 إنشاء بوردرية": "إنشاء بوردرية"
        }
        
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

# --- التطبيق الرئيسي ---
def main():
    """الدالة الرئيسية للتطبيق"""
    
    if st.session_state.user is None:
        login_screen()
    else:
        main_interface()

if __name__ == "__main__":
    main()