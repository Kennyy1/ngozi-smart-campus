from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.faculty import Faculty
    from app.models.institution import Institution
    from app.models.lecturer import Lecturer


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "code",
            name="uq_departments_institution_code",
        ),
        UniqueConstraint(
            "faculty_id",
            "name",
            name="uq_departments_faculty_name",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="department_status",
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
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )

    institution: Mapped[Institution] = relationship(
        back_populates="departments",
    )
    faculty: Mapped[Faculty] = relationship(back_populates="departments")
    lecturers: Mapped[list[Lecturer]] = relationship(
        back_populates="department",
    )
