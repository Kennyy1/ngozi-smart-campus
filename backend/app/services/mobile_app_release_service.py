from datetime import datetime,timezone
from uuid import UUID
from sqlalchemy import select,update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.mobile_app_release import MobileAppRelease
from app.schemas.mobile_app_release import MobileReleaseUpdate
from app.services.mobile_release_storage import StoredMobileReleaseFile,remove,resolve

class MobileReleaseNotFoundError(Exception):pass
class DuplicateMobileReleaseError(Exception):pass
def public_filename(version:str)->str:return f"ngozi-smart-campus-android-v{version}.apk"
def create(session:Session,*,user_id:UUID,version:str,version_code:int,release_notes:str,stored:StoredMobileReleaseFile)->MobileAppRelease:
    item=MobileAppRelease(platform="android",version=version.strip(),version_code=version_code,filename=public_filename(version.strip()),file_reference=stored.reference,file_size=stored.size,sha256=stored.sha256,release_notes=release_notes.strip(),status="draft",is_latest=False,created_by_user_id=user_id);session.add(item)
    try:session.commit()
    except IntegrityError as error:session.rollback();remove(stored.reference);raise DuplicateMobileReleaseError() from error
    session.refresh(item);return item
def listing(session:Session)->list[MobileAppRelease]:return list(session.scalars(select(MobileAppRelease).order_by(MobileAppRelease.created_at.desc())).all())
def get(session:Session,release_id:UUID)->MobileAppRelease:
    item=session.get(MobileAppRelease,release_id)
    if item is None:raise MobileReleaseNotFoundError()
    return item
def edit(session:Session,release_id:UUID,data:MobileReleaseUpdate)->MobileAppRelease:
    item=get(session,release_id)
    if item.status!="draft":raise ValueError("Only draft releases may be edited")
    item.release_notes=data.release_notes;session.commit();session.refresh(item);return item
def publish(session:Session,release_id:UUID)->MobileAppRelease:
    item=get(session,release_id)
    if item.status=="retired":raise ValueError("Retired releases cannot be published")
    session.execute(update(MobileAppRelease).where(MobileAppRelease.platform==item.platform,MobileAppRelease.id!=item.id).values(is_latest=False))
    item.status="published";item.is_latest=True;item.released_at=datetime.now(timezone.utc);session.commit();session.refresh(item);return item
def retire(session:Session,release_id:UUID)->MobileAppRelease:
    item=get(session,release_id);item.status="retired";item.is_latest=False;session.commit();session.refresh(item);return item
def latest(session:Session)->MobileAppRelease:
    item=session.scalar(select(MobileAppRelease).where(MobileAppRelease.platform=="android",MobileAppRelease.status=="published",MobileAppRelease.is_latest.is_(True)))
    if item is None:raise MobileReleaseNotFoundError()
    return item
def download(session:Session,version:str|None=None):
    if version is None:item=latest(session)
    else:
        item=session.scalar(select(MobileAppRelease).where(MobileAppRelease.platform=="android",MobileAppRelease.version==version,MobileAppRelease.status=="published"))
        if item is None:raise MobileReleaseNotFoundError()
    return item,resolve(item.file_reference)
