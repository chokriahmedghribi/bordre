# config.py - إدارة الإعدادات والتكوين
import os
from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class AppConfig:
    """إعدادات التطبيق"""
    # معلومات المؤسسة
    INSTITUTION_NAME: str = "المدرسة الإعدادية حي الأمل قابس"
    SYSTEM_NAME: str = "مكتب الضبط"
    VERSION: str = "2.0"
    
    # إعدادات قاعدة البيانات
    DB_NAME: str = "management.db"
    DB_POOL_SIZE: int = 5
    
    # إعدادات التخزين المؤقت
    CACHE_TTL_CONTACTS: int = 300  # 5 دقائق
    CACHE_TTL_USERS: int = 300     # 5 دقائق
    CACHE_TTL_STATS: int = 60      # دقيقة واحدة
    
    # إعدادات الترقيم
    ITEMS_PER_PAGE: int = 20
    
    # إعدادات الملفات
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_EXTENSIONS: list = None
    
    # إعدادات البريد
    MAIL_PREFIX_INCOMING: str = "و"
    MAIL_PREFIX_OUTGOING: str = "ص"
    
    # إعدادات التنبيهات
    DUE_DATE_REMINDER_DAYS: int = 3
    
    # إعدادات النسخ الاحتياطي
    BACKUP_ENABLED: bool = True
    BACKUP_DIR: str = "backups"
    BACKUP_KEEP_COUNT: int = 10
    
    def __post_init__(self):
        if self.ALLOWED_EXTENSIONS is None:
            self.ALLOWED_EXTENSIONS = ['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png']
        
        # إنشاء المجلدات المطلوبة
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(f"{self.UPLOAD_DIR}/incoming", exist_ok=True)
        os.makedirs(f"{self.UPLOAD_DIR}/outgoing", exist_ok=True)
        os.makedirs(f"{self.UPLOAD_DIR}/bordereau", exist_ok=True)
        if self.BACKUP_ENABLED:
            os.makedirs(self.BACKUP_DIR, exist_ok=True)

# إنشاء مثيل عام للإعدادات
config = AppConfig()

# تعريف الصلاحيات
PERMISSIONS: Dict[str, list] = {
    'admin': ['view', 'add', 'edit', 'delete', 'manage_users', 'export', 'configure_system'],
    'user': ['view', 'add', 'edit', 'export'],
    'viewer': ['view', 'export']
}

# تعريف الحالات والأولويات
MAIL_STATUSES = {
    'incoming': ['جديد', 'قيد المعالجة', 'مكتمل', 'ملغي'],
    'outgoing': ['مسودة', 'مرسل', 'مؤرشف']
}

MAIL_PRIORITIES = ['عادي', 'مهم', 'عاجل']

MAIL_CATEGORIES = ['إداري', 'مالي', 'فني', 'قانوني', 'أخرى']

# ألوان الحالات والأولويات
STATUS_COLORS = {
    'جديد': '#e3f2fd',
    'قيد المعالجة': '#fff3e0',
    'مكتمل': '#e8f5e9',
    'ملغي': '#ffebee',
    'مسودة': '#f5f5f5',
    'مرسل': '#e8eaf6',
    'مؤرشف': '#f3e5f5'
}

PRIORITY_COLORS = {
    'عادي': '#e8f5e9',
    'مهم': '#fff3e0',
    'عاجل': '#ffebee'
}

def get_config() -> AppConfig:
    """الحصول على إعدادات التطبيق"""
    return config

def check_permission(user_role: str, required_permission: str) -> bool:
    """التحقق من صلاحيات المستخدم"""
    if user_role not in PERMISSIONS:
        return False
    return required_permission in PERMISSIONS[user_role]
