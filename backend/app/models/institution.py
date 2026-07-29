from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.institution_setting import InstitutionSetting
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
