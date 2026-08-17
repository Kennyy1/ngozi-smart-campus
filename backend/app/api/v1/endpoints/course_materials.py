from typing import Annotated
from uuid import UUID

from fastapi import APIRouter,Depends,File,Form,HTTPException,Response,UploadFile,status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session,require_roles
from app.schemas.course_material import CourseMaterialCreate,CourseMaterialRead,CourseMaterialType,CourseMaterialUpdate
from app.services.authentication import AuthenticatedUserContext
from app.services import course_material_service as service
from app.services import course_material_storage as storage

router=APIRouter(prefix="/course-materials",tags=["Course Materials"])
User=Annotated[AuthenticatedUserContext,Depends(require_roles("lecturer","student","administrator","system_super_admin"))]
Lecturer=Annotated[AuthenticatedUserContext,Depends(require_roles("lecturer"))]

def call(fn,session,auth,**kw):
    try:return fn(session,institution_id=auth.institution.id,user_id=auth.user.id,roles=auth.roles,**kw)
    except (service.CourseMaterialNotFoundError,storage.CourseMaterialFileMissingError) as error:raise HTTPException(404,"Course Material not found") from error
    except service.DuplicateCourseMaterialError as error:raise HTTPException(409,"Course Material title already exists for Offering") from error

@router.post("",response_model=CourseMaterialRead,status_code=201)
def create(request:CourseMaterialCreate,session:Annotated[Session,Depends(get_db_session)],authenticated:User):return call(service.create,session,authenticated,data=request)

@router.post("/upload",response_model=CourseMaterialRead,status_code=201)
async def upload(course_offering_id:Annotated[UUID,Form()],title:Annotated[str,Form(min_length=1,max_length=255)],material_type:Annotated[CourseMaterialType,Form()],file:Annotated[UploadFile,File()],session:Annotated[Session,Depends(get_db_session)],authenticated:Lecturer,description:Annotated[str|None,Form()]=None):
    try:stored=await storage.store(file)
    except storage.InvalidCourseMaterialFileError as error:raise HTTPException(415,"Unsupported Course Material file type") from error
    except storage.CourseMaterialFileTooLargeError as error:raise HTTPException(413,"Course Material file exceeds the upload limit") from error
    try:return call(service.create_uploaded,session,authenticated,course_offering_id=course_offering_id,title=title,description=description,material_type=material_type.value,stored=stored)
    except Exception:storage.remove(stored.reference);raise

@router.get("",response_model=list[CourseMaterialRead])
def listing(session:Annotated[Session,Depends(get_db_session)],authenticated:User,course_offering_id:UUID|None=None):return call(service.list_items,session,authenticated,course_offering_id=course_offering_id)

@router.get("/{material_id}/download")
def download(material_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:User):
    item,path=call(service.download,session,authenticated,material_id=material_id)
    return FileResponse(path=path,media_type=item.mime_type or "application/octet-stream",filename=item.original_filename or "course-material")

@router.get("/{material_id}",response_model=CourseMaterialRead)
def get(material_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:User):return call(service.get,session,authenticated,material_id=material_id)

@router.patch("/{material_id}",response_model=CourseMaterialRead)
def update(material_id:UUID,request:CourseMaterialUpdate,session:Annotated[Session,Depends(get_db_session)],authenticated:User):return call(service.update,session,authenticated,material_id=material_id,data=request)

@router.post("/{material_id}/publish",response_model=CourseMaterialRead)
def publish(material_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:User):return call(service.publish,session,authenticated,material_id=material_id,value=True)

@router.post("/{material_id}/unpublish",response_model=CourseMaterialRead)
def unpublish(material_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:User):return call(service.publish,session,authenticated,material_id=material_id,value=False)

@router.delete("/{material_id}",status_code=status.HTTP_204_NO_CONTENT)
def delete(material_id:UUID,session:Annotated[Session,Depends(get_db_session)],authenticated:User):call(service.delete,session,authenticated,material_id=material_id);return Response(status_code=204)
