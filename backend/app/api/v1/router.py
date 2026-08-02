from fastapi import APIRouter

from app.api.v1.endpoints import (
    academic_levels_router,
    academic_sessions_router,
    auth_router,
    courses_router,
    course_offerings_router,
    course_registrations_router,
    class_sessions_router,
    departments_router,
    faculties_router,
    lecturers_router,
    lecturer_assignments_router,
    programmes_router,
    semesters_router,
    students_router,
)


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(courses_router)
api_router.include_router(course_offerings_router)
api_router.include_router(course_registrations_router)
api_router.include_router(class_sessions_router)
api_router.include_router(academic_levels_router)
api_router.include_router(academic_sessions_router)
api_router.include_router(semesters_router)
api_router.include_router(faculties_router)
api_router.include_router(lecturers_router)
api_router.include_router(lecturer_assignments_router)
api_router.include_router(departments_router)
api_router.include_router(programmes_router)
api_router.include_router(students_router)
