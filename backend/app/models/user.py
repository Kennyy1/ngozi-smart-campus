from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment_score import AssessmentScore
    from app.models.attendance_record import AttendanceRecord
    from app.models.audit_log import AuditLog
    from app.models.institution import Institution
    from app.models.lecturer import Lecturer
    from app.models.student import Student
    from app.models.user_role import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "email",
            name="uq_users_institution_email",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    institution: Mapped[Institution] = relationship(back_populates="users")
    role_assignments: Mapped[list[UserRole]] = relationship(
        back_populates="user",
    )
    student_profile: Mapped[Student | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    lecturer_profile: Mapped[Lecturer | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")
    recorded_attendance_records: Mapped[list[AttendanceRecord]] = relationship(back_populates="recorded_by_user")
    graded_assessment_scores: Mapped[list[AssessmentScore]] = relationship(back_populates="graded_by_user")
