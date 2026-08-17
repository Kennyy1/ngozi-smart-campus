from app.api.v1.endpoints.academic_sessions import (
    router as academic_sessions_router,
)
from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.attendance_records import router as attendance_records_router
from app.api.v1.endpoints.attendance_analytics import router as attendance_analytics_router
from app.api.v1.endpoints.courses import router as courses_router
from app.api.v1.endpoints.course_offerings import (
    router as course_offerings_router,
)
from app.api.v1.endpoints.course_registrations import (
    router as course_registrations_router,
)
from app.api.v1.endpoints.class_sessions import router as class_sessions_router
from app.api.v1.endpoints.departments import router as departments_router
from app.api.v1.endpoints.faculties import router as faculties_router
from app.api.v1.endpoints.lecturers import router as lecturers_router
from app.api.v1.endpoints.lecturer_assignments import router as lecturer_assignments_router
from app.api.v1.endpoints.programmes import router as programmes_router
from app.api.v1.endpoints.semesters import router as semesters_router
from app.api.v1.endpoints.students import router as students_router
from app.api.v1.endpoints.assessment_components import router as assessment_components_router
from app.api.v1.endpoints.assessment_scores import router as assessment_scores_router
from app.api.v1.endpoints.examinations import router as examinations_router
from app.api.v1.endpoints.examination_scores import router as examination_scores_router
from app.api.v1.endpoints.result_computation import router as result_computation_router
from app.api.v1.endpoints.results import router as results_router
from app.api.v1.endpoints.academic_performance import router as academic_performance_router
from app.api.v1.endpoints.academic_progression import router as academic_progression_router
from app.api.v1.endpoints.transcripts import router as transcripts_router
from app.api.v1.endpoints.official_transcripts import router as official_transcripts_router
from app.api.v1.endpoints.graduation_eligibility import router as graduation_eligibility_router
from app.api.v1.endpoints.degree_classification import router as degree_classification_router
from app.api.v1.endpoints.graduations import router as graduations_router
from app.api.v1.endpoints.academic_documents import router as academic_documents_router, public_router as public_academic_documents_router
from app.api.v1.endpoints.clearance_requirements import router as clearance_requirements_router
from app.api.v1.endpoints.student_clearances import router as student_clearances_router, student_router as student_clearance_students_router

__all__ = [
    "assessment_components_router",
    "assessment_scores_router",
    "examinations_router",
    "examination_scores_router",
    "result_computation_router",
    "results_router",
    "academic_performance_router",
    "academic_progression_router",
    "transcripts_router",
    "official_transcripts_router",
    "graduation_eligibility_router",
    "degree_classification_router",
    "graduations_router",
    "academic_documents_router",
    "public_academic_documents_router",
    "clearance_requirements_router",
    "student_clearances_router",
    "student_clearance_students_router",
    "academic_levels_router",
    "academic_sessions_router",
    "auth_router",
    "attendance_records_router",
    "attendance_analytics_router",
    "courses_router",
    "course_offerings_router",
    "course_registrations_router",
    "class_sessions_router",
    "departments_router",
    "faculties_router",
    "lecturers_router",
    "lecturer_assignments_router",
    "programmes_router",
    "semesters_router",
    "students_router",
]
from app.api.v1.endpoints.academic_levels import (
    router as academic_levels_router,
)
from app.api.v1.endpoints.student_portal import router as student_portal_router
from app.api.v1.endpoints.lecturer_portal import router as lecturer_portal_router
from app.api.v1.endpoints.admin_portal import router as admin_portal_router
from app.api.v1.endpoints.guardians import router as guardians_router, relationships_router as guardian_student_relationships_router
from app.api.v1.endpoints.guardian_portal import router as guardian_portal_router
from app.api.v1.endpoints.course_materials import router as course_materials_router
from app.api.v1.endpoints.mobile_app_releases import router as mobile_app_releases_router,public_router as public_mobile_app_router

__all__ += ["student_portal_router", "lecturer_portal_router", "admin_portal_router", "guardians_router", "guardian_student_relationships_router", "guardian_portal_router", "course_materials_router", "mobile_app_releases_router", "public_mobile_app_router"]
