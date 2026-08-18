from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.academic_level import AcademicLevel
from app.models.announcement import Announcement, AnnouncementRead, AnnouncementTarget
from app.models.course_offering import CourseOffering
from app.models.course_registration import CourseRegistration
from app.models.lecturer import Lecturer
from app.models.lecturer_assignment import LecturerAssignment
from app.models.notification import Notification
from app.models.programme import Programme
from app.models.role import Role
from app.models.student import Student
from app.models.user import User
from app.models.user_role import UserRole


class CommunicationNotFound(Exception): pass
class CommunicationConflict(Exception): pass
class CommunicationForbidden(Exception): pass

TARGET_MODELS={"programme":Programme,"academic_level":AcademicLevel,"course_offering":CourseOffering}
ROLE_AUDIENCES={"students":"student","lecturers":"lecturer","guardians":"guardian","administrators":"admin"}

def _now(): return datetime.now(timezone.utc)

def _validate_targets(session:Session,institution_id:UUID,audience_type:str,target_ids:list[UUID]):
    model=TARGET_MODELS.get(audience_type)
    if model is None:
        if target_ids: raise CommunicationConflict("This audience does not accept targets")
        return
    if not target_ids: raise CommunicationConflict("At least one target is required")
    found=set(session.scalars(select(model.id).where(model.institution_id==institution_id,model.id.in_(target_ids))).all())
    if found != set(target_ids): raise CommunicationForbidden("Invalid audience target")

def _replace_targets(session,announcement,target_ids):
    session.query(AnnouncementTarget).filter(AnnouncementTarget.announcement_id==announcement.id).delete(synchronize_session=False)
    for target_id in target_ids:
        session.add(AnnouncementTarget(institution_id=announcement.institution_id,announcement_id=announcement.id,target_type=announcement.audience_type,target_id=target_id))

def create_announcement(session:Session,*,institution_id:UUID,user_id:UUID,data,status="draft"):
    values=data.model_dump(); target_ids=values.pop("target_ids",[])
    _validate_targets(session,institution_id,values["audience_type"],target_ids)
    announcement=Announcement(institution_id=institution_id,created_by_user_id=user_id,status=status,**values)
    if status=="published": announcement.published_at=_now()
    session.add(announcement); session.flush(); _replace_targets(session,announcement,target_ids)
    if status=="published": _create_publish_notifications(session,announcement)
    session.commit(); session.refresh(announcement); return announcement

def list_admin(session,institution_id):
    return list(session.scalars(select(Announcement).where(Announcement.institution_id==institution_id).order_by(Announcement.created_at.desc())).all())

def get_admin(session,institution_id,announcement_id):
    item=session.scalar(select(Announcement).where(Announcement.id==announcement_id,Announcement.institution_id==institution_id))
    if not item: raise CommunicationNotFound()
    return item

def update_draft(session,*,institution_id,announcement_id,data):
    item=get_admin(session,institution_id,announcement_id)
    if item.status!="draft": raise CommunicationConflict("Only draft announcements can be edited")
    changes=data.model_dump(exclude_unset=True); target_ids=changes.pop("target_ids",None)
    audience=changes.get("audience_type",item.audience_type)
    if target_ids is None:
        target_ids=list(session.scalars(select(AnnouncementTarget.target_id).where(AnnouncementTarget.announcement_id==item.id)).all())
    else: target_ids=[UUID(x) if isinstance(x,str) else x for x in target_ids]
    _validate_targets(session,institution_id,audience,target_ids)
    for key,value in changes.items(): setattr(item,key,value)
    _replace_targets(session,item,target_ids); session.commit(); session.refresh(item); return item

def publish(session,institution_id,announcement_id):
    item=get_admin(session,institution_id,announcement_id)
    if item.status!="draft": raise CommunicationConflict("Only draft announcements can be published")
    item.status="published"; item.published_at=_now(); _create_publish_notifications(session,item); session.commit(); session.refresh(item); return item

def archive(session,institution_id,announcement_id):
    item=get_admin(session,institution_id,announcement_id)
    if item.status=="archived": return item
    item.status="archived"; session.commit(); session.refresh(item); return item

def _target_ids(session,announcement):
    return list(session.scalars(select(AnnouncementTarget.target_id).where(AnnouncementTarget.announcement_id==announcement.id)).all())

def entitled_user_ids(session,announcement):
    inst=announcement.institution_id; audience=announcement.audience_type; targets=_target_ids(session,announcement)
    if audience=="all": return list(session.scalars(select(User.id).where(User.institution_id==inst,User.is_active.is_(True))).all())
    if audience in ROLE_AUDIENCES:
        return list(session.scalars(select(UserRole.user_id).join(Role).join(User).where(User.institution_id==inst,User.is_active.is_(True),Role.name.ilike(ROLE_AUDIENCES[audience]))).all())
    if audience=="programme": return list(session.scalars(select(Student.user_id).where(Student.institution_id==inst,Student.programme_id.in_(targets))).all())
    if audience=="academic_level":
        levels=list(session.execute(select(AcademicLevel.code,AcademicLevel.name).where(AcademicLevel.id.in_(targets),AcademicLevel.institution_id==inst)).all())
        labels={x for row in levels for x in row}
        return list(session.scalars(select(Student.user_id).where(Student.institution_id==inst,Student.current_level.in_(labels))).all())
    if audience=="course_offering":
        return list(session.scalars(select(Student.user_id).join(CourseRegistration,CourseRegistration.student_id==Student.id).where(Student.institution_id==inst,CourseRegistration.course_offering_id.in_(targets),CourseRegistration.status=="active",CourseRegistration.registration_status=="registered")).all())
    return []

def _create_publish_notifications(session,announcement):
    notification_type="course_announcement" if announcement.audience_type=="course_offering" else "announcement"
    for user_id in set(entitled_user_ids(session,announcement)):
        session.add(Notification(institution_id=announcement.institution_id,user_id=user_id,notification_type=notification_type,title=announcement.title,message=announcement.body,reference_type="announcement",reference_id=announcement.id))

def feed(session,*,institution_id,user_id,mode="current"):
    now=_now(); query=select(Announcement).where(Announcement.institution_id==institution_id,Announcement.status=="published")
    if mode=="current": query=query.where(or_(Announcement.expires_at.is_(None),Announcement.expires_at>now))
    items=[a for a in session.scalars(query.order_by(Announcement.published_at.desc())).all() if user_id in set(entitled_user_ids(session,a))]
    reads=set(session.scalars(select(AnnouncementRead.announcement_id).where(AnnouncementRead.user_id==user_id,AnnouncementRead.institution_id==institution_id)).all())
    if mode=="unread": items=[a for a in items if a.id not in reads and (a.expires_at is None or a.expires_at>now)]
    return [(a,a.id in reads) for a in items]

def mark_announcement_read(session,*,institution_id,user_id,announcement_id):
    allowed={a.id for a,_ in feed(session,institution_id=institution_id,user_id=user_id,mode="all")}
    if announcement_id not in allowed: raise CommunicationNotFound()
    record=session.scalar(select(AnnouncementRead).where(AnnouncementRead.announcement_id==announcement_id,AnnouncementRead.user_id==user_id))
    if not record: session.add(AnnouncementRead(institution_id=institution_id,announcement_id=announcement_id,user_id=user_id,read_at=_now()))
    session.commit()

def lecturer_offering(session,institution_id,user_id,offering_id):
    lecturer=session.scalar(select(Lecturer).where(Lecturer.institution_id==institution_id,Lecturer.user_id==user_id))
    if not lecturer: raise CommunicationNotFound()
    assignment=session.scalar(select(LecturerAssignment).where(LecturerAssignment.institution_id==institution_id,LecturerAssignment.lecturer_id==lecturer.id,LecturerAssignment.course_offering_id==offering_id,LecturerAssignment.status=="active"))
    if not assignment: raise CommunicationForbidden("Course Offering is not assigned to this Lecturer")
    return assignment

def lecturer_announcements(session,*,institution_id,user_id,offering_id):
    lecturer_offering(session,institution_id,user_id,offering_id)
    ids=select(AnnouncementTarget.announcement_id).where(AnnouncementTarget.institution_id==institution_id,AnnouncementTarget.target_type=="course_offering",AnnouncementTarget.target_id==offering_id)
    return list(session.scalars(select(Announcement).where(Announcement.institution_id==institution_id,Announcement.id.in_(ids)).order_by(Announcement.created_at.desc())).all())

def notifications(session,institution_id,user_id): return list(session.scalars(select(Notification).where(Notification.institution_id==institution_id,Notification.user_id==user_id).order_by(Notification.created_at.desc())).all())
def unread_count(session,institution_id,user_id): return session.query(Notification).filter(Notification.institution_id==institution_id,Notification.user_id==user_id,Notification.is_read.is_(False)).count()
def mark_notification(session,institution_id,user_id,notification_id):
    item=session.scalar(select(Notification).where(Notification.id==notification_id,Notification.institution_id==institution_id,Notification.user_id==user_id))
    if not item: raise CommunicationNotFound()
    item.is_read=True; item.read_at=item.read_at or _now(); session.commit(); session.refresh(item); return item
def mark_all_notifications(session,institution_id,user_id):
    now=_now(); session.query(Notification).filter(Notification.institution_id==institution_id,Notification.user_id==user_id,Notification.is_read.is_(False)).update({Notification.is_read:True,Notification.read_at:now},synchronize_session=False); session.commit()
