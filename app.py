# app.py - الإصدار المعدل
import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image
import os
import sqlite3
from datetime import datetime, date
import json
from database import get_db_connection, log_activity

st.set_page_config(
    page_title="نظام الإدارة الذكي - مكتب النظام",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# تحميل التنسيقات
with open('style.css', encoding='utf-8') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# إدارة حالة التنقل والمستخدم
if 'page' not in st.session_state:
    st.session_state.page = "لوحة القيادة"
if 'user' not in st.session_state:
    st.session_state.user = None
if 'mail_filter' not in st.session_state:
    st.session_state.mail_filter = "الكل"

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
def generate_ref_no(prefix="IN"):
    """توليد رقم مرجعي"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM incoming_mail WHERE reference_no LIKE '{prefix}%'")
    count = cursor.fetchone()[0]
    conn.close()
    return f"{prefix}{datetime.now().strftime('%Y%m%d')}-{count+1:04d}"

def get_contacts():
    """جلب جميع جهات الاتصال"""
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, name, organization, department, position, phone, email FROM contacts", conn)
    conn.close()
    return df

def get_users():
    """جلب جميع المستخدمين"""
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, username, full_name, role, email, phone FROM users WHERE is_active = 1", conn)
    conn.close()
    return df

# --- شاشة تسجيل الدخول ---
def login_screen():
    """عرض واجهة تسجيل الدخول"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="login-title">نظام مكتب النظام</h1>', unsafe_allow_html=True)
        st.markdown('<p class="login-subtitle">الرجاء تسجيل الدخول للوصول إلى النظام</p>', unsafe_allow_html=True)
        
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
    
    st.markdown('</div>', unsafe_allow_html=True)
    return False

# --- واجهة التطبيق الرئيسية ---
def main_interface():
    """الواجهة الرئيسية بعد تسجيل الدخول"""
    
    # --- القائمة الجانبية (العمود الأيمن) ---
    col_sidebar, col_content = st.columns([1, 4], gap="large")
    
    with col_sidebar:
        st.markdown('<div class="sidebar-right-container">', unsafe_allow_html=True)
        
        if os.path.exists("logo.jpg"):
            st.image(Image.open("logo.jpg"), use_container_width=True)
        
        # معلومات المستخدم
        if st.session_state.user:
            st.markdown(f'<div class="user-info"><strong>{st.session_state.user["full_name"]}</strong><br><small>{st.session_state.user["role"]}</small></div>', unsafe_allow_html=True)
        
        st.markdown('<h2 class="sidebar-header">القائمة الرئيسية</h2>', unsafe_allow_html=True)
        
        # تعريف الأزرار
        menu_items = {
            "📊 لوحة القيادة": "لوحة القيادة",
            "📥 البريد الوارد": "البريد الوارد",
            "➕ تسجيل بريد وارد": "تسجيل بريد وارد",
            "📤 البريد الصادر": "البريد الصادر",
            "✏️ إنشاء بريد صادر": "إنشاء بريد صادر",
            "📇 جهات الاتصال": "جهات الاتصال",
            "👥 المستخدمون": "المستخدمون",
            "📈 الإحصائيات": "الإحصائيات",
            "📋 المتابعات": "المتابعات",
            "⚙️ الإعدادات": "الإعدادات"
        }
        
        for label, page_name in menu_items.items():
            if st.button(label, key=f"btn_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()
        
        # زر تسجيل الخروج
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout_user()
        
        st.markdown('<div class="sidebar-footer">نظام الإدارة v2.0</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # --- محتوى الصفحات (العمود الأيسر) ---
    with col_content:
        # شريط البحث العام
        col_search, col_filter = st.columns([3, 1])
        with col_search:
            search_query = st.text_input("🔍 بحث سريع...", placeholder="ابحث في البريد، الجهات، المستندات...")
        
        with col_filter:
            filter_options = ["الكل", "اليوم", "الأسبوع", "الشهر"]
            selected_filter = st.selectbox("الفترة", filter_options, index=0)
        
        st.markdown(f'<h1 class="page-title">{st.session_state.page}</h1>', unsafe_allow_html=True)
        
        # صفحة لوحة القيادة
        if st.session_state.page == "لوحة القيادة":
            display_dashboard()
        
        # صفحة البريد الوارد
        elif st.session_state.page == "البريد الوارد":
            display_incoming_mail()
        
        # صفحة تسجيل بريد وارد جديد
        elif st.session_state.page == "تسجيل بريد وارد":
            register_incoming_mail()
        
        # صفحة البريد الصادر
        elif st.session_state.page == "البريد الصادر":
            display_outgoing_mail()
        
        # صفحة إنشاء بريد صادر
        elif st.session_state.page == "إنشاء بريد صادر":
            create_outgoing_mail()
        
        # صفحة جهات الاتصال
        elif st.session_state.page == "جهات الاتصال":
            display_contacts()
        
        # صفحة المستخدمين
        elif st.session_state.page == "المستخدمون":
            display_users()
        
        # صفحة الإحصائيات
        elif st.session_state.page == "الإحصائيات":
            display_statistics()
        
        # صفحة المتابعات
        elif st.session_state.page == "المتابعات":
            display_followups()
        
        # صفحة الإعدادات
        elif st.session_state.page == "الإعدادات":
            display_settings()

# --- وظائف عرض الصفحات ---
def display_dashboard():
    """عرض لوحة القيادة"""
    conn = get_db_connection()
    
    # احصائيات سريعة
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        new_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status = 'جديد'", conn).iloc[0,0]
        st.metric("بريد وارد جديد", new_mail, delta=None)
    
    with col2:
        pending_followups = pd.read_sql("SELECT COUNT(*) FROM actions WHERE status = 'معلق'", conn).iloc[0,0]
        st.metric("متابعات معلقة", pending_followups, delta=None)
    
    with col3:
        total_contacts = pd.read_sql("SELECT COUNT(*) FROM contacts", conn).iloc[0,0]
        st.metric("جهات اتصال", total_contacts, delta=None)
    
    with col4:
        total_users = pd.read_sql("SELECT COUNT(*) FROM users WHERE is_active = 1", conn).iloc[0,0]
        st.metric("المستخدمون", total_users, delta=None)
    
    # مخطط البريد الوارد حسب الأولوية
    st.markdown('<div class="card"><h3>البريد الوارد حسب الأولوية</h3></div>', unsafe_allow_html=True)
    priority_data = pd.read_sql('''
    SELECT priority, COUNT(*) as count FROM incoming_mail 
    GROUP BY priority ORDER BY count DESC
    ''', conn)
    
    if not priority_data.empty:
        st.bar_chart(priority_data.set_index('priority'))
    else:
        st.info("لا توجد بيانات للعرض")
    
    # آخر 10 بريد وارد
    st.markdown('<div class="card"><h3>آخر البريد الوارد</h3></div>', unsafe_allow_html=True)
    recent_mail = pd.read_sql('''
    SELECT reference_no, sender_name, subject, received_date, priority, status 
    FROM incoming_mail 
    ORDER BY received_date DESC LIMIT 10
    ''', conn)
    
    if not recent_mail.empty:
        st.dataframe(recent_mail, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد رسائل واردة حالياً")
    
    conn.close()

def display_incoming_mail():
    """عرض البريد الوارد"""
    conn = get_db_connection()
    
    # أزرار التصفية
    col_filters = st.columns(6)
    filters = ["الكل", "جديد", "قيد المعالجة", "مكتمل", "مهم", "عاجل"]
    
    for i, filter_name in enumerate(filters):
        with col_filters[i]:
            if st.button(filter_name, key=f"filter_{filter_name}", use_container_width=True):
                st.session_state.mail_filter = filter_name
    
    # استعلام حسب التصفية
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
    
    df = pd.read_sql(query, conn)
    
    if not df.empty:
        # عرض البيانات مع إجراءات
        for idx, row in df.iterrows():
            with st.expander(f"{row['reference_no']} - {row['subject']}"):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**المرسل:** {row['sender_name']}")
                    st.markdown(f"**التاريخ:** {row['received_date']}")
                    st.markdown(f"**الأولوية:** {row['priority']}")
                    st.markdown(f"**الحالة:** {row['status']}")
                    st.markdown(f"**الموضوع:** {row['subject']}")
                    
                    if row['notes']:
                        st.markdown(f"**ملاحظات:** {row['notes']}")
                
                with col_actions:
                    if st.button("عرض التفاصيل", key=f"view_{row['id']}"):
                        st.session_state.selected_mail = row['id']
                        st.rerun()
                    
                    if st.button("تغيير الحالة", key=f"status_{row['id']}"):
                        st.session_state.edit_mail = row['id']
    
        st.dataframe(df[['reference_no', 'sender_name', 'subject', 'received_date', 'priority', 'status']], 
                    use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد رسائل واردة")
    
    conn.close()

def register_incoming_mail():
    """تسجيل بريد وارد جديد"""
    st.markdown('<div class="card"><h3>تسجيل بريد وارد جديد</h3></div>', unsafe_allow_html=True)
    
    with st.form("incoming_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            sender_name = st.text_input("اسم المرسل *", placeholder="اسم المرسل أو الجهة")
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no())
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
            received_date = st.date_input("تاريخ الاستلام *", value=date.today())
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
            due_date = st.date_input("تاريخ الاستحقاق (إن وجد)")
            
            users_df = get_users()
            assigned_to = st.selectbox("محال إلى", users_df['full_name'].tolist())
        
        content = st.text_area("محتوى الرسالة", height=150, placeholder="أدخل محتوى الرسالة...")
        notes = st.text_area("ملاحظات إضافية", height=100, placeholder="ملاحظات إضافية...")
        
        uploaded_files = st.file_uploader("إرفاق مستندات", type=['pdf', 'doc', 'docx', 'jpg', 'png'], accept_multiple_files=True)
        
        submitted = st.form_submit_button("حفظ البريد الوارد", use_container_width=True)
        
        if submitted:
            if not sender_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            else:
                # الحصول على ID المستخدم المحال إليه
                assigned_user_id = users_df[users_df['full_name'] == assigned_to].iloc[0]['id']
                
                # حفظ الملفات المرفوعة
                attachments = []
                if uploaded_files:
                    for file in uploaded_files:
                        attachments.append(file.name)
                
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    cursor.execute('''
                    INSERT INTO incoming_mail 
                    (reference_no, sender_name, subject, content, priority, status, received_date, 
                     due_date, assigned_to, category, attachments, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, sender_name, subject, content, priority, "جديد", 
                          received_date.strftime('%Y-%m-%d'), due_date.strftime('%Y-%m-%d') if due_date else None, 
                          assigned_user_id, category, json.dumps(attachments), notes))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تسجيل بريد وارد", f"تم تسجيل بريد جديد: {reference_no}")
                    st.success("تم تسجيل البريد الوارد بنجاح!")
                    st.balloons()
                except sqlite3.IntegrityError as e:
                    st.error(f"رقم المرجع '{reference_no}' موجود مسبقاً!")
                finally:
                    conn.close()

def display_outgoing_mail():
    """عرض البريد الصادر"""
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM outgoing_mail ORDER BY sent_date DESC", conn)
    
    if not df.empty:
        st.dataframe(df[['reference_no', 'recipient_name', 'subject', 'sent_date', 'status']], 
                    use_container_width=True, hide_index=True)
        
        # خيارات الإجراءات
        selected_mail = st.selectbox("اختر بريداً للتحكم", df['reference_no'].tolist())
        
        if selected_mail:
            mail_data = df[df['reference_no'] == selected_mail].iloc[0]
            
            col_view, col_edit, col_delete = st.columns(3)
            
            with col_view:
                if st.button("عرض التفاصيل", use_container_width=True):
                    st.json(mail_data.to_dict())
            
            with col_edit:
                if st.button("تعديل", use_container_width=True):
                    st.session_state.edit_outgoing = mail_data['id']
            
            with col_delete:
                if st.button("حذف", use_container_width=True):
                    conn.execute("DELETE FROM outgoing_mail WHERE id = ?", (mail_data['id'],))
                    conn.commit()
                    st.success("تم حذف البريد الصادر")
                    st.rerun()
    else:
        st.info("لا توجد رسائل صادرة حالياً")
    
    conn.close()

def create_outgoing_mail():
    """إنشاء بريد صادر جديد"""
    st.markdown('<div class="card"><h3>إنشاء بريد صادر جديد</h3></div>', unsafe_allow_html=True)
    
    contacts_df = get_contacts()
    
    with st.form("outgoing_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            recipient_type = st.radio("نوع المرسل إليه", ["جهة اتصال مسجلة", "جهة جديدة"])
            
            if recipient_type == "جهة اتصال مسجلة" and not contacts_df.empty:
                recipient = st.selectbox("اختر جهة الاتصال", contacts_df['name'].tolist())
                recipient_id = contacts_df[contacts_df['name'] == recipient].iloc[0]['id']
                recipient_name = recipient
            else:
                recipient_name = st.text_input("اسم الجهة المستلمة")
                recipient_id = None
            
            reference_no = st.text_input("رقم المرجع", value=f"OUT{datetime.now().strftime('%Y%m%d')}-001")
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
            status = st.selectbox("الحالة", ["مسودة", "مرسل", "مؤرشف"])
            sent_date = st.date_input("تاريخ الإرسال", value=date.today())
        
        content = st.text_area("محتوى الرسالة", height=200, placeholder="أدخل محتوى الرسالة...")
        
        col_save, col_send = st.columns(2)
        with col_save:
            save_draft = st.form_submit_button("حفظ مسودة", use_container_width=True)
        
        with col_send:
            send_mail = st.form_submit_button("إرسال البريد", use_container_width=True)
        
        if save_draft or send_mail:
            if not subject:
                st.error("الرجاء إدخال الموضوع")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                final_status = "مرسل" if send_mail else "مسودة"
                
                try:
                    cursor.execute('''
                    INSERT INTO outgoing_mail 
                    (reference_no, recipient_id, recipient_name, subject, content, priority, 
                     status, sent_date, sent_by, category)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, recipient_id, recipient_name, subject, content, priority,
                          final_status, sent_date.strftime('%Y-%m-%d'), st.session_state.user['id'], category))
                    
                    conn.commit()
                    action = "إرسال بريد صادر" if send_mail else "حفظ مسودة بريد صادر"
                    log_activity(st.session_state.user['id'], action, f"رقم المرجع: {reference_no}")
                    
                    st.success(f"تم {action} بنجاح!")
                    if send_mail:
                        st.balloons()
                except sqlite3.IntegrityError:
                    st.error(f"رقم المرجع '{reference_no}' موجود مسبقاً!")
                finally:
                    conn.close()

def display_contacts():
    """عرض وإدارة جهات الاتصال"""
    st.markdown('<div class="card"><h3>إدارة جهات الاتصال</h3></div>', unsafe_allow_html=True)
    
    # زر إضافة جديد
    if st.button("➕ إضافة جهة اتصال جديدة", use_container_width=True):
        with st.form("add_contact_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input("الاسم *")
                organization = st.text_input("المؤسسة")
                department = st.text_input("القسم")
                position = st.text_input("المنصب")
            
            with col2:
                email = st.text_input("البريد الإلكتروني")
                phone = st.text_input("الهاتف")
                mobile = st.text_input("الجوال")
                category = st.selectbox("التصنيف", ["حكومي", "خاص", "أفراد", "أخرى"])
            
            address = st.text_input("العنوان")
            notes = st.text_area("ملاحظات")
            
            if st.form_submit_button("إضافة جهة اتصال"):
                if name:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                    INSERT INTO contacts (name, organization, department, position, 
                    email, phone, mobile, address, notes, category, created_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (name, organization, department, position, email, phone, 
                          mobile, address, notes, category, st.session_state.user['id']))
                    
                    conn.commit()
                    conn.close()
                    st.success(f"تم إضافة جهة الاتصال {name} بنجاح")
                    st.rerun()
    
    # شريط البحث
    search_term = st.text_input("بحث في الجهات...", placeholder="اسم، مؤسسة، قسم...")
    
    # عرض جهات الاتصال
    contacts_df = get_contacts()
    
    if not contacts_df.empty:
        if not search_term:
            filtered_contacts = contacts_df
        else:
            filtered_contacts = contacts_df[
                contacts_df['name'].str.contains(search_term, case=False, na=False) |
                contacts_df['organization'].str.contains(search_term, case=False, na=False) |
                contacts_df['department'].str.contains(search_term, case=False, na=False)
            ]
        
        if not filtered_contacts.empty:
            st.dataframe(filtered_contacts, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد نتائج للبحث")
    else:
        st.info("لا توجد جهات اتصال مسجلة")

def display_users():
    """عرض وإدارة المستخدمين"""
    if st.session_state.user['role'] != 'مدير':
        st.warning("⛔ ليس لديك صلاحية الوصول إلى هذه الصفحة")
        return
    
    st.markdown('<div class="card"><h3>إدارة المستخدمين</h3></div>', unsafe_allow_html=True)
    
    # زر إضافة مستخدم جديد
    if st.button("➕ إضافة مستخدم جديد", use_container_width=True):
        with st.form("add_user_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                new_username = st.text_input("اسم المستخدم")
                new_password = st.text_input("كلمة المرور", type="password")
                full_name = st.text_input("الاسم الكامل")
            
            with col2:
                email = st.text_input("البريد الإلكتروني")
                phone = st.text_input("الهاتف")
                role = st.selectbox("الدور", ["مدير", "مشرف", "موظف", "مراجع"])
            
            if st.form_submit_button("إضافة المستخدم"):
                if new_username and new_password and full_name:
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    try:
                        cursor.execute('''
                        INSERT INTO users (username, password, full_name, role, email, phone)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (new_username, new_password, full_name, role, email, phone))
                        conn.commit()
                        st.success(f"تم إضافة المستخدم {full_name} بنجاح")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(f"اسم المستخدم '{new_username}' موجود مسبقاً!")
                    finally:
                        conn.close()
    
    # عرض قائمة المستخدمين
    users_df = get_users()
    if not users_df.empty:
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        
        # خيارات إدارة المستخدم
        selected_user = st.selectbox("اختر مستخدم للإدارة", users_df['username'].tolist())
        
        if selected_user:
            user_data = users_df[users_df['username'] == selected_user].iloc[0]
            
            col_activate, col_deactivate, col_reset = st.columns(3)
            
            with col_activate:
                if st.button("تفعيل", use_container_width=True):
                    conn = get_db_connection()
                    conn.execute("UPDATE users SET is_active = 1 WHERE id = ?", (user_data['id'],))
                    conn.commit()
                    conn.close()
                    st.success("تم تفعيل المستخدم")
                    st.rerun()
            
            with col_deactivate:
                if st.button("تعطيل", use_container_width=True):
                    conn = get_db_connection()
                    conn.execute("UPDATE users SET is_active = 0 WHERE id = ?", (user_data['id'],))
                    conn.commit()
                    conn.close()
                    st.success("تم تعطيل المستخدم")
                    st.rerun()
            
            with col_reset:
                if st.button("إعادة تعيين كلمة المرور", use_container_width=True):
                    conn = get_db_connection()
                    conn.execute("UPDATE users SET password = '123456' WHERE id = ?", (user_data['id'],))
                    conn.commit()
                    conn.close()
                    st.success("تم إعادة تعيين كلمة المرور إلى 123456")
    else:
        st.info("لا يوجد مستخدمون مسجلون")

def display_statistics():
    """عرض الإحصائيات والرسوم البيانية"""
    conn = get_db_connection()
    
    # مخططات متنوعة
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="card"><h4>البريد الوارد حسب الشهر</h4></div>', unsafe_allow_html=True)
        monthly_data = pd.read_sql('''
        SELECT strftime('%Y-%m', received_date) as month, COUNT(*) as count 
        FROM incoming_mail 
        GROUP BY month ORDER BY month
        ''', conn)
        
        if not monthly_data.empty:
            st.line_chart(monthly_data.set_index('month'))
        else:
            st.info("لا توجد بيانات")
    
    with col2:
        st.markdown('<div class="card"><h4>توزيع المهام على المستخدمين</h4></div>', unsafe_allow_html=True)
        user_tasks = pd.read_sql('''
        SELECT u.full_name, COUNT(i.id) as task_count 
        FROM users u 
        LEFT JOIN incoming_mail i ON u.id = i.assigned_to 
        WHERE u.is_active = 1
        GROUP BY u.id
        ''', conn)
        
        if not user_tasks.empty:
            st.bar_chart(user_tasks.set_index('full_name'))
        else:
            st.info("لا توجد بيانات")
    
    # إحصائيات تفصيلية
    st.markdown('<div class="card"><h4>إحصائيات تفصيلية</h4></div>', unsafe_allow_html=True)
    
    col_stats1, col_stats2, col_stats3 = st.columns(3)
    
    with col_stats1:
        mail_by_priority = pd.read_sql('''
        SELECT priority, COUNT(*) as count FROM incoming_mail GROUP BY priority
        ''', conn)
        st.dataframe(mail_by_priority, use_container_width=True, hide_index=True)
    
    with col_stats2:
        mail_by_status = pd.read_sql('''
        SELECT status, COUNT(*) as count FROM incoming_mail GROUP BY status
        ''', conn)
        st.dataframe(mail_by_status, use_container_width=True, hide_index=True)
    
    with col_stats3:
        contacts_by_category = pd.read_sql('''
        SELECT category, COUNT(*) as count FROM contacts GROUP BY category
        ''', conn)
        st.dataframe(contacts_by_category, use_container_width=True, hide_index=True)
    
    conn.close()

def display_followups():
    """عرض وإدارة المتابعات"""
    st.markdown('<div class="card"><h3>المتابعات والمهام</h3></div>', unsafe_allow_html=True)
    
    conn = get_db_connection()
    
    # إنشاء متابعة جديدة
    with st.expander("➕ إنشاء متابعة جديدة"):
        mail_type = st.radio("نوع البريد", ["وارد", "صادر"])
        mail_id = st.number_input("رقم البريد", min_value=1)
        action_type = st.selectbox("نوع الإجراء", ["متابعة", "رد", "أرشفة", "تحويل", "أخرى"])
        description = st.text_area("وصف الإجراء")
        
        users_df = get_users()
        assigned_to = st.selectbox("مكلف إلى", users_df['full_name'].tolist())
        due_date = st.date_input("تاريخ الاستحقاق", value=date.today())
        
        if st.button("إنشاء المتابعة"):
            assigned_user_id = users_df[users_df['full_name'] == assigned_to].iloc[0]['id']
            
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO actions 
            (mail_id, mail_type, action_type, description, assigned_to, due_date, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (mail_id, "incoming" if mail_type == "وارد" else "outgoing", 
                  action_type, description, assigned_user_id, due_date.strftime('%Y-%m-%d'), st.session_state.user['id']))
            
            conn.commit()
            st.success("تم إنشاء المتابعة بنجاح")
    
    # عرض المتابعات الحالية
    st.markdown('<h4>المتابعات الحالية</h4>', unsafe_allow_html=True)
    
    followups_df = pd.read_sql('''
    SELECT a.*, u.full_name as assigned_user 
    FROM actions a 
    LEFT JOIN users u ON a.assigned_to = u.id 
    WHERE a.status = 'معلق'
    ORDER BY a.due_date
    ''', conn)
    
    if not followups_df.empty:
        for idx, row in followups_df.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"**{row['action_type']}** - {row['description']}")
                    st.markdown(f"مكلف إلى: {row['assigned_user']} | تاريخ الاستحقاق: {row['due_date']}")
                
                with col2:
                    if st.button("إكمال", key=f"complete_{row['id']}"):
                        conn.execute("UPDATE actions SET status = 'مكتمل', completed_date = ? WHERE id = ?", 
                                   (date.today().strftime('%Y-%m-%d'), row['id']))
                        conn.commit()
                        st.rerun()
                
                with col3:
                    if st.button("إلغاء", key=f"cancel_{row['id']}"):
                        conn.execute("UPDATE actions SET status = 'ملغي' WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                
                st.divider()
    else:
        st.info("لا توجد متابعات معلقة حالياً")
    
    conn.close()

def display_settings():
    """عرض صفحة الإعدادات"""
    st.markdown('<div class="card"><h3>إعدادات النظام</h3></div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["عام", "المظهر", "متقدم"])
    
    with tab1:
        language = st.selectbox("لغة الواجهة", ["العربية", "English", "Français"])
        timezone = st.selectbox("المنطقة الزمنية", ["Asia/Riyadh", "UTC", "Europe/Paris", "America/New_York"])
        date_format = st.selectbox("تنسيق التاريخ", ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"])
        
        if st.button("حفظ الإعدادات العامة", use_container_width=True):
            st.success("تم حفظ الإعدادات")
    
    with tab2:
        theme_color = st.color_picker("لون السمة الرئيسي", "#4CAF50")
        font_size = st.slider("حجم الخط", 12, 24, 16)
        dark_mode = st.checkbox("الوضع الداكن")
        
        if st.button("تطبيق التخصيص", use_container_width=True):
            st.success("تم تطبيق الإعدادات")
    
    with tab3:
        st.warning("⚠️ هذه الإعدادات للمستخدمين المتقدمين فقط")
        
        auto_backup = st.checkbox("النسخ الاحتياطي التلقائي")
        backup_interval = st.selectbox("فترة النسخ الاحتياطي", ["يومياً", "أسبوعياً", "شهرياً"])
        
        log_retention = st.number_input("فترة احتفاظ السجلات (أيام)", min_value=30, max_value=365, value=90)
        
        if st.button("تفريغ ذاكرة التخزين المؤقت", use_container_width=True):
            st.cache_data.clear()
            st.success("تم تفريغ الذاكرة المؤقتة")
        
        if st.button("تصدير قاعدة البيانات", use_container_width=True):
            st.info("يتم تنفيذ عملية التصدير...")

# --- التطبيق الرئيسي ---
def main():
    """الدالة الرئيسية للتطبيق"""
    
    # التحقق من حالة المستخدم
    if st.session_state.user is None:
        login_screen()
    else:
        main_interface()

if __name__ == "__main__":
    main()