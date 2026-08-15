from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.dependencies import get_current_user, require_roles
from app.api.v1.endpoints import admin_portal, lecturer_portal, student_portal
from app.main import app
from app.models.institution import Institution
from app.models.user import User
from app.services.authentication import AuthenticatedUserContext
from app.services import lecturer_portal_service, student_portal_service


def _context(role: str) -> AuthenticatedUserContext:
    institution = Institution(id=uuid4(), name="Portal University", code="PORTAL", status="active")
    user = User(id=uuid4(), institution_id=institution.id, email=f"{role}@example.edu",
                password_hash="must-never-be-exposed", first_name="Portal", last_name="User",
                is_active=True, is_verified=True)
    return AuthenticatedUserContext(user=user, institution=institution, roles=(role,))


def test_all_portal_routes_are_registered_as_get_only() -> None:
    expected = {
        "/api/v1/student-portal/dashboard", "/api/v1/student-portal/profile",
        "/api/v1/student-portal/courses", "/api/v1/student-portal/attendance",
        "/api/v1/student-portal/results", "/api/v1/student-portal/academic-performance",
        "/api/v1/student-portal/transcript", "/api/v1/student-portal/clearance",
        "/api/v1/student-portal/documents", "/api/v1/lecturer-portal/dashboard",
        "/api/v1/lecturer-portal/courses",
        "/api/v1/lecturer-portal/course-offerings/{course_offering_id}/students",
        "/api/v1/lecturer-portal/course-offerings/{course_offering_id}/attendance",
        "/api/v1/lecturer-portal/course-offerings/{course_offering_id}/assessments",
        "/api/v1/lecturer-portal/course-offerings/{course_offering_id}/examinations",
        "/api/v1/lecturer-portal/course-offerings/{course_offering_id}/results",
        "/api/v1/admin-portal/dashboard", "/api/v1/admin-portal/students/{student_id}/summary",
        "/api/v1/admin-portal/course-offerings/{course_offering_id}/summary",
    }
    routes = {
        f"/api/v1{route.path}": route.methods
        for router in (student_portal.router, lecturer_portal.router, admin_portal.router)
        for route in router.routes
    }
    assert set(routes) == expected
    assert all(methods == {"GET"} for methods in routes.values())


def test_portals_require_authentication() -> None:
    with pytest.raises(HTTPException) as raised:
        get_current_user(None, object())  # type: ignore[arg-type]
    assert raised.value.status_code == 401


def test_student_without_profile_is_safe_404_and_has_no_id_impersonation_parameter() -> None:
    with pytest.raises(student_portal_service.StudentPortalProfileNotFoundError):
        student_portal_service.resolve_student(_EmptySession(), institution_id=uuid4(), user_id=uuid4())  # type: ignore[arg-type]
    route = next(route for route in student_portal.router.routes if route.path.endswith("/profile"))
    parameters = {parameter.name for parameter in (*route.dependant.path_params, *route.dependant.query_params)}
    assert "student_id" not in parameters


def test_lecturer_without_profile_is_safe_404() -> None:
    with pytest.raises(lecturer_portal_service.LecturerPortalProfileNotFoundError):
        lecturer_portal_service.resolve_lecturer(_EmptySession(), institution_id=uuid4(), user_id=uuid4())  # type: ignore[arg-type]


def test_non_admin_cannot_access_admin_portal() -> None:
    with pytest.raises(HTTPException) as raised:
        require_roles("administrator", "system_super_admin")(_context("student"))
    assert raised.value.status_code == 403


class _EmptySession:
    def scalar(self, statement: object) -> None:
        return None
