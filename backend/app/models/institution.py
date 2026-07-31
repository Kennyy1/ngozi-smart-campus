from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.department import Department
    from app.models.faculty import Faculty
    from app.models.institution_setting import InstitutionSetting
    from app.models.lecturer import Lecturer
    from app.models.programme import Programme
    from app.models.student import Student
    from app.models.user import User
    from app.models.user_role import UserRole


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
    students: Mapped[list[Student]] = relationship(
        back_populates="institution",
    )
    lecturers: Mapped[list[Lecturer]] = relationship(
        back_populates="institution",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="institution",
    )
