from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.academic_level import AcademicLevel
    from app.models.department import Department
    from app.models.institution import Institution
    from app.models.programme import Programme


class Course(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "code",
            name="uq_courses_institution_code",
        ),
        UniqueConstraint(
            "programme_id",
            "academic_level_id",
            "title",
            name="uq_courses_programme_level_title",
        ),
        CheckConstraint("credit_units > 0", name="course_credit_units"),
        CheckConstraint(
            "course_type IN ('compulsory', 'elective', 'required', 'general')",
            name="course_type",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="course_status",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    programme_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("programmes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    academic_level_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("academic_levels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    credit_units: Mapped[int] = mapped_column(Integer, nullable=False)
    course_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    institution: Mapped[Institution] = relationship(back_populates="courses")
    department: Mapped[Department] = relationship(back_populates="courses")
    programme: Mapped[Programme] = relationship(back_populates="courses")
    academic_level: Mapped[AcademicLevel] = relationship(back_populates="courses")
