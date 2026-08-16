from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class RelationshipType(StrEnum):
    FATHER="father"; MOTHER="mother"; GUARDIAN="guardian"; SPONSOR="sponsor"; OTHER="other"

class RelationshipStatus(StrEnum):
    PENDING="pending"; VERIFIED="verified"; SUSPENDED="suspended"; REVOKED="revoked"

class GuardianCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=255)
    address: str | None = None
    emergency_contact: str | None = Field(default=None, max_length=255)

class GuardianUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, max_length=30)
    occupation: str | None = Field(default=None, max_length=255)
    address: str | None = None
    emergency_contact: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

class GuardianRead(BaseModel):
    id: UUID; institution_id: UUID; user_id: UUID
    email: str; first_name: str; last_name: str; phone: str | None
    occupation: str | None; address: str | None; emergency_contact: str | None
    is_active: bool; created_at: datetime; updated_at: datetime

class GuardianStudentCreate(BaseModel):
    guardian_id: UUID; student_id: UUID; relationship_type: RelationshipType
    is_primary: bool = False
    can_view_results: bool = False
    can_view_attendance: bool = False
    can_view_academic_performance: bool = False
    can_view_transcript: bool = False
    can_view_clearance: bool = False

class GuardianStudentUpdate(BaseModel):
    relationship_type: RelationshipType | None = None
    is_primary: bool | None = None
    can_view_results: bool | None = None
    can_view_attendance: bool | None = None
    can_view_academic_performance: bool | None = None
    can_view_transcript: bool | None = None
    can_view_clearance: bool | None = None

class GuardianStudentRead(BaseModel):
    id: UUID; institution_id: UUID; guardian_id: UUID; student_id: UUID
    relationship_type: RelationshipType; is_primary: bool; status: RelationshipStatus
    can_view_results: bool; can_view_attendance: bool; can_view_academic_performance: bool
    can_view_transcript: bool; can_view_clearance: bool
    created_at: datetime; updated_at: datetime

class GuardianChild(BaseModel):
    student_id: UUID; matriculation_number: str; student_name: str
    programme_name: str | None; current_level: str | None; enrollment_status: str
    relationship_type: RelationshipType; is_primary: bool
    can_view_results: bool; can_view_attendance: bool; can_view_academic_performance: bool
    can_view_transcript: bool; can_view_clearance: bool

class GuardianDashboard(BaseModel):
    guardian_id: UUID; guardian_name: str; child_count: int; children: list[GuardianChild]

class ChildOverview(BaseModel):
    child: GuardianChild
    result_count: int | None = None
    attendance_percentage: str | None = None
    current_gpa: str | None = None
    cgpa: str | None = None
    academic_standing: str | None = None
    clearance: dict | None = None

class GuardianClearanceItem(BaseModel):
    clearance_requirement_id: UUID; name: str; code: str; is_mandatory: bool; status: str

class GuardianClearance(BaseModel):
    student_id: UUID; matriculation_number: str; student_name: str
    is_fully_cleared: bool; pending_count: int; requirements: list[GuardianClearanceItem]
