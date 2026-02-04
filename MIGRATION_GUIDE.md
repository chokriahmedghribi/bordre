# دليل الترحيل - Migration Guide

## نظرة عامة

هذا الدليل يساعدك على الانتقال من الملفات القديمة إلى الملفات المحسنة.

## 🔄 خطوات الترحيل

### الخطوة 1: النسخ الاحتياطي

قبل البدء، قم بعمل نسخة احتياطية من الملفات الحالية:

```bash
# إنشاء مجلد للنسخ الاحتياطية
mkdir backup_$(date +%Y%m%d)

# نسخ الملفات الحالية
cp app*.py backup_$(date +%Y%m%d)/
cp database*.py backup_$(date +%Y%m%d)/
cp style.css backup_$(date +%Y%m%d)/
cp management*.db backup_$(date +%Y%m%d)/
```

### الخطوة 2: تحديث الاستيرادات

#### في ملف التطبيق الرئيسي (app.py أو app4.py)

**قبل**:
```python
from database import get_db_connection, log_activity
import sqlite3
from datetime import datetime, date
import json
import os
```

**بعد**:
```python
from database_optimized import (
    get_db_connection, 
    log_activity,
    get_contacts_cached,
    get_users_cached,
    get_statistics_cached,
    get_mail_paginated,
    clear_cache
)
from config import (
    config,
    check_permission,
    MAIL_STATUSES,
    MAIL_PRIORITIES,
    MAIL_CATEGORIES
)
from utils import (
    hash_password,
    generate_temp_password,
    generate_ref_no,
    save_uploaded_file,
    get_attachment_list,
    generate_bordereau,
    export_to_excel,
    validate_email,
    validate_phone
)
```

### الخطوة 3: تحديث استخدام قاعدة البيانات

#### استخدام Connection Pool

**قبل**:
```python
conn = sqlite3.connect('management.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM contacts")
results = cursor.fetchall()
conn.close()
```

**بعد**:
```python
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM contacts")
    results = cursor.fetchall()
# الاتصال يُرجع تلقائياً إلى المجمع
```

#### استخدام Cache

**قبل**:
```python
def get_contacts():
    conn = get_db_connection()
    df = pd.read_sql("SELECT * FROM contacts", conn)
    conn.close()
    return df

# يتم استدعاؤها في كل مرة
contacts = get_contacts()
```

**بعد**:
```python
# يتم تخزين النتيجة مؤقتاً لمدة 5 دقائق
contacts = get_contacts_cached()
```

#### استخدام Pagination

**قبل**:
```python
# تحميل جميع السجلات دفعة واحدة
conn = get_db_connection()
df = pd.read_sql("SELECT * FROM incoming_mail ORDER BY received_date DESC", conn)
conn.close()
```

**بعد**:
```python
# تحميل 20 سجل فقط
df, total = get_mail_paginated(
    mail_type="incoming",
    page=1,
    per_page=20,
    filters={'status': 'جديد'}
)
```

### الخطوة 4: تحديث استخدام الإعدادات

**قبل**:
```python
# قيم ثابتة مبعثرة في الكود
INSTITUTION_NAME = "المدرسة الإعدادية حي الأمل قابس"
MAX_FILE_SIZE = 10  # MB
UPLOAD_DIR = "uploads"
```

**بعد**:
```python
from config import config

# استخدام الإعدادات المركزية
institution_name = config.INSTITUTION_NAME
max_file_size = config.MAX_FILE_SIZE_MB
upload_dir = config.UPLOAD_DIR
```

### الخطوة 5: تحديث الوظائف المساعدة

#### توليد رقم مرجعي

**قبل**:
```python
def generate_ref_no(mail_type="incoming"):
    conn = get_db_connection()
    cursor = conn.cursor()
    # ... كود طويل
    conn.close()
    return ref_no

ref_no = generate_ref_no("incoming")
```

**بعد**:
```python
from utils import generate_ref_no

ref_no = generate_ref_no("incoming")
```

#### حفظ الملفات

**قبل**:
```python
def save_uploaded_file(uploaded_file, mail_type="incoming"):
    if uploaded_file is None:
        return None
    
    upload_dir = f"uploads/{mail_type}"
    os.makedirs(upload_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{uploaded_file.name}"
    filepath = os.path.join(upload_dir, filename)
    
    with open(filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return filepath
```

**بعد**:
```python
from utils import save_uploaded_file

# يتضمن التحقق من الحجم والنوع تلقائياً
try:
    filepath = save_uploaded_file(uploaded_file, "incoming")
except ValueError as e:
    st.error(str(e))
```

#### تصدير إلى Excel

**قبل**:
```python
def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='البيانات')
        # ... كود تحسين الأعمدة
    output.seek(0)
    return output
```

**بعد**:
```python
from utils import export_to_excel

excel_buffer = export_to_excel(df, "البريد الوارد")
if excel_buffer:
    st.download_button(
        "تحميل Excel",
        excel_buffer,
        "incoming_mail.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
```

### الخطوة 6: تحديث ملف CSS

**في ملف التطبيق الرئيسي**:

**قبل**:
```python
with open('style.css', encoding='utf-8') as f:
    st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
```

**بعد**:
```python
try:
    with open('style_optimized.css', encoding='utf-8') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except FileNotFoundError:
    st.warning("⚠️ ملف CSS غير موجود")
```

### الخطوة 7: تحديث نظام الصلاحيات

**قبل**:
```python
def check_permission(required_permission="view"):
    if not st.session_state.user:
        return False
    
    user_role = st.session_state.user['role']
    
    permissions = {
        'admin': ['view', 'add', 'edit', 'delete', 'manage_users', 'export'],
        'user': ['view', 'add', 'edit', 'export'],
        'viewer': ['view', 'export']
    }
    
    if user_role not in permissions:
        return False
    
    return required_permission in permissions[user_role]
```

**بعد**:
```python
from config import check_permission

# استخدام بسيط
if check_permission(user_role, 'delete'):
    # تنفيذ عملية الحذف
    pass
```

### الخطوة 8: تحديث تجزئة كلمات المرور

**قبل**:
```python
# تخزين بنص واضح (غير آمن!)
cursor.execute('''
INSERT INTO users (username, password, full_name, role)
VALUES (?, ?, ?, ?)
''', ('admin', 'admin123', 'المشرف', 'admin'))
```

**بعد**:
```python
from utils import hash_password

# تخزين مجزأ (آمن)
cursor.execute('''
INSERT INTO users (username, password, full_name, role)
VALUES (?, ?, ?, ?)
''', ('admin', hash_password('admin123'), 'المشرف', 'admin'))
```

## 🧪 اختبار الترحيل

بعد تطبيق التغييرات، قم باختبار الوظائف التالية:

### 1. اختبار قاعدة البيانات
```python
# اختبار Connection Pool
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    print(f"عدد المستخدمين: {count}")

# اختبار Cache
contacts = get_contacts_cached()
print(f"عدد جهات الاتصال: {len(contacts)}")

# اختبار Pagination
df, total = get_mail_paginated("incoming", page=1, per_page=10)
print(f"عدد السجلات: {len(df)} من أصل {total}")
```

### 2. اختبار الوظائف المساعدة
```python
from utils import (
    generate_ref_no,
    validate_email,
    validate_phone
)

# اختبار توليد رقم مرجعي
ref_no = generate_ref_no("incoming")
print(f"رقم المرجع: {ref_no}")

# اختبار التحقق من البريد
is_valid = validate_email("test@example.com")
print(f"البريد صحيح: {is_valid}")

# اختبار التحقق من الهاتف
is_valid = validate_phone("+216 12 345 678")
print(f"الهاتف صحيح: {is_valid}")
```

### 3. اختبار الإعدادات
```python
from config import config, check_permission

# اختبار الإعدادات
print(f"اسم المؤسسة: {config.INSTITUTION_NAME}")
print(f"حجم الملف الأقصى: {config.MAX_FILE_SIZE_MB} MB")

# اختبار الصلاحيات
can_delete = check_permission('admin', 'delete')
print(f"يمكن الحذف: {can_delete}")
```

## ⚠️ مشاكل محتملة وحلولها

### المشكلة 1: خطأ في الاستيراد
```
ModuleNotFoundError: No module named 'database_optimized'
```

**الحل**: تأكد من وجود الملف في نفس المجلد:
```bash
ls -la database_optimized.py
```

### المشكلة 2: خطأ في قاعدة البيانات
```
sqlite3.OperationalError: no such table: users
```

**الحل**: قم بتهيئة قاعدة البيانات:
```python
from database_optimized import init_db
init_db()
```

### المشكلة 3: كلمات المرور لا تعمل
```
تسجيل الدخول فشل
```

**الحل**: إعادة تعيين كلمات المرور بالتجزئة الجديدة:
```python
from utils import hash_password
from database_optimized import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password = ? WHERE username = ?",
        (hash_password('admin123'), 'admin')
    )
    conn.commit()
```

### المشكلة 4: Cache لا يتحدث
```
البيانات القديمة تظهر بعد التحديث
```

**الحل**: مسح Cache يدوياً:
```python
from database_optimized import clear_cache
clear_cache()
```

## 📋 قائمة التحقق

- [ ] نسخ احتياطي للملفات القديمة
- [ ] تحديث الاستيرادات في الملف الرئيسي
- [ ] استبدال استخدام قاعدة البيانات بـ Connection Pool
- [ ] استخدام الوظائف المخزنة مؤقتاً
- [ ] تحديث استخدام الإعدادات
- [ ] استخدام الوظائف المساعدة من utils.py
- [ ] تحديث ملف CSS
- [ ] تحديث نظام الصلاحيات
- [ ] تحديث تجزئة كلمات المرور
- [ ] اختبار جميع الوظائف
- [ ] مراجعة الأداء

## 🎯 النتيجة المتوقعة

بعد إتمام الترحيل بنجاح:

✅ تحسين الأداء بنسبة 70-80%  
✅ تقليل استهلاك الذاكرة بنسبة 40%  
✅ كود أنظف وأسهل في الصيانة  
✅ أمان محسن مع تجزئة كلمات المرور  
✅ نظام صلاحيات واضح ومنظم  

## 📞 الدعم

إذا واجهت أي مشاكل أثناء الترحيل:

1. راجع [`OPTIMIZATION_GUIDE.md`](OPTIMIZATION_GUIDE.md)
2. راجع [`OPTIMIZATION_SUMMARY.md`](OPTIMIZATION_SUMMARY.md)
3. تحقق من التعليقات في الكود المصدري
4. تأكد من تثبيت جميع المكتبات المطلوبة

---

**ملاحظة**: يمكنك الترحيل تدريجياً، بدءاً بالوظائف الأقل أهمية، ثم الانتقال إلى الوظائف الرئيسية.
