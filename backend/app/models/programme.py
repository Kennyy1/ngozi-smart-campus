from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.academic_level import AcademicLevel
    from app.models.course import Course
    from app.models.department import Department
    from app.models.faculty import Faculty
    from app.models.institution import Institution


class Programme(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "programmes"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "code",
            name="uq_programmes_institution_code",
        ),
        UniqueConstraint(
            "department_id",
            "name",
            name="uq_programmes_department_name",
        ),
        CheckConstraint("duration_years > 0", name="programme_duration_years"),
        CheckConstraint(
            "award IN ('BSc', 'BA', 'BEng', 'MSc', 'MBA', 'PGD', 'MPhil', 'PhD')",
            name="programme_award",
        ),
        CheckConstraint(
            "study_mode IN ('FULL_TIME', 'PART_TIME', 'DISTANCE')",
            name="programme_study_mode",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="programme_status",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    faculty_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("faculties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    award: Mapped[str] = mapped_column(String(20), nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False)
    study_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    institution: Mapped[Institution] = relationship(
        back_populates="programmes",
    )
    faculty: Mapped[Faculty] = relationship(back_populates="programmes")
    department: Mapped[Department] = relationship(back_populates="programmes")
    academic_levels: Mapped[list[AcademicLevel]] = relationship(
        back_populates="programme",
    )
    courses: Mapped[list[Course]] = relationship(back_populates="programme")
