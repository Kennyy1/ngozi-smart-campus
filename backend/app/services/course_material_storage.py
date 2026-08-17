from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


ALLOWED_TYPES={
    ".pdf":{"application/pdf"},
    ".doc":{"application/msword","application/octet-stream"},
    ".docx":{"application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/octet-stream"},
    ".ppt":{"application/vnd.ms-powerpoint","application/octet-stream"},
    ".pptx":{"application/vnd.openxmlformats-officedocument.presentationml.presentation","application/octet-stream"},
    ".xls":{"application/vnd.ms-excel","application/octet-stream"},
    ".xlsx":{"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/octet-stream"},
    ".txt":{"text/plain","application/octet-stream"},
    ".png":{"image/png"},
    ".jpg":{"image/jpeg"},
    ".jpeg":{"image/jpeg"},
}


class InvalidCourseMaterialFileError(Exception):pass
class CourseMaterialFileTooLargeError(Exception):pass
class CourseMaterialFileMissingError(Exception):pass


@dataclass(frozen=True)
class StoredMaterialFile:
    reference:str; original_filename:str; mime_type:str; size:int


def storage_root()->Path:
    root=settings.COURSE_MATERIAL_STORAGE_DIR.expanduser()
    if not root.is_absolute():root=Path.cwd()/root
    return root.resolve()


async def store(upload:UploadFile)->StoredMaterialFile:
    original=Path(upload.filename or "").name
    extension=Path(original).suffix.lower()
    supplied=(upload.content_type or "application/octet-stream").lower()
    if not original or extension not in ALLOWED_TYPES or supplied not in ALLOWED_TYPES[extension]:raise InvalidCourseMaterialFileError()
    reference=f"{uuid4().hex}{extension}";root=storage_root();root.mkdir(parents=True,exist_ok=True);target=root/reference;size=0
    try:
        with target.open("xb") as output:
            while chunk:=await upload.read(1024*1024):
                size+=len(chunk)
                if size>settings.COURSE_MATERIAL_MAX_UPLOAD_BYTES:raise CourseMaterialFileTooLargeError()
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True);raise
    finally:await upload.close()
    return StoredMaterialFile(reference,original,supplied,size)


def resolve(reference:str)->Path:
    root=storage_root();candidate=(root/reference).resolve()
    if candidate.parent!=root or not candidate.is_file():raise CourseMaterialFileMissingError()
    return candidate


def remove(reference:str|None)->None:
    if not reference:return
    try:resolve(reference).unlink(missing_ok=True)
    except CourseMaterialFileMissingError:pass
