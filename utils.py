# utils.py - وظائف مساعدة محسنة
import os
import json
import io
import hashlib
import secrets
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any
import pandas as pd
from docxtpl import DocxTemplate
from config import config

def hash_password(password: str) -> str:
    """تجزئة كلمة المرور"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_temp_password(length: int = 8) -> str:
    """توليد كلمة مرور مؤقتة"""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%&"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def generate_ref_no(mail_type: str = "incoming", conn=None) -> str:
    """
    توليد رقم مرجعي محسن
    
    Args:
        mail_type: نوع البريد (incoming أو outgoing)
        conn: اتصال قاعدة البيانات (اختياري)
    
    Returns:
        رقم المرجع بالصيغة: و-0001-02-2026
    """
    from database_optimized import get_db_connection
    
    current_month = datetime.now().strftime('%m')
    current_year = datetime.now().strftime('%Y')
    
    prefix = config.MAIL_PREFIX_INCOMING if mail_type == "incoming" else config.MAIL_PREFIX_OUTGOING
    
    # استخدام الاتصال الموجود أو إنشاء واحد جديد
    should_close = False
    if conn is None:
        conn = get_db_connection().__enter__()
        should_close = True
    
    try:
        cursor = conn.cursor()
        table = "incoming_mail" if mail_type == "incoming" else "outgoing_mail"
        
        cursor.execute(f'''
        SELECT MAX(CAST(SUBSTR(reference_no, 3, 4) AS INTEGER)) 
        FROM {table}
        WHERE reference_no LIKE '{prefix}-____-{current_month}-{current_year}'
        ''')
        
        result = cursor.fetchone()[0]
        count = result if result is not None else 0
        
        return f"{prefix}-{count+1:04d}-{current_month}-{current_year}"
    
    except Exception as e:
        print(f"خطأ في توليد رقم المرجع: {e}")
        return f"{prefix}-0001-{current_month}-{current_year}"
    
    finally:
        if should_close:
            conn.close()

def save_uploaded_file(uploaded_file, mail_type: str = "incoming") -> Optional[str]:
    """
    حفظ الملف المرفوع بشكل محسن
    
    Args:
        uploaded_file: الملف المرفوع من Streamlit
        mail_type: نوع البريد
    
    Returns:
        مسار الملف أو None في حالة الفشل
    """
    if uploaded_file is None:
        return None
    
    # التحقق من حجم الملف
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > config.MAX_FILE_SIZE_MB:
        raise ValueError(f"حجم الملف يتجاوز الحد المسموح ({config.MAX_FILE_SIZE_MB} MB)")
    
    # التحقق من امتداد الملف
    file_ext = os.path.splitext(uploaded_file.name)[1][1:].lower()
    if file_ext not in config.ALLOWED_EXTENSIONS:
        raise ValueError(f"نوع الملف غير مسموح. الأنواع المسموحة: {', '.join(config.ALLOWED_EXTENSIONS)}")
    
    upload_dir = f"{config.UPLOAD_DIR}/{mail_type}"
    os.makedirs(upload_dir, exist_ok=True)
    
    # إنشاء اسم فريد للملف
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = "".join(c for c in uploaded_file.name if c.isalnum() or c in "._- ")
    filename = f"{timestamp}_{safe_filename}"
    filepath = os.path.join(upload_dir, filename)
    
    try:
        with open(filepath, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return filepath
    except Exception as e:
        print(f"خطأ في حفظ الملف: {e}")
        return None

def get_attachment_list(attachments_json: Any) -> List[str]:
    """الحصول على قائمة المرفقات من JSON"""
    if not attachments_json:
        return []
    
    if isinstance(attachments_json, str):
        try:
            return json.loads(attachments_json)
        except:
            return []
    elif isinstance(attachments_json, list):
        return attachments_json
    
    return []

def generate_bordereau(mail_data: Dict, contact_info: Optional[Dict] = None) -> Optional[io.BytesIO]:
    """
    إنشاء بوردرية للبريد الصادر
    
    Args:
        mail_data: بيانات البريد
        contact_info: معلومات جهة الاتصال (اختياري)
    
    Returns:
        BytesIO: الملف في الذاكرة أو None
    """
    template_path = "templates/bordereau_template.docx"
    
    if not os.path.exists(template_path):
        print(f"❌ قالب البوردرية غير موجود: {template_path}")
        return None
    
    try:
        doc = DocxTemplate(template_path)
        
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
        
        doc.render(context)
        
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        
        return buffer
    
    except Exception as e:
        print(f"❌ خطأ في إنشاء البوردرية: {e}")
        return None

def export_to_excel(df: pd.DataFrame, sheet_name: str = "البيانات") -> Optional[io.BytesIO]:
    """
    تصدير DataFrame إلى Excel
    
    Args:
        df: البيانات
        sheet_name: اسم الورقة
    
    Returns:
        BytesIO: الملف في الذاكرة أو None
    """
    if df.empty:
        return None
    
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            
            # تحسين عرض الأعمدة
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 50)
        
        output.seek(0)
        return output
    
    except Exception as e:
        print(f"❌ خطأ في التصدير إلى Excel: {e}")
        return None

def format_date(date_str: Any, format: str = "%Y-%m-%d") -> str:
    """تنسيق التاريخ"""
    if not date_str:
        return ""
    
    try:
        if isinstance(date_str, str):
            return date_str
        elif isinstance(date_str, (date, datetime)):
            return date_str.strftime(format)
        return str(date_str)
    except:
        return str(date_str)

def calculate_days_until(target_date: Any) -> Optional[int]:
    """حساب عدد الأيام حتى تاريخ معين"""
    if not target_date:
        return None
    
    try:
        if isinstance(target_date, str):
            target = datetime.strptime(target_date, "%Y-%m-%d").date()
        elif isinstance(target_date, datetime):
            target = target_date.date()
        else:
            target = target_date
        
        today = date.today()
        delta = (target - today).days
        return delta
    except:
        return None

def is_due_soon(due_date: Any, days_threshold: int = None) -> bool:
    """التحقق من قرب تاريخ الاستحقاق"""
    if days_threshold is None:
        days_threshold = config.DUE_DATE_REMINDER_DAYS
    
    days_until = calculate_days_until(due_date)
    if days_until is None:
        return False
    
    return 0 <= days_until <= days_threshold

def sanitize_filename(filename: str) -> str:
    """تنظيف اسم الملف من الأحرف غير المسموحة"""
    return "".join(c for c in filename if c.isalnum() or c in "._- ")

def get_file_size_mb(filepath: str) -> float:
    """الحصول على حجم الملف بالميجابايت"""
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except:
        return 0.0

def validate_email(email: str) -> bool:
    """التحقق من صحة البريد الإلكتروني"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone: str) -> bool:
    """التحقق من صحة رقم الهاتف"""
    import re
    # نمط بسيط لأرقام الهواتف
    pattern = r'^[\d\s\-\+\(\)]{8,}$'
    return bool(re.match(pattern, phone))
