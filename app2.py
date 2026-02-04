# app.py - نسخة معدلة بدون المستطيلات البيضاء
import streamlit as st
import pandas as pd
import numpy as np
import os
import sqlite3
from datetime import datetime, date
import json
from database import get_db_connection, log_activity

st.set_page_config(
    page_title="نظام مكتب النظام - معهد حي الأمل بقابس",
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
def generate_ref_no(mail_type="incoming"):
    """توليد رقم مرجعي بالتنسيق الجديد"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # الحصول على الشهر والسنة الحالية بالعربية
    current_month = datetime.now().strftime('%m')
    current_year = datetime.now().strftime('%Y')
    
    # تحديد البادئة حسب نوع البريد
    prefix = "و" if mail_type == "incoming" else "ص"
    
    # الحصول على آخر رقم في نفس الشهر والسنة
    cursor.execute(f'''
    SELECT COUNT(*) FROM incoming_mail 
    WHERE reference_no LIKE '{prefix}-____-{current_month}-{current_year}'
    ''' if mail_type == "incoming" else f'''
    SELECT COUNT(*) FROM outgoing_mail 
    WHERE reference_no LIKE '{prefix}-____-{current_month}-{current_year}'
    ''')
    
    count = cursor.fetchone()[0]
    conn.close()
    
    # توليد الرقم بالصيغة الجديدة: و-0001-الشهر-السنة
    return f"{prefix}-{count+1:04d}-{current_month}-{current_year}"

def get_contacts():
    """جلب جميع جهات الاتصال"""
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, code, name, organization, phone, email FROM contacts ORDER BY name", conn)
    conn.close()
    return df

def get_users():
    """جلب جميع المستخدمين"""
    conn = get_db_connection()
    df = pd.read_sql("SELECT id, username, full_name, role FROM users WHERE is_active = 1 ORDER BY full_name", conn)
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

# --- وظائف إدارة الملفات ---
def save_uploaded_file(uploaded_file, mail_type="incoming"):
    """حفظ الملف المرفوع"""
    if uploaded_file is None:
        return None
    
    # إنشاء مجلد لحفظ الملفات إذا لم يكن موجوداً
    upload_dir = f"uploads/{mail_type}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # إنشاء اسم فريد للملف
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_ext = os.path.splitext(uploaded_file.name)[1]
    filename = f"{timestamp}{file_ext}"
    filepath = os.path.join(upload_dir, filename)
    
    # حفظ الملف
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return filepath

# --- شاشة تسجيل الدخول ---
def login_screen():
    """عرض واجهة تسجيل الدخول"""
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # إضافة اسم المؤسسة فقط بدون إطارات
        st.markdown('<div class="institution-title">معهد حي الأمل بقابس</div>', unsafe_allow_html=True)
        st.markdown('<div class="system-title">نظام مكتب النظام</div>', unsafe_allow_html=True)
        
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

# --- واجهة التطبيق الرئيسية ---
def main_interface():
    """الواجهة الرئيسية بعد تسجيل الدخول"""
    
    # --- القائمة الجانبية (العمود الأيمن) ---
    col_sidebar, col_content = st.columns([1, 4], gap="large")
    
    with col_sidebar:
        st.markdown('<div class="sidebar-right-container">', unsafe_allow_html=True)
        
        # عرض اسم المؤسسة فقط (بدون إطارات)
        st.markdown('<div class="institution-title">معهد حي الأمل بقابس</div>', unsafe_allow_html=True)
        st.markdown('<div class="system-title">نظام مكتب النظام</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="sidebar-header">القائمة الرئيسية</div>', unsafe_allow_html=True)
        
        # تعريف الأزرار (مختصرة)
        menu_items = {
            "📊 لوحة القيادة": "لوحة القيادة",
            "📥 البريد الوارد": "البريد الوارد",
            "➕ تسجيل بريد وارد": "تسجيل بريد وارد",
            "📤 البريد الصادر": "البريد الصادر",
            "✏️ إنشاء بريد صادر": "إنشاء بريد صادر",
            "📇 جهات الاتصال": "جهات الاتصال"
        }
        
        for label, page_name in menu_items.items():
            if st.button(label, key=f"btn_{page_name}", use_container_width=True):
                st.session_state.page = page_name
                st.rerun()
        
        # زر تسجيل الخروج
        st.markdown('<div class="sidebar-divider"></div>', unsafe_allow_html=True)
        if st.button("🚪 تسجيل الخروج", use_container_width=True):
            logout_user()
        
        st.markdown('<div class="sidebar-footer">نظام الإدارة v2.0</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # --- محتوى الصفحات (العمود الأيسر) ---
    with col_content:
        # شريط أعلى المحتوى مع معلومات المستخدم
        col_user, col_date = st.columns([2, 1])
        with col_user:
            if st.session_state.user:
                st.markdown(f'<div class="top-user-info">مرحباً <strong>{st.session_state.user["full_name"]}</strong> - {st.session_state.user["role"]}</div>', unsafe_allow_html=True)
        
        with col_date:
            today = datetime.now().strftime("%Y-%m-%d %H:%M")
            st.markdown(f'<div class="top-date">{today}</div>', unsafe_allow_html=True)
        
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
        pending_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE status = 'قيد المعالجة'", conn).iloc[0,0]
        st.metric("قيد المعالجة", pending_mail, delta=None)
    
    with col3:
        total_contacts = pd.read_sql("SELECT COUNT(*) FROM contacts", conn).iloc[0,0]
        st.metric("جهات اتصال", total_contacts, delta=None)
    
    with col4:
        total_mail = pd.read_sql("SELECT COUNT(*) FROM incoming_mail", conn).iloc[0,0]
        st.metric("إجمالي البريد", total_mail, delta=None)
    
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
    
    # آخر 10 بريد صادر
    st.markdown('<div class="card"><h3>آخر البريد الصادر</h3></div>', unsafe_allow_html=True)
    recent_outgoing = pd.read_sql('''
    SELECT reference_no, recipient_name, subject, sent_date, status 
    FROM outgoing_mail 
    ORDER BY sent_date DESC LIMIT 10
    ''', conn)
    
    if not recent_outgoing.empty:
        st.dataframe(recent_outgoing, use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد رسائل صادرة حالياً")
    
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
        # خيارات البحث
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            search_ref = st.text_input("🔍 البحث برقم المرجع")
        with search_col2:
            search_sender = st.text_input("🔍 البحث بالمرسل")
        
        if search_ref:
            df = df[df['reference_no'].str.contains(search_ref, case=False, na=False)]
        if search_sender:
            df = df[df['sender_name'].str.contains(search_sender, case=False, na=False)]
        
        # عرض البيانات مع إجراءات
        for idx, row in df.iterrows():
            with st.expander(f"{row['reference_no']} - {row['subject']} ({row['status']})"):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**المرسل:** {row['sender_name']}")
                    st.markdown(f"**التاريخ:** {row['received_date']}")
                    st.markdown(f"**الأولوية:** {row['priority']}")
                    st.markdown(f"**الحالة:** {row['status']}")
                    st.markdown(f"**الموضوع:** {row['subject']}")
                    
                    if row['notes']:
                        st.markdown(f"**ملاحظات:** {row['notes']}")
                    
                    if row['due_date']:
                        st.markdown(f"**تاريخ الاستحقاق:** {row['due_date']}")
                    
                    # عرض المرفقات إن وجدت
                    if row['attachments']:
                        st.markdown("**المرفقات:**")
                        attachments = json.loads(row['attachments'])
                        for att in attachments:
                            st.markdown(f"- {att}")
                    
                    # عرض البوردرية إن وجدت
                    if row['bordereau']:
                        st.markdown(f"**البوردرية:** {row['bordereau']}")
                
                with col_actions:
                    # زر تغيير الحالة
                    new_status = st.selectbox(
                        "تغيير الحالة",
                        ["جديد", "قيد المعالجة", "مكتمل", "ملغي"],
                        key=f"status_select_{row['id']}"
                    )
                    
                    if st.button("تطبيق", key=f"apply_{row['id']}"):
                        cursor = conn.cursor()
                        cursor.execute("UPDATE incoming_mail SET status = ? WHERE id = ?", 
                                     (new_status, row['id']))
                        conn.commit()
                        log_activity(st.session_state.user['id'], "تحديث حالة بريد وارد", 
                                   f"{row['reference_no']}: {row['status']} → {new_status}")
                        st.success("تم تحديث الحالة")
                        st.rerun()
        
        # عرض ملخص في جدول
        st.markdown("#### ملخص البريد الوارد")
        st.dataframe(df[['reference_no', 'sender_name', 'subject', 'received_date', 'priority', 'status']], 
                    use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد رسائل واردة")
    
    conn.close()

def register_incoming_mail():
    """تسجيل بريد وارد جديد"""
    st.markdown('<div class="card"><h3>تسجيل بريد وارد جديد</h3></div>', unsafe_allow_html=True)
    
    # جلب قائمة جهات الاتصال
    contacts_df = get_contacts()
    contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
    
    with st.form("incoming_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # توليد رقم المرجع الجديد
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no("incoming"))
            
            # اختيار المرسل من جهات الاتصال
            sender_choice = st.selectbox("اختر المرسل", contact_names)
            
            if sender_choice == "--- اختر من جهات الاتصال ---" or (contacts_df.empty and sender_choice == "--- لا توجد جهات اتصال ---"):
                st.warning("الرجاء إضافة جهة اتصال أولاً من صفحة 'جهات الاتصال'")
                sender_name = ""
                sender_id = None
            else:
                sender_name = sender_choice
                # الحصول على ID المرسل
                sender_id = contacts_df[contacts_df['name'] == sender_choice].iloc[0]['id'] if not contacts_df.empty else None
                # عرض معلومات المرسل
                if sender_id:
                    contact_info = get_contact_by_id(sender_id)
                    if contact_info:
                        st.info(f"المؤسسة: {contact_info['organization']} | الهاتف: {contact_info['phone']} | البريد: {contact_info['email']}")
            
            subject = st.text_input("الموضوع *", placeholder="موضوع الرسالة")
        
        with col2:
            priority = st.selectbox("الأولوية", ["عادي", "مهم", "عاجل"])
            category = st.selectbox("التصنيف", ["إداري", "مالي", "فني", "قانوني", "أخرى"])
            received_date = st.date_input("تاريخ الاستلام *", value=date.today())
            due_date = st.date_input("تاريخ الاستحقاق (إن وجد)")
        
        content = st.text_area("محتوى الرسالة", height=150, placeholder="أدخل محتوى الرسالة...")
        notes = st.text_area("ملاحظات إضافية", height=100, placeholder="ملاحظات إضافية...")
        
        # إرفاق الملفات
        st.markdown("### المرفقات")
        col_attach1, col_attach2 = st.columns(2)
        
        with col_attach1:
            uploaded_files = st.file_uploader("إرفاق مستندات", 
                                            type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                            accept_multiple_files=True,
                                            help="يمكنك رفع أكثر من ملف")
        
        with col_attach2:
            bordereau_file = st.file_uploader("إرفاق البوردرية", 
                                            type=['pdf', 'jpg', 'jpeg', 'png'],
                                            help="رفع صورة أو ملف PDF للبوردرية")
        
        submitted = st.form_submit_button("💾 حفظ البريد الوارد", use_container_width=True)
        
        if submitted:
            if not sender_name or not subject:
                st.error("الرجاء ملء الحقول الإلزامية (*)")
            elif sender_choice == "--- اختر من جهات الاتصال ---":
                st.error("الرجاء اختيار المرسل من قائمة جهات الاتصال")
            else:
                conn = get_db_connection()
                cursor = conn.cursor()
                try:
                    # حفظ الملفات المرفوعة
                    attachments = []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "incoming")
                            if filepath:
                                attachments.append(os.path.basename(filepath))
                    
                    bordereau_path = None
                    if bordereau_file:
                        bordereau_path = save_uploaded_file(bordereau_file, "bordereau")
                    
                    cursor.execute('''
                    INSERT INTO incoming_mail 
                    (reference_no, sender_id, sender_name, subject, content, priority, status, 
                     received_date, due_date, category, attachments, bordereau, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, sender_id, sender_name, subject, content, priority, "جديد", 
                          received_date.strftime('%Y-%m-%d'), 
                          due_date.strftime('%Y-%m-%d') if due_date else None, 
                          category, json.dumps(attachments) if attachments else None,
                          os.path.basename(bordereau_path) if bordereau_path else None,
                          notes))
                    
                    conn.commit()
                    log_activity(st.session_state.user['id'], "تسجيل بريد وارد", 
                               f"تم تسجيل بريد جديد: {reference_no}")
                    st.success("✅ تم تسجيل البريد الوارد بنجاح!")
                    st.balloons()
                    
                    # عرض ملخص
                    st.markdown("#### ملخص البريد المسجل")
                    summary_data = {
                        "رقم المرجع": reference_no,
                        "المرسل": sender_name,
                        "الموضوع": subject,
                        "التاريخ": received_date.strftime('%Y-%m-%d'),
                        "الأولوية": priority,
                        "الحالة": "جديد"
                    }
                    st.json(summary_data)
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً!")
                finally:
                    conn.close()

def display_outgoing_mail():
    """عرض البريد الصادر"""
    conn = get_db_connection()
    
    # أزرار التصفية
    col_filters = st.columns(4)
    filters = ["الكل", "مسودة", "مرسل", "مؤرشف"]
    
    for i, filter_name in enumerate(filters):
        with col_filters[i]:
            if st.button(filter_name, key=f"out_filter_{filter_name}", use_container_width=True):
                st.session_state.mail_filter = filter_name
    
    # استعلام حسب التصفية
    if st.session_state.mail_filter == "الكل":
        query = "SELECT * FROM outgoing_mail ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "مسودة":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مسودة' ORDER BY created_at DESC"
    elif st.session_state.mail_filter == "مرسل":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مرسل' ORDER BY sent_date DESC"
    elif st.session_state.mail_filter == "مؤرشف":
        query = "SELECT * FROM outgoing_mail WHERE status = 'مؤرشف' ORDER BY sent_date DESC"
    
    df = pd.read_sql(query, conn)
    
    if not df.empty:
        # خيارات البحث
        search_col1, search_col2 = st.columns(2)
        with search_col1:
            search_ref = st.text_input("🔍 البحث برقم المرجع")
        with search_col2:
            search_recipient = st.text_input("🔍 البحث بالمستلم")
        
        if search_ref:
            df = df[df['reference_no'].str.contains(search_ref, case=False, na=False)]
        if search_recipient:
            df = df[df['recipient_name'].str.contains(search_recipient, case=False, na=False)]
        
        # عرض البيانات مع إجراءات
        for idx, row in df.iterrows():
            with st.expander(f"{row['reference_no']} - {row['subject']} ({row['status']})"):
                col_info, col_actions = st.columns([3, 1])
                
                with col_info:
                    st.markdown(f"**المستلم:** {row['recipient_name']}")
                    st.markdown(f"**التاريخ:** {row['sent_date']}")
                    st.markdown(f"**الأولوية:** {row['priority']}")
                    st.markdown(f"**الحالة:** {row['status']}")
                    st.markdown(f"**الموضوع:** {row['subject']}")
                    
                    if row['notes']:
                        st.markdown(f"**ملاحظات:** {row['notes']}")
                    
                    # عرض المرفقات إن وجدت
                    if row['attachments']:
                        st.markdown("**المرفقات:**")
                        attachments = json.loads(row['attachments'])
                        for att in attachments:
                            st.markdown(f"- {att}")
                    
                    # عرض البوردرية إن وجدت
                    if row['bordereau']:
                        st.markdown(f"**البوردرية:** {row['bordereau']}")
                
                with col_actions:
                    # زر تغيير الحالة
                    new_status = st.selectbox(
                        "تغيير الحالة",
                        ["مسودة", "مرسل", "مؤرشف", "ملغي"],
                        key=f"out_status_select_{row['id']}"
                    )
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if st.button("تطبيق", key=f"out_apply_{row['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("UPDATE outgoing_mail SET status = ? WHERE id = ?", 
                                         (new_status, row['id']))
                            conn.commit()
                            log_activity(st.session_state.user['id'], "تحديث حالة بريد صادر", 
                                       f"{row['reference_no']}: {row['status']} → {new_status}")
                            st.success("تم تحديث الحالة")
                            st.rerun()
                    
                    with col_btn2:
                        if st.button("حذف", key=f"out_delete_{row['id']}"):
                            cursor = conn.cursor()
                            cursor.execute("DELETE FROM outgoing_mail WHERE id = ?", (row['id'],))
                            conn.commit()
                            log_activity(st.session_state.user['id'], "حذف بريد صادر", 
                                       f"{row['reference_no']}")
                            st.success("تم حذف البريد الصادر")
                            st.rerun()
        
        # عرض ملخص في جدول
        st.markdown("#### ملخص البريد الصادر")
        st.dataframe(df[['reference_no', 'recipient_name', 'subject', 'sent_date', 'status']], 
                    use_container_width=True, hide_index=True)
    else:
        st.info("لا توجد رسائل صادرة حالياً")
    
    conn.close()

def create_outgoing_mail():
    """إنشاء بريد صادر جديد"""
    st.markdown('<div class="card"><h3>إنشاء بريد صادر جديد</h3></div>', unsafe_allow_html=True)
    
    # جلب قائمة جهات الاتصال
    contacts_df = get_contacts()
    contact_names = ["--- اختر من جهات الاتصال ---"] + contacts_df['name'].tolist() if not contacts_df.empty else ["--- لا توجد جهات اتصال ---"]
    
    with st.form("outgoing_mail_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            # توليد رقم المرجع الجديد
            reference_no = st.text_input("رقم المرجع", value=generate_ref_no("outgoing"))
            
            # اختيار المستلم من جهات الاتصال
            recipient_choice = st.selectbox("اختر المستلم", contact_names)
            
            if recipient_choice == "--- اختر من جهات الاتصال ---" or (contacts_df.empty and recipient_choice == "--- لا توجد جهات اتصال ---"):
                st.warning("الرجاء إضافة جهة اتصال أولاً من صفحة 'جهات الاتصال'")
                recipient_name = ""
                recipient_id = None
            else:
                recipient_name = recipient_choice
                # الحصول على ID المستلم
                recipient_id = contacts_df[contacts_df['name'] == recipient_choice].iloc[0]['id'] if not contacts_df.empty else None
                # عرض معلومات المستلم
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
        
        # إرفاق الملفات
        st.markdown("### المرفقات")
        col_attach1, col_attach2 = st.columns(2)
        
        with col_attach1:
            uploaded_files = st.file_uploader("إرفاق مستندات", 
                                            type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
                                            accept_multiple_files=True,
                                            help="يمكنك رفع أكثر من ملف")
        
        with col_attach2:
            bordereau_file = st.file_uploader("إرفاق البوردرية", 
                                            type=['pdf', 'jpg', 'jpeg', 'png'],
                                            help="رفع صورة أو ملف PDF للبوردرية")
        
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
                
                try:
                    # حفظ الملفات المرفوعة
                    attachments = []
                    if uploaded_files:
                        for file in uploaded_files:
                            filepath = save_uploaded_file(file, "outgoing")
                            if filepath:
                                attachments.append(os.path.basename(filepath))
                    
                    bordereau_path = None
                    if bordereau_file:
                        bordereau_path = save_uploaded_file(bordereau_file, "bordereau")
                    
                    cursor.execute('''
                    INSERT INTO outgoing_mail 
                    (reference_no, recipient_id, recipient_name, subject, content, priority, 
                     status, sent_date, sent_by, category, attachments, bordereau, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (reference_no, recipient_id, recipient_name, subject, content, priority,
                          final_status, sent_date.strftime('%Y-%m-%d'), 
                          st.session_state.user['id'], category, 
                          json.dumps(attachments) if attachments else None,
                          os.path.basename(bordereau_path) if bordereau_path else None,
                          notes))
                    
                    conn.commit()
                    action = "إرسال بريد صادر" if send_mail else "حفظ مسودة بريد صادر"
                    log_activity(st.session_state.user['id'], action, f"رقم المرجع: {reference_no}")
                    
                    st.success(f"✅ تم {action} بنجاح!")
                    if send_mail:
                        st.balloons()
                    
                    # عرض ملخص
                    st.markdown("#### ملخص البريد المسجل")
                    summary_data = {
                        "رقم المرجع": reference_no,
                        "المستلم": recipient_name,
                        "الموضوع": subject,
                        "التاريخ": sent_date.strftime('%Y-%m-%d'),
                        "الحالة": final_status
                    }
                    st.json(summary_data)
                    
                except sqlite3.IntegrityError:
                    st.error(f"❌ رقم المرجع '{reference_no}' موجود مسبقاً!")
                finally:
                    conn.close()

def display_contacts():
    """عرض وإدارة جهات الاتصال"""
    st.markdown('<div class="card"><h3>إدارة جهات الاتصال</h3></div>', unsafe_allow_html=True)
    
    # زر إضافة جديد
    if st.button("➕ إضافة جهة اتصال جديدة", use_container_width=True, key="add_contact_btn"):
        st.session_state.show_contact_form = True
    
    # عرض نموذج إضافة جهة اتصال إذا كان مفعل
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
                    except sqlite3.Error as e:
                        st.error(f"❌ خطأ في إضافة جهة الاتصال: {str(e)}")
                    finally:
                        conn.close()
                else:
                    st.error("❌ الرجاء إدخال الكود والاسم")
    
    # شريط البحث
    search_term = st.text_input("🔍 بحث في الجهات...", placeholder="كود، اسم، مؤسسة...")
    
    # عرض جهات الاتصال
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
            
            # خيارات متقدمة
            with st.expander("خيارات متقدمة"):
                selected_contact = st.selectbox("اختر جهة اتصال", filtered_contacts['name'].tolist(), key="contact_select")
                if selected_contact:
                    contact_id = filtered_contacts[filtered_contacts['name'] == selected_contact].iloc[0]['id']
                    
                    col_del, col_edit = st.columns(2)
                    with col_del:
                        if st.button("🗑️ حذف الجهة", use_container_width=True, key="delete_contact"):
                            conn = get_db_connection()
                            try:
                                # تحقق إذا كانت الجهة مستخدمة في البريد الوارد أو الصادر
                                mail_incoming = pd.read_sql("SELECT COUNT(*) FROM incoming_mail WHERE sender_id = ?", 
                                                           conn, params=(contact_id,)).iloc[0,0]
                                mail_outgoing = pd.read_sql("SELECT COUNT(*) FROM outgoing_mail WHERE recipient_id = ?", 
                                                           conn, params=(contact_id,)).iloc[0,0]
                                
                                if mail_incoming > 0 or mail_outgoing > 0:
                                    st.warning(f"⚠️ لا يمكن حذف الجهة لأنها مستخدمة في {mail_incoming + mail_outgoing} بريد")
                                else:
                                    conn.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
                                    conn.commit()
                                    st.success("✅ تم حذف الجهة بنجاح")
                                    st.rerun()
                            finally:
                                conn.close()
                    
                    with col_edit:
                        if st.button("✏️ تعديل الجهة", use_container_width=True, key="edit_contact"):
                            # هنا يمكن إضافة وظيفة التعديل
                            st.info("وظيفة التعديل قيد التطوير")
        else:
            st.info("🔍 لا توجد نتائج للبحث")
    else:
        st.info("📭 لا توجد جهات اتصال مسجلة")

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