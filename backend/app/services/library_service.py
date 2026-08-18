from datetime import datetime,timedelta,timezone
from uuid import UUID
from sqlalchemy import func,or_,select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.library import Author,LibraryCategory,LibraryCopy,LibraryItem,LibraryItemAuthor,LibraryLoan
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services.library_storage import StoredLibraryFile,resolve

class LibraryNotFound(Exception):pass
class LibraryConflict(Exception):pass
class LibraryForbidden(Exception):pass
ADMIN_ROLES={"administrator","system_super_admin","librarian"};BORROWER_ROLES={"student","lecturer"}
def now():return datetime.now(timezone.utc)
def is_admin(roles):return bool(ADMIN_ROLES&set(roles))
def _commit(session):
    try:session.commit()
    except IntegrityError as e:session.rollback();raise LibraryConflict("Library record conflicts with an existing record") from e
def category(session,institution_id,id):
    x=session.scalar(select(LibraryCategory).where(LibraryCategory.id==id,LibraryCategory.institution_id==institution_id))
    if not x:raise LibraryNotFound()
    return x
def create_category(session,institution_id,data):
    if data.parent_id:category(session,institution_id,data.parent_id)
    x=LibraryCategory(institution_id=institution_id,**data.model_dump());session.add(x);_commit(session);session.refresh(x);return x
def list_categories(session,institution_id,active_only=False):
    q=select(LibraryCategory).where(LibraryCategory.institution_id==institution_id)
    if active_only:q=q.where(LibraryCategory.is_active.is_(True))
    return list(session.scalars(q.order_by(LibraryCategory.name)).all())
def update_category(session,institution_id,id,data):
    x=category(session,institution_id,id);changes=data.model_dump(exclude_unset=True)
    if changes.get("parent_id")==id:raise LibraryConflict("A category cannot be its own parent")
    if changes.get("parent_id"):category(session,institution_id,changes["parent_id"])
    for k,v in changes.items():setattr(x,k,v)
    _commit(session);session.refresh(x);return x
def create_author(session,institution_id,data):
    x=Author(institution_id=institution_id,**data.model_dump());session.add(x);_commit(session);session.refresh(x);return x
def list_authors(session,institution_id):return list(session.scalars(select(Author).where(Author.institution_id==institution_id).order_by(Author.display_name)).all())
def _authors(session,institution_id,ids):
    found=list(session.scalars(select(Author).where(Author.institution_id==institution_id,Author.id.in_(ids))).all()) if ids else []
    if len(found)!=len(set(ids)):raise LibraryForbidden("Invalid author reference")
    return found
def item(session,institution_id,id,active=False):
    q=select(LibraryItem).where(LibraryItem.id==id,LibraryItem.institution_id==institution_id)
    if active:q=q.where(LibraryItem.status=="active")
    x=session.scalar(q)
    if not x:raise LibraryNotFound()
    return x
def _set_authors(session,x,ids):
    _authors(session,x.institution_id,ids);session.query(LibraryItemAuthor).filter(LibraryItemAuthor.library_item_id==x.id).delete(synchronize_session=False)
    for order,author_id in enumerate(ids,1):session.add(LibraryItemAuthor(institution_id=x.institution_id,library_item_id=x.id,author_id=author_id,author_order=order))
def create_item(session,institution_id,user_id,data):
    values=data.model_dump();ids=values.pop("author_ids");external=values.get("external_url")
    if values.get("category_id"):category(session,institution_id,values["category_id"])
    values["source_type"]="external_url" if external else None
    x=LibraryItem(institution_id=institution_id,created_by_user_id=user_id,**values);session.add(x);session.flush();_set_authors(session,x,ids);_commit(session);session.refresh(x);return x
def update_item(session,institution_id,id,data):
    x=item(session,institution_id,id);values=data.model_dump(exclude_unset=True);ids=values.pop("author_ids",None)
    if values.get("category_id"):category(session,institution_id,values["category_id"])
    if "external_url" in values:
        values["source_type"]="external_url" if values["external_url"] else ("uploaded_file" if x.file_reference else None)
    for k,v in values.items():setattr(x,k,v)
    if ids is not None:_set_authors(session,x,ids)
    _commit(session);session.refresh(x);return x
def archive_item(session,institution_id,id):
    x=item(session,institution_id,id);x.status="archived";_commit(session);session.refresh(x);return x
def attach_file(session,institution_id,id,stored:StoredLibraryFile):
    x=item(session,institution_id,id)
    if x.access_type=="physical":raise LibraryConflict("Physical-only items cannot contain a digital file")
    x.source_type="uploaded_file";x.file_reference=stored.reference;x.external_url=None;x.original_filename=stored.original_filename;x.mime_type=stored.mime_type;x.file_size=stored.size;x.sha256=stored.sha256;x.uploaded_at=now();_commit(session);session.refresh(x);return x
def _read(session,x):
    authors=list(session.scalars(select(Author.display_name).join(LibraryItemAuthor,LibraryItemAuthor.author_id==Author.id).where(LibraryItemAuthor.library_item_id==x.id).order_by(LibraryItemAuthor.author_order)).all())
    category_name=session.scalar(select(LibraryCategory.name).where(LibraryCategory.id==x.category_id)) if x.category_id else None
    total=session.query(LibraryCopy).filter(LibraryCopy.library_item_id==x.id).count();available=session.query(LibraryCopy).filter(LibraryCopy.library_item_id==x.id,LibraryCopy.status=="available").count()
    hidden={"institution_id","created_by_user_id","file_reference","sha256","uploaded_at"};result={c.name:getattr(x,c.name) for c in x.__table__.columns if c.name not in hidden};result.update(authors=authors,category_name=category_name,total_copies=total,available_copies=available);return result
def catalogue(session,institution_id,*,q=None,item_type=None,category_id=None,access_type=None,availability=None,publication_year=None,include_inactive=False):
    stmt=select(LibraryItem).where(LibraryItem.institution_id==institution_id)
    if not include_inactive:stmt=stmt.where(LibraryItem.status=="active")
    if item_type:stmt=stmt.where(LibraryItem.item_type==item_type)
    if category_id:stmt=stmt.where(LibraryItem.category_id==category_id)
    if access_type:stmt=stmt.where(LibraryItem.access_type==access_type)
    if publication_year:stmt=stmt.where(LibraryItem.publication_year==publication_year)
    if q:
        term=f"%{q.strip()}%";author_items=select(LibraryItemAuthor.library_item_id).join(Author).where(Author.display_name.ilike(term));category_items=select(LibraryCategory.id).where(LibraryCategory.institution_id==institution_id,LibraryCategory.name.ilike(term));stmt=stmt.where(or_(LibraryItem.title.ilike(term),LibraryItem.isbn.ilike(term),LibraryItem.publisher.ilike(term),LibraryItem.description.ilike(term),LibraryItem.id.in_(author_items),LibraryItem.category_id.in_(category_items)))
    if availability is True:stmt=stmt.where(LibraryItem.id.in_(select(LibraryCopy.library_item_id).where(LibraryCopy.institution_id==institution_id,LibraryCopy.status=="available")))
    return [_read(session,x) for x in session.scalars(stmt.order_by(LibraryItem.title)).all()]
def get_catalogue_item(session,institution_id,id,include_inactive=False):return _read(session,item(session,institution_id,id,active=not include_inactive))
def add_copy(session,institution_id,item_id,data):
    x=item(session,institution_id,item_id)
    if x.access_type=="digital":raise LibraryConflict("Digital-only items cannot have physical copies")
    copy=LibraryCopy(institution_id=institution_id,library_item_id=item_id,**data.model_dump());session.add(copy);_commit(session);session.refresh(copy);return copy
def copies(session,institution_id,item_id):item(session,institution_id,item_id);return list(session.scalars(select(LibraryCopy).where(LibraryCopy.institution_id==institution_id,LibraryCopy.library_item_id==item_id).order_by(LibraryCopy.accession_number)).all())
def update_copy(session,institution_id,id,data):
    x=session.scalar(select(LibraryCopy).where(LibraryCopy.id==id,LibraryCopy.institution_id==institution_id))
    if not x:raise LibraryNotFound()
    for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
    _commit(session);session.refresh(x);return x
def _borrower_roles(session,institution_id,user_id):return set(session.scalars(select(Role.name).join(UserRole,UserRole.role_id==Role.id).where(UserRole.institution_id==institution_id,UserRole.user_id==user_id)).all())
def issue(session,institution_id,actor_id,data):
    borrower=session.scalar(select(User).where(User.id==data.borrower_user_id,User.institution_id==institution_id,User.is_active.is_(True)))
    roles=_borrower_roles(session,institution_id,data.borrower_user_id) if borrower else set()
    permitted=roles&BORROWER_ROLES
    if not borrower or not permitted:raise LibraryForbidden("Borrower is not eligible")
    copy=session.scalar(select(LibraryCopy).where(LibraryCopy.id==data.copy_id,LibraryCopy.institution_id==institution_id).with_for_update())
    if not copy or copy.status!="available":raise LibraryConflict("Library copy is not available")
    book=item(session,institution_id,copy.library_item_id,active=True)
    if book.access_type not in {"physical","hybrid"}:raise LibraryConflict("Item is not borrowable")
    role="lecturer" if "lecturer" in permitted else "student";limit=settings.LIBRARY_LECTURER_LOAN_LIMIT if role=="lecturer" else settings.LIBRARY_STUDENT_LOAN_LIMIT
    active=session.query(LibraryLoan).filter(LibraryLoan.institution_id==institution_id,LibraryLoan.borrower_user_id==borrower.id,LibraryLoan.returned_at.is_(None),LibraryLoan.status.in_(["borrowed","overdue"])).count()
    if active>=limit:raise LibraryConflict("Borrowing limit reached")
    borrowed=now();days=settings.LIBRARY_LECTURER_LOAN_DAYS if role=="lecturer" else settings.LIBRARY_STUDENT_LOAN_DAYS;due=data.due_at or borrowed+timedelta(days=days)
    if due.tzinfo is None:due=due.replace(tzinfo=timezone.utc)
    if due<=borrowed:raise LibraryConflict("Due date must be after issue date")
    loan=LibraryLoan(institution_id=institution_id,copy_id=copy.id,borrower_user_id=borrower.id,borrowed_at=borrowed,due_at=due,status="borrowed",issued_by_user_id=actor_id);copy.status="borrowed";session.add(loan);_commit(session);session.refresh(loan);return loan
def return_loan(session,institution_id,actor_id,id):
    loan=session.scalar(select(LibraryLoan).where(LibraryLoan.id==id,LibraryLoan.institution_id==institution_id).with_for_update())
    if not loan:raise LibraryNotFound()
    if loan.returned_at:raise LibraryConflict("Loan has already been returned")
    copy=session.scalar(select(LibraryCopy).where(LibraryCopy.id==loan.copy_id).with_for_update());loan.returned_at=now();loan.returned_to_user_id=actor_id;loan.status="returned";copy.status="available";_commit(session);session.refresh(loan);return loan
def effective_status(loan,at=None):
    at=at or now()
    if loan.returned_at:return "returned"
    due=loan.due_at if loan.due_at.tzinfo else loan.due_at.replace(tzinfo=timezone.utc)
    return "overdue" if due<at else loan.status
def _loan_read(session,loan,show_borrower=False):
    copy=session.scalar(select(LibraryCopy).where(LibraryCopy.id==loan.copy_id));title=session.scalar(select(LibraryItem.title).where(LibraryItem.id==copy.library_item_id));user=session.scalar(select(User).where(User.id==loan.borrower_user_id));status=effective_status(loan)
    return dict(id=loan.id,title=title,accession_number=copy.accession_number,borrower_name=f"{user.first_name} {user.last_name}" if show_borrower else None,borrowed_at=loan.borrowed_at,due_at=loan.due_at,returned_at=loan.returned_at,status=status,is_overdue=status=="overdue")
def loans(session,institution_id,*,view="active",borrower_id=None,item_id=None,show_borrower=True):
    stmt=select(LibraryLoan).where(LibraryLoan.institution_id==institution_id)
    if borrower_id:stmt=stmt.where(LibraryLoan.borrower_user_id==borrower_id)
    if item_id:stmt=stmt.where(LibraryLoan.copy_id.in_(select(LibraryCopy.id).where(LibraryCopy.library_item_id==item_id)))
    rows=list(session.scalars(stmt.order_by(LibraryLoan.borrowed_at.desc())).all());result=[_loan_read(session,x,show_borrower) for x in rows]
    if view=="active":result=[x for x in result if x["status"] in {"borrowed","overdue"}]
    elif view=="overdue":result=[x for x in result if x["is_overdue"]]
    elif view=="returned":result=[x for x in result if x["status"]=="returned"]
    return result
def download(session,institution_id,id):
    x=item(session,institution_id,id,active=True)
    if x.source_type!="uploaded_file" or not x.file_reference:raise LibraryNotFound()
    return x,resolve(x.file_reference)
def metrics(session,institution_id):
    active_copies=session.query(LibraryCopy).filter(LibraryCopy.institution_id==institution_id,LibraryCopy.status!="withdrawn").count()
    all_loans=list(session.scalars(select(LibraryLoan).where(LibraryLoan.institution_id==institution_id)).all())
    return dict(total_items=session.query(LibraryItem).filter(LibraryItem.institution_id==institution_id).count(),active_physical_copies=active_copies,available_copies=session.query(LibraryCopy).filter(LibraryCopy.institution_id==institution_id,LibraryCopy.status=="available").count(),borrowed_copies=session.query(LibraryCopy).filter(LibraryCopy.institution_id==institution_id,LibraryCopy.status=="borrowed").count(),overdue_loans=sum(effective_status(x)=="overdue" for x in all_loans),digital_resources=session.query(LibraryItem).filter(LibraryItem.institution_id==institution_id,LibraryItem.access_type.in_(["digital","hybrid"]),LibraryItem.status=="active").count(),categories=session.query(LibraryCategory).filter(LibraryCategory.institution_id==institution_id,LibraryCategory.is_active.is_(True)).count())
