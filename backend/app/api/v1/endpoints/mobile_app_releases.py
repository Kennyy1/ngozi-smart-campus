from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,File,Form,HTTPException,UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.mobile_app_release import MobileReleaseRead,MobileReleaseUpdate,PublicMobileRelease
from app.services.authentication import AuthenticatedUserContext
from app.services import mobile_app_release_service as service
from app.services import mobile_release_storage as storage

router=APIRouter(prefix="/mobile-app-releases",tags=["Mobile App Releases"])
public_router=APIRouter(prefix="/public/mobile-app/android",tags=["Public Mobile App"])
Admin=Annotated[AuthenticatedUserContext,Depends(require_roles("administrator","system_super_admin"))]
def call(fn,*args,**kwargs):
    try:return fn(*args,**kwargs)
    except (service.MobileReleaseNotFoundError,storage.MobileReleaseFileMissingError) as error:raise HTTPException(404,"Mobile App release not found") from error
    except service.DuplicateMobileReleaseError as error:raise HTTPException(409,"Android version or version code already exists") from error
    except ValueError as error:raise HTTPException(409,str(error)) from error
@router.post("/upload",response_model=MobileReleaseRead,status_code=201)
async def upload(version:Annotated[str,Form(min_length=1,max_length=40)],version_code:Annotated[int,Form(gt=0)],file:Annotated[UploadFile,File()],session:Annotated[Session,Depends(get_db_session)],authenticated:Admin,release_notes:Annotated[str,Form(max_length=10000)]=""):
    try:stored=await storage.store(file)
    except storage.InvalidMobileReleaseFileError as error:raise HTTPException(415,"A non-empty Android APK file is required") from error
    except storage.MobileReleaseFileTooLargeError as error:raise HTTPException(413,"Android APK exceeds the upload limit") from error
    return call(service.create,session,user_id=authenticated.user.id,version=version,version_code=version_code,release_notes=release_notes,stored=stored)
@router.get("",response_model=list[MobileReleaseRead])
def list_releases(session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return service.listing(session)
@router.get("/{release_id}",response_model=MobileReleaseRead)
def get_release(release_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return call(service.get,session,release_id)
@router.patch("/{release_id}",response_model=MobileReleaseRead)
def edit_release(release_id:UUID,request:MobileReleaseUpdate,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return call(service.edit,session,release_id,request)
@router.post("/{release_id}/publish",response_model=MobileReleaseRead)
def publish_release(release_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return call(service.publish,session,release_id)
@router.post("/{release_id}/retire",response_model=MobileReleaseRead)
def retire_release(release_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:Admin):return call(service.retire,session,release_id)
def public(item):return PublicMobileRelease(platform=item.platform,version=item.version,version_code=item.version_code,filename=item.filename,file_size=item.file_size,sha256=item.sha256,release_notes=item.release_notes,released_at=item.released_at,download_url="/api/v1/public/mobile-app/android/download")
@public_router.get("/latest",response_model=PublicMobileRelease)
def latest_release(session:Annotated[Session,Depends(get_db_session)]):return public(call(service.latest,session))
@public_router.get("/download")
def download_latest(session:Annotated[Session,Depends(get_db_session)]):
    item,path=call(service.download,session);return FileResponse(path,media_type="application/vnd.android.package-archive",filename=item.filename)
@public_router.get("/{version}/download")
def download_version(version:str,session:Annotated[Session,Depends(get_db_session)]):
    item,path=call(service.download,session,version);return FileResponse(path,media_type="application/vnd.android.package-archive",filename=item.filename)
