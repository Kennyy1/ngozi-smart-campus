from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.institution import Institution
    from app.models.lecturer_assignment import LecturerAssignment
    from app.models.user import User


class Lecturer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lecturers"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "staff_number",
            name="uq_lecturers_institution_staff_number",
        ),
        UniqueConstraint("user_id", name="uq_lecturers_user_id"),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    staff_number: Mapped[str] = mapped_column(String(100), nullable=False)
    academic_title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    academic_rank: Mapped[str] = mapped_column(String(30), nullable=False)
    employment_status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="active",
    )
    specialization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    employment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    office_location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    institution: Mapped[Institution] = relationship(back_populates="lecturers")
    user: Mapped[User] = relationship(back_populates="lecturer_profile")
    department: Mapped[Department] = relationship(back_populates="lecturers")
    lecturer_assignments: Mapped[list[LecturerAssignment]] = relationship(back_populates="lecturer")
