from typing import Annotated
from uuid import UUID
from fastapi import APIRouter,Depends,File,HTTPException,Query,UploadFile
from fastapi.responses import FileResponse,RedirectResponse
from sqlalchemy.orm import Session
from app.api.dependencies import get_db_session,require_roles
from app.schemas.library import *
from app.services.authentication import AuthenticatedUserContext
from app.services import library_service as service
from app.services import library_storage as storage

router=APIRouter(prefix="/library",tags=["Digital Library"])
Member=Annotated[AuthenticatedUserContext,Depends(require_roles("student","lecturer","administrator","system_super_admin","librarian"))]
Admin=Annotated[AuthenticatedUserContext,Depends(require_roles("administrator","system_super_admin","librarian"))]
def call(fn,*a,**kw):
    try:return fn(*a,**kw)
    except service.LibraryNotFound as e:raise HTTPException(404,"Library resource not found") from e
    except service.LibraryForbidden as e:raise HTTPException(403,str(e)) from e
    except service.LibraryConflict as e:raise HTTPException(409,str(e)) from e
@router.get("/catalogue",response_model=list[LibraryItemRead])
def catalogue(session:Annotated[Session,Depends(get_db_session)],auth:Member,q:str|None=None,item_type:ItemType|None=None,category_id:UUID|None=None,access_type:AccessType|None=None,availability:bool|None=None,publication_year:int|None=Query(default=None,ge=1000,le=9999)):return service.catalogue(session,auth.institution.id,q=q,item_type=item_type,category_id=category_id,access_type=access_type,availability=availability,publication_year=publication_year)
@router.get("/catalogue/{item_id}",response_model=LibraryItemRead)
def catalogue_item(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Member):return call(service.get_catalogue_item,session,auth.institution.id,item_id)
@router.get("/my-loans",response_model=list[LoanRead])
def my_loans(session:Annotated[Session,Depends(get_db_session)],auth:Member,view:str="active"):return service.loans(session,auth.institution.id,view=view,borrower_id=auth.user.id,show_borrower=False)
@router.get("/metrics",response_model=LibraryMetrics)
def dashboard_metrics(session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service.metrics(session,auth.institution.id)
@router.post("/categories",response_model=CategoryRead,status_code=201)
def add_category(data:CategoryCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.create_category,session,auth.institution.id,data)
@router.get("/categories",response_model=list[CategoryRead])
def categories(session:Annotated[Session,Depends(get_db_session)],auth:Member):return service.list_categories(session,auth.institution.id,not service.is_admin(auth.roles))
@router.patch("/categories/{category_id}",response_model=CategoryRead)
def edit_category(category_id:UUID,data:CategoryUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.update_category,session,auth.institution.id,category_id,data)
@router.post("/authors",response_model=AuthorRead,status_code=201)
def add_author(data:AuthorCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.create_author,session,auth.institution.id,data)
@router.get("/authors",response_model=list[AuthorRead])
def authors(session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service.list_authors(session,auth.institution.id)
@router.post("/items",response_model=LibraryItemRead,status_code=201)
def add_item(data:LibraryItemCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service._read(session,call(service.create_item,session,auth.institution.id,auth.user.id,data))
@router.get("/items",response_model=list[LibraryItemRead])
def items(session:Annotated[Session,Depends(get_db_session)],auth:Admin,q:str|None=None):return service.catalogue(session,auth.institution.id,q=q,include_inactive=True)
@router.get("/items/{item_id}",response_model=LibraryItemRead)
def admin_item(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.get_catalogue_item,session,auth.institution.id,item_id,True)
@router.patch("/items/{item_id}",response_model=LibraryItemRead)
def edit_item(item_id:UUID,data:LibraryItemUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service._read(session,call(service.update_item,session,auth.institution.id,item_id,data))
@router.post("/items/{item_id}/archive",response_model=LibraryItemRead)
def archive(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service._read(session,call(service.archive_item,session,auth.institution.id,item_id))
@router.post("/items/{item_id}/upload",response_model=LibraryItemRead)
async def upload(item_id:UUID,file:Annotated[UploadFile,File()],session:Annotated[Session,Depends(get_db_session)],auth:Admin):
    try:stored=await storage.store(file)
    except storage.InvalidLibraryFile as e:raise HTTPException(415,"Unsupported or unsafe library file") from e
    except storage.LibraryFileTooLarge as e:raise HTTPException(413,"Library file exceeds upload limit") from e
    try:return service._read(session,call(service.attach_file,session,auth.institution.id,item_id,stored))
    except Exception:storage.remove(stored.reference);raise
@router.get("/items/{item_id}/download")
def download(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Member):
    item,path=call(service.download,session,auth.institution.id,item_id);return FileResponse(path,media_type=item.mime_type or "application/octet-stream",filename=item.original_filename or "library-resource")
@router.get("/items/{item_id}/external")
def external(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Member):
    item=call(service.item,session,auth.institution.id,item_id,True)
    if item.source_type!="external_url" or not item.external_url:raise HTTPException(404,"Library resource not found")
    return RedirectResponse(item.external_url,status_code=307)
@router.post("/items/{item_id}/copies",response_model=CopyRead,status_code=201)
def add_copy(item_id:UUID,data:CopyCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.add_copy,session,auth.institution.id,item_id,data)
@router.get("/items/{item_id}/copies",response_model=list[CopyRead])
def copies(item_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.copies,session,auth.institution.id,item_id)
@router.patch("/copies/{copy_id}",response_model=CopyRead)
def edit_copy(copy_id:UUID,data:CopyUpdate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return call(service.update_copy,session,auth.institution.id,copy_id,data)
@router.post("/loans",response_model=LoanRead,status_code=201)
def issue(data:LoanCreate,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service._loan_read(session,call(service.issue,session,auth.institution.id,auth.user.id,data),True)
@router.post("/loans/{loan_id}/return",response_model=LoanRead)
def return_item(loan_id:UUID,session:Annotated[Session,Depends(get_db_session)],auth:Admin):return service._loan_read(session,call(service.return_loan,session,auth.institution.id,auth.user.id,loan_id),True)
@router.get("/loans",response_model=list[LoanRead])
def loans(session:Annotated[Session,Depends(get_db_session)],auth:Admin,view:str="active",borrower_id:UUID|None=None,item_id:UUID|None=None):return service.loans(session,auth.institution.id,view=view,borrower_id=borrower_id,item_id=item_id)
