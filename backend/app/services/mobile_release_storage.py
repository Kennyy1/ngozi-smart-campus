from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from app.core.config import settings

ALLOWED_MIME_TYPES={"application/vnd.android.package-archive","application/octet-stream","application/zip"}
class InvalidMobileReleaseFileError(Exception):pass
class MobileReleaseFileTooLargeError(Exception):pass
class MobileReleaseFileMissingError(Exception):pass
@dataclass(frozen=True)
class StoredMobileReleaseFile:reference:str;original_filename:str;size:int;sha256:str
def storage_root()->Path:
    root=settings.MOBILE_RELEASE_STORAGE_DIR.expanduser()
    if not root.is_absolute():root=Path.cwd()/root
    return root.resolve()
async def store(upload:UploadFile)->StoredMobileReleaseFile:
    original=Path(upload.filename or "").name
    if not original or Path(original).suffix.lower()!=".apk" or (upload.content_type or "application/octet-stream").lower() not in ALLOWED_MIME_TYPES:raise InvalidMobileReleaseFileError()
    reference=f"{uuid4().hex}.apk";root=storage_root();root.mkdir(parents=True,exist_ok=True);target=root/reference;size=0;digest=sha256()
    try:
        with target.open("xb") as output:
            while chunk:=await upload.read(1024*1024):
                size+=len(chunk)
                if size>settings.MOBILE_RELEASE_MAX_UPLOAD_BYTES:raise MobileReleaseFileTooLargeError()
                digest.update(chunk);output.write(chunk)
        if size==0:raise InvalidMobileReleaseFileError()
    except Exception:target.unlink(missing_ok=True);raise
    finally:await upload.close()
    return StoredMobileReleaseFile(reference,original,size,digest.hexdigest())
def resolve(reference:str)->Path:
    root=storage_root();candidate=(root/reference).resolve()
    if candidate.parent!=root or not candidate.is_file():raise MobileReleaseFileMissingError()
    return candidate
def remove(reference:str|None)->None:
    if not reference:return
    try:resolve(reference).unlink(missing_ok=True)
    except MobileReleaseFileMissingError:pass
