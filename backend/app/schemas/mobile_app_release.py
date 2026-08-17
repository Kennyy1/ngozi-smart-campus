from datetime import datetime
from enum import StrEnum
from uuid import UUID
from pydantic import BaseModel,ConfigDict,Field,field_validator

class MobilePlatform(StrEnum):ANDROID="android"
class MobileReleaseStatus(StrEnum):DRAFT="draft";PUBLISHED="published";RETIRED="retired"
class MobileReleaseUpdate(BaseModel):
    model_config=ConfigDict(extra="forbid")
    release_notes:str=Field(max_length=10000)
    @field_validator("release_notes")
    @classmethod
    def clean_notes(cls,value:str)->str:return value.strip()
class MobileReleaseRead(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:UUID;platform:MobilePlatform;version:str;version_code:int;filename:str;file_size:int;sha256:str;release_notes:str;status:MobileReleaseStatus;is_latest:bool;released_at:datetime|None;created_by_user_id:UUID;created_at:datetime;updated_at:datetime
class PublicMobileRelease(BaseModel):
    platform:MobilePlatform;version:str;version_code:int;filename:str;file_size:int;sha256:str;release_notes:str;released_at:datetime;download_url:str
