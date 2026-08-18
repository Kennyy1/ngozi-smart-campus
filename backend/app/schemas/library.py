from datetime import date, datetime
from enum import StrEnum
from uuid import UUID
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class ItemType(StrEnum): BOOK="book"; EBOOK="ebook"; JOURNAL="journal"; ARTICLE="article"; THESIS="thesis"; REPORT="report"; LECTURE_REFERENCE="lecture_reference"; OTHER="other"
class AccessType(StrEnum): PHYSICAL="physical"; DIGITAL="digital"; HYBRID="hybrid"
class ItemStatus(StrEnum): ACTIVE="active"; INACTIVE="inactive"; ARCHIVED="archived"
class CopyCondition(StrEnum): NEW="new"; GOOD="good"; FAIR="fair"; POOR="poor"; DAMAGED="damaged"
class CopyStatus(StrEnum): AVAILABLE="available"; BORROWED="borrowed"; RESERVED="reserved"; LOST="lost"; DAMAGED="damaged"; WITHDRAWN="withdrawn"

def clean(value:str|None): return None if value is None else " ".join(value.split()) or None
def https_url(value:str|None):
    if value is None:return None
    value=value.strip(); parsed=urlparse(value)
    if parsed.scheme!="https" or not parsed.netloc:raise ValueError("must be a valid HTTPS URL")
    return value

class CategoryCreate(BaseModel):
    name:str=Field(min_length=1,max_length=150);description:str|None=None;parent_id:UUID|None=None;is_active:bool=True
    _name=field_validator("name")(clean)
class CategoryUpdate(BaseModel):
    name:str|None=Field(default=None,min_length=1,max_length=150);description:str|None=None;parent_id:UUID|None=None;is_active:bool|None=None
class CategoryRead(CategoryCreate):
    model_config=ConfigDict(from_attributes=True);id:UUID;created_at:datetime;updated_at:datetime

class AuthorCreate(BaseModel):
    first_name:str|None=Field(default=None,max_length=100);last_name:str|None=Field(default=None,max_length=100);display_name:str=Field(min_length=1,max_length=255)
    _display=field_validator("display_name")(clean)
class AuthorRead(AuthorCreate):
    model_config=ConfigDict(from_attributes=True);id:UUID;created_at:datetime;updated_at:datetime

class LibraryItemCreate(BaseModel):
    title:str=Field(min_length=1,max_length=255);subtitle:str|None=Field(default=None,max_length=255);description:str|None=None;item_type:ItemType;isbn:str|None=Field(default=None,max_length=30);edition:str|None=Field(default=None,max_length=80);publisher:str|None=Field(default=None,max_length=255);publication_year:int|None=Field(default=None,ge=1000,le=9999);language:str=Field(default="English",min_length=1,max_length=80);category_id:UUID|None=None;cover_image_url:str|None=None;access_type:AccessType;status:ItemStatus=ItemStatus.ACTIVE;author_ids:list[UUID]=Field(default_factory=list,max_length=30);external_url:str|None=None
    _title=field_validator("title")(clean);_external=field_validator("external_url")(https_url);_cover=field_validator("cover_image_url")(https_url)
    @model_validator(mode="after")
    def digital_source(self):
        if self.external_url and self.access_type==AccessType.PHYSICAL:raise ValueError("physical items cannot have a digital URL")
        if len(set(self.author_ids))!=len(self.author_ids):raise ValueError("duplicate authors")
        return self
class LibraryItemUpdate(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=255);subtitle:str|None=None;description:str|None=None;item_type:ItemType|None=None;isbn:str|None=None;edition:str|None=None;publisher:str|None=None;publication_year:int|None=Field(default=None,ge=1000,le=9999);language:str|None=None;category_id:UUID|None=None;cover_image_url:str|None=None;access_type:AccessType|None=None;status:ItemStatus|None=None;author_ids:list[UUID]|None=None;external_url:str|None=None
    _external=field_validator("external_url")(https_url);_cover=field_validator("cover_image_url")(https_url)
class LibraryItemRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID;title:str;subtitle:str|None;description:str|None;item_type:ItemType;isbn:str|None;edition:str|None;publisher:str|None;publication_year:int|None;language:str;category_id:UUID|None;category_name:str|None=None;cover_image_url:str|None;access_type:AccessType;status:ItemStatus;source_type:str|None;original_filename:str|None;mime_type:str|None;file_size:int|None;external_url:str|None;authors:list[str]=Field(default_factory=list);available_copies:int=0;total_copies:int=0;created_at:datetime;updated_at:datetime

class CopyCreate(BaseModel):
    accession_number:str=Field(min_length=1,max_length=100);barcode:str|None=Field(default=None,max_length=100);shelf_location:str|None=Field(default=None,max_length=150);acquisition_date:date|None=None;condition:CopyCondition=CopyCondition.GOOD;status:CopyStatus=CopyStatus.AVAILABLE
class CopyUpdate(BaseModel):
    barcode:str|None=None;shelf_location:str|None=None;acquisition_date:date|None=None;condition:CopyCondition|None=None;status:CopyStatus|None=None
class CopyRead(CopyCreate):
    model_config=ConfigDict(from_attributes=True);id:UUID;library_item_id:UUID;created_at:datetime;updated_at:datetime

class LoanCreate(BaseModel):
    copy_id:UUID;borrower_user_id:UUID;due_at:datetime|None=None
class LoanRead(BaseModel):
    id:UUID;title:str;accession_number:str;borrower_name:str|None=None;borrowed_at:datetime;due_at:datetime;returned_at:datetime|None;status:str;is_overdue:bool
class LibraryMetrics(BaseModel):
    total_items:int;active_physical_copies:int;available_copies:int;borrowed_copies:int;overdue_loans:int;digital_resources:int;categories:int
