from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from app.core.config import settings

ALLOWED={".pdf":{"application/pdf"},".doc":{"application/msword","application/octet-stream"},".docx":{"application/vnd.openxmlformats-officedocument.wordprocessingml.document","application/octet-stream"},".ppt":{"application/vnd.ms-powerpoint","application/octet-stream"},".pptx":{"application/vnd.openxmlformats-officedocument.presentationml.presentation","application/octet-stream"},".xls":{"application/vnd.ms-excel","application/octet-stream"},".xlsx":{"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","application/octet-stream"},".txt":{"text/plain","application/octet-stream"}}
class InvalidLibraryFile(Exception):pass
class LibraryFileTooLarge(Exception):pass
class LibraryFileMissing(Exception):pass
@dataclass(frozen=True)
class StoredLibraryFile: reference:str;original_filename:str;mime_type:str;size:int;sha256:str
def root():
    value=settings.LIBRARY_RESOURCE_STORAGE_DIR.expanduser()
    if not value.is_absolute():value=Path.cwd()/value
    return value.resolve()
async def store(upload:UploadFile):
    original=Path(upload.filename or "").name;ext=Path(original).suffix.lower();mime=(upload.content_type or "application/octet-stream").lower()
    if not original or ext not in ALLOWED or mime not in ALLOWED[ext]:raise InvalidLibraryFile()
    base=root();base.mkdir(parents=True,exist_ok=True);reference=f"{uuid4().hex}{ext}";target=base/reference;size=0;digest=sha256();head=b""
    try:
        with target.open("xb") as output:
            while chunk:=await upload.read(1024*1024):
                if not head:head=chunk[:8]
                size+=len(chunk)
                if size>settings.LIBRARY_RESOURCE_MAX_UPLOAD_BYTES:raise LibraryFileTooLarge()
                digest.update(chunk);output.write(chunk)
        if size==0 or head.startswith((b"MZ",b"\x7fELF")) or (ext==".pdf" and not head.startswith(b"%PDF-")):raise InvalidLibraryFile()
    except Exception:target.unlink(missing_ok=True);raise
    finally:await upload.close()
    return StoredLibraryFile(reference,original,mime,size,digest.hexdigest())
def resolve(reference:str):
    base=root();path=(base/reference).resolve()
    if path.parent!=base or not path.is_file():raise LibraryFileMissing()
    return path
def remove(reference:str|None):
    if not reference:return
    try:resolve(reference).unlink(missing_ok=True)
    except LibraryFileMissing:pass
