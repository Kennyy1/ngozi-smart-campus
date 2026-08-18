from __future__ import annotations

from datetime import date, datetime
from uuid import UUID as UUIDType

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class LibraryCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__="library_categories"
    __table_args__=(UniqueConstraint("institution_id","name",name="uq_library_categories_institution_name"),)
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    name:Mapped[str]=mapped_column(String(150),nullable=False)
    description:Mapped[str|None]=mapped_column(Text)
    parent_id:Mapped[UUIDType|None]=mapped_column(UUID(as_uuid=True),ForeignKey("library_categories.id",ondelete="RESTRICT"),index=True)
    is_active:Mapped[bool]=mapped_column(Boolean,nullable=False,default=True,index=True)


class Author(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__="authors"
    __table_args__=(UniqueConstraint("institution_id","display_name",name="uq_authors_institution_display_name"),)
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    first_name:Mapped[str|None]=mapped_column(String(100))
    last_name:Mapped[str|None]=mapped_column(String(100))
    display_name:Mapped[str]=mapped_column(String(255),nullable=False,index=True)


class LibraryItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__="library_items"
    __table_args__=(
        CheckConstraint("item_type IN ('book','ebook','journal','article','thesis','report','lecture_reference','other')",name="library_item_type"),
        CheckConstraint("access_type IN ('physical','digital','hybrid')",name="library_item_access_type"),
        CheckConstraint("status IN ('active','inactive','archived')",name="library_item_status"),
        CheckConstraint("source_type IS NULL OR source_type IN ('uploaded_file','external_url')",name="library_item_source_type"),
        CheckConstraint("publication_year IS NULL OR publication_year BETWEEN 1000 AND 9999",name="library_item_publication_year"),
        UniqueConstraint("institution_id","isbn",name="uq_library_items_institution_isbn"),
    )
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    title:Mapped[str]=mapped_column(String(255),nullable=False,index=True)
    subtitle:Mapped[str|None]=mapped_column(String(255))
    description:Mapped[str|None]=mapped_column(Text)
    item_type:Mapped[str]=mapped_column(String(30),nullable=False,index=True)
    isbn:Mapped[str|None]=mapped_column(String(30),index=True)
    edition:Mapped[str|None]=mapped_column(String(80))
    publisher:Mapped[str|None]=mapped_column(String(255),index=True)
    publication_year:Mapped[int|None]=mapped_column(Integer,index=True)
    language:Mapped[str]=mapped_column(String(80),nullable=False,default="English")
    category_id:Mapped[UUIDType|None]=mapped_column(UUID(as_uuid=True),ForeignKey("library_categories.id",ondelete="RESTRICT"),index=True)
    cover_image_url:Mapped[str|None]=mapped_column(String(2048))
    access_type:Mapped[str]=mapped_column(String(20),nullable=False,index=True)
    status:Mapped[str]=mapped_column(String(20),nullable=False,default="active",index=True)
    created_by_user_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False)
    source_type:Mapped[str|None]=mapped_column(String(30),index=True)
    original_filename:Mapped[str|None]=mapped_column(String(255))
    mime_type:Mapped[str|None]=mapped_column(String(150))
    file_size:Mapped[int|None]=mapped_column(Integer)
    file_reference:Mapped[str|None]=mapped_column(String(500))
    external_url:Mapped[str|None]=mapped_column(String(2048))
    sha256:Mapped[str|None]=mapped_column(String(64))
    uploaded_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))


class LibraryItemAuthor(UUIDPrimaryKeyMixin, Base):
    __tablename__="library_item_authors"
    __table_args__=(UniqueConstraint("library_item_id","author_id",name="uq_library_item_authors_pair"),UniqueConstraint("library_item_id","author_order",name="uq_library_item_authors_order"),CheckConstraint("author_order > 0",name="library_item_author_order"))
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    library_item_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("library_items.id",ondelete="CASCADE"),nullable=False,index=True)
    author_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("authors.id",ondelete="RESTRICT"),nullable=False,index=True)
    author_order:Mapped[int]=mapped_column(Integer,nullable=False)


class LibraryCopy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__="library_copies"
    __table_args__=(UniqueConstraint("institution_id","accession_number",name="uq_library_copies_institution_accession"),UniqueConstraint("institution_id","barcode",name="uq_library_copies_institution_barcode"),CheckConstraint("condition IN ('new','good','fair','poor','damaged')",name="library_copy_condition"),CheckConstraint("status IN ('available','borrowed','reserved','lost','damaged','withdrawn')",name="library_copy_status"))
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    library_item_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("library_items.id",ondelete="CASCADE"),nullable=False,index=True)
    accession_number:Mapped[str]=mapped_column(String(100),nullable=False)
    barcode:Mapped[str|None]=mapped_column(String(100))
    shelf_location:Mapped[str|None]=mapped_column(String(150))
    acquisition_date:Mapped[date|None]=mapped_column(Date)
    condition:Mapped[str]=mapped_column(String(20),nullable=False,default="good")
    status:Mapped[str]=mapped_column(String(20),nullable=False,default="available",index=True)


class LibraryLoan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__="library_loans"
    __table_args__=(CheckConstraint("status IN ('borrowed','returned','overdue','lost')",name="library_loan_status"),CheckConstraint("due_at > borrowed_at",name="library_loan_due_date"),Index("uq_library_loans_active_copy","copy_id",unique=True,postgresql_where=text("returned_at IS NULL AND status IN ('borrowed','overdue')")),)
    institution_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("institutions.id",ondelete="CASCADE"),nullable=False,index=True)
    copy_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("library_copies.id",ondelete="RESTRICT"),nullable=False,index=True)
    borrower_user_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False,index=True)
    borrowed_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    due_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False,index=True)
    returned_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    status:Mapped[str]=mapped_column(String(20),nullable=False,default="borrowed",index=True)
    issued_by_user_id:Mapped[UUIDType]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"),nullable=False)
    returned_to_user_id:Mapped[UUIDType|None]=mapped_column(UUID(as_uuid=True),ForeignKey("users.id",ondelete="RESTRICT"))
