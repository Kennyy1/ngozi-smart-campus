from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment_score import AssessmentScore
    from app.models.assessment_component import AssessmentComponent
    from app.models.attendance_record import AttendanceRecord
    from app.models.class_session import ClassSession
    from app.models.academic_level import AcademicLevel
    from app.models.academic_session import AcademicSession
    from app.models.audit_log import AuditLog
    from app.models.course import Course
    from app.models.course_offering import CourseOffering
    from app.models.course_registration import CourseRegistration
    from app.models.department import Department
    from app.models.faculty import Faculty
    from app.models.institution_setting import InstitutionSetting
    from app.models.lecturer import Lecturer
    from app.models.lecturer_assignment import LecturerAssignment
    from app.models.programme import Programme
    from app.models.semester import Semester
    from app.models.student import Student
    from app.models.user import User
    from app.models.user_role import UserRole
    from app.models.examination import Examination
    from app.models.examination_score import ExaminationScore


class Institution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "institutions"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    domain: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    settings: Mapped[list[InstitutionSetting]] = relationship(
        back_populates="institution",
    )
    users: Mapped[list[User]] = relationship(back_populates="institution")
    user_role_assignments: Mapped[list[UserRole]] = relationship(
        back_populates="institution",
    )
    faculties: Mapped[list[Faculty]] = relationship(
        back_populates="institution",
    )
    departments: Mapped[list[Department]] = relationship(
        back_populates="institution",
    )
    programmes: Mapped[list[Programme]] = relationship(
        back_populates="institution",
    )
    academic_sessions: Mapped[list[AcademicSession]] = relationship(
        back_populates="institution",
    )
    semesters: Mapped[list[Semester]] = relationship(back_populates="institution")
    academic_levels: Mapped[list[AcademicLevel]] = relationship(
        back_populates="institution",
    )
    courses: Mapped[list[Course]] = relationship(back_populates="institution")
    course_offerings: Mapped[list[CourseOffering]] = relationship(
        back_populates="institution",
    )
    course_registrations: Mapped[list[CourseRegistration]] = relationship(
        back_populates="institution",
    )
    students: Mapped[list[Student]] = relationship(
        back_populates="institution",
    )
    lecturers: Mapped[list[Lecturer]] = relationship(
        back_populates="institution",
    )
    lecturer_assignments: Mapped[list[LecturerAssignment]] = relationship(back_populates="institution")
    class_sessions: Mapped[list[ClassSession]] = relationship(back_populates="institution")
    attendance_records: Mapped[list[AttendanceRecord]] = relationship(back_populates="institution")
    assessment_components: Mapped[list[AssessmentComponent]] = relationship(back_populates="institution")
    assessment_scores: Mapped[list[AssessmentScore]] = relationship(back_populates="institution")
    examinations: Mapped[list[Examination]] = relationship(back_populates="institution")
    examination_scores: Mapped[list[ExaminationScore]] = relationship(back_populates="institution")
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="institution",
    )
