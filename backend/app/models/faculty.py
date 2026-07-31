from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID as UUIDType

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.department import Department
    from app.models.institution import Institution
    from app.models.programme import Programme


class Faculty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "faculties"
    __table_args__ = (
        UniqueConstraint(
            "institution_id",
            "code",
            name="uq_faculties_institution_code",
        ),
        UniqueConstraint(
            "institution_id",
            "name",
            name="uq_faculties_institution_name",
        ),
        CheckConstraint(
            "status IN ('active', 'inactive')",
            name="faculty_status",
        ),
    )

    institution_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("institutions.id", ondelete="CASCADE"),
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

    institution: Mapped[Institution] = relationship(back_populates="faculties")
    departments: Mapped[list[Department]] = relationship(
        back_populates="faculty",
    )
    programmes: Mapped[list[Programme]] = relationship(
        back_populates="faculty",
    )
