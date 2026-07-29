from app.models.audit_log import AuditLog
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.institution_setting import InstitutionSetting
from app.models.lecturer import Lecturer
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.models.user_role import UserRole

__all__ = [
    "AuditLog",
    "Department",
    "Faculty",
    "Institution",
    "InstitutionSetting",
    "Lecturer",
    "Role",
    "Student",
    "User",
    "UserRole",
]
