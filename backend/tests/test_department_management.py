from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import CheckConstraint
from sqlalchemy.exc import IntegrityError

from app.api import dependencies
from app.api.v1.endpoints import departments
from app.main import app
from app.models.department import Department
from app.models.faculty import Faculty
from app.models.institution import Institution
from app.models.user import User
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.services import department_service
from app.services.authentication import AuthenticatedUserContext


class FakeScalarResult:
    def __init__(self, values: list[Department]) -> None:
        self.values = values

    def all(self) -> list[Department]:
        return self.values


class FakeSession:
    def __init__(self, *scalar_results: object) -> None:
        self.scalar_results = list(scalar_results)
        self.added: list[object] = []
        self.statements: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    def scalar(self, statement: object) -> object:
        self.statements.append(statement)
        if not self.scalar_results:
            return None
        return self.scalar_results.pop(0)

    def scalars(self, statement: object) -> FakeScalarResult:
        self.statements.append(statement)
        values = self.scalar_results.pop(0) if self.scalar_results else []
        return FakeScalarResult(values)  # type: ignore[arg-type]

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def refresh(self, _: object) -> None:
        return None


def _context(institution_id: UUID | None = None) -> AuthenticatedUserContext:
    institution = Institution(
        id=institution_id or uuid4(),
        name="Test University",
        code=f"TEST-{uuid4()}",
        status="active",
    )
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email="admin@example.edu",
        password_hash="not-returned",
        first_name="Department",
        last_name="Admin",
        is_active=True,
        is_verified=True,
    )
    return AuthenticatedUserContext(
        user=user,
        institution=institution,
        roles=("administrator",),
    )


def _faculty(institution_id: UUID) -> Faculty:
    return Faculty(
        id=uuid4(),
        institution_id=institution_id,
        name="Science",
        code="SCI",
        status="active",
    )


def _department(
    institution_id: UUID,
    faculty_id: UUID,
    *,
    name: str = "Computer Science",
    code: str = "CSC",
) -> Department:
    now = datetime.now(UTC)
    return Department(
        id=uuid4(),
        institution_id=institution_id,
        faculty_id=faculty_id,
        name=name,
        code=code,
        description=None,
        status="active",
        created_at=now,
        updated_at=now,
    )


def test_department_model_and_schema_validation() -> None:
    checks = {
        str(constraint.sqltext)
        for constraint in Department.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "status IN ('active', 'inactive')" in checks

    faculty_id = uuid4()
    created = DepartmentCreate(
        faculty_id=faculty_id,
        name="  Computer Science ",
        code=" CSC ",
        description="  Computing ",
    )
    assert created.model_dump() == {
        "faculty_id": faculty_id,
        "name": "Computer Science",
        "code": "CSC",
        "description": "Computing",
    }
    for payload in (
        {"faculty_id": faculty_id, "name": " ", "code": "CSC"},
        {"faculty_id": faculty_id, "name": "Computer Science", "code": ""},
    ):
        with pytest.raises(ValidationError):
            DepartmentCreate(**payload)
    with pytest.raises(ValidationError):
        DepartmentUpdate(status="deleted")
    with pytest.raises(ValidationError):
        DepartmentUpdate(faculty_id=None)


def test_create_department_uses_authenticated_institution() -> None:
    context = _context()
    faculty = _faculty(context.institution.id)
    session = FakeSession(faculty, None, None)

    result = department_service.create_department(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        department_data=DepartmentCreate(
            faculty_id=faculty.id,
            name="Computer Science",
            code="CSC",
        ),
    )

    assert result.institution_id == context.institution.id
    assert result.faculty_id == faculty.id
    assert result.status == "active"
    assert session.added == [result]
    assert session.commits == 1


@pytest.mark.parametrize(
    ("results", "expected_error"),
    [
        ((None,), department_service.DepartmentFacultyNotFoundError),
        (
            (object(), uuid4()),
            department_service.DuplicateDepartmentCodeError,
        ),
        (
            (object(), None, uuid4()),
            department_service.DuplicateDepartmentNameError,
        ),
    ],
)
def test_create_rejects_missing_faculty_and_duplicates(
    results: tuple[object, ...],
    expected_error: type[Exception],
) -> None:
    context = _context()
    with pytest.raises(expected_error):
        department_service.create_department(
            FakeSession(*results),  # type: ignore[arg-type]
            institution_id=context.institution.id,
            department_data=DepartmentCreate(
                faculty_id=uuid4(),
                name="Computer Science",
                code="CSC",
            ),
        )


def test_cross_institution_faculty_is_hidden_as_not_found() -> None:
    own_context = _context()
    other_faculty = _faculty(uuid4())

    with pytest.raises(department_service.DepartmentFacultyNotFoundError):
        department_service.create_department(
            FakeSession(None),  # query is institution-scoped
            institution_id=own_context.institution.id,
            department_data=DepartmentCreate(
                faculty_id=other_faculty.id,
                name="Computer Science",
                code="CSC",
            ),
        )


def test_list_is_institution_scoped_and_supports_faculty_filter() -> None:
    context = _context()
    faculty = _faculty(context.institution.id)
    expected = [_department(context.institution.id, faculty.id)]
    session = FakeSession(expected)

    result = department_service.list_departments(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        faculty_id=faculty.id,
    )

    assert result == expected
    statement_text = str(session.statements[0])
    assert "departments.institution_id" in statement_text
    assert "departments.faculty_id" in statement_text
    assert "departments.status" in statement_text


def test_retrieve_update_delete_and_institution_isolation() -> None:
    context = _context()
    faculty = _faculty(context.institution.id)
    department = _department(context.institution.id, faculty.id)
    session = FakeSession(department, department, department)

    assert (
        department_service.get_department(
            session,  # type: ignore[arg-type]
            department_id=department.id,
            institution_id=context.institution.id,
        )
        is department
    )
    updated = department_service.update_department(
        session,  # type: ignore[arg-type]
        department_id=department.id,
        institution_id=context.institution.id,
        department_data=DepartmentUpdate(description=" Algorithms "),
    )
    assert updated.description == "Algorithms"

    deleted = department_service.delete_department(
        session,  # type: ignore[arg-type]
        department_id=department.id,
        institution_id=context.institution.id,
    )
    assert deleted.status == "inactive"

    for operation in (
        department_service.get_department,
        department_service.delete_department,
    ):
        with pytest.raises(department_service.DepartmentNotFoundError):
            operation(
                FakeSession(),  # type: ignore[arg-type]
                department_id=department.id,
                institution_id=uuid4(),
            )
    with pytest.raises(department_service.DepartmentNotFoundError):
        department_service.update_department(
            FakeSession(),  # type: ignore[arg-type]
            department_id=department.id,
            institution_id=uuid4(),
            department_data=DepartmentUpdate(name="Hidden"),
        )


def test_same_name_is_allowed_under_a_different_faculty() -> None:
    context = _context()
    new_faculty = _faculty(context.institution.id)
    session = FakeSession(new_faculty, None)
    department = _department(
        context.institution.id,
        _faculty(context.institution.id).id,
    )

    updated = department_service.update_department(
        FakeSession(department, new_faculty, None),  # type: ignore[arg-type]
        department_id=department.id,
        institution_id=context.institution.id,
        department_data=DepartmentUpdate(faculty_id=new_faculty.id),
    )
    assert updated.faculty_id == new_faculty.id

    # The name lookup is faculty-scoped, so an existing name elsewhere does not
    # prevent creation.
    result = department_service.create_department(
        session,  # type: ignore[arg-type]
        institution_id=context.institution.id,
        department_data=DepartmentCreate(
            faculty_id=new_faculty.id,
            name="Computer Science",
            code="CSC2",
        ),
    )
    assert result.name == "Computer Science"


def test_integrity_conflict_rolls_back() -> None:
    class FailingSession(FakeSession):
        def commit(self) -> None:
            raise IntegrityError("insert", {}, Exception("duplicate"))

    context = _context()
    faculty = _faculty(context.institution.id)
    session = FailingSession(faculty, None, None)
    with pytest.raises(department_service.DuplicateDepartmentError):
        department_service.create_department(
            session,  # type: ignore[arg-type]
            institution_id=context.institution.id,
            department_data=DepartmentCreate(
                faculty_id=faculty.id,
                name="Computer Science",
                code="CSC",
            ),
        )
    assert session.rollbacks == 1


def test_unauthenticated_creation_is_rejected() -> None:
    with pytest.raises(HTTPException) as raised:
        dependencies.get_current_user(
            None,
            FakeSession(),  # type: ignore[arg-type]
        )
    assert raised.value.status_code == 401


def test_route_errors_and_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    monkeypatch.setattr(
        departments,
        "create_department",
        lambda *_, **__: (_ for _ in ()).throw(
            department_service.DuplicateDepartmentCodeError()
        ),
    )
    with pytest.raises(HTTPException) as duplicate:
        departments.create_department_endpoint(
            DepartmentCreate(
                faculty_id=uuid4(),
                name="Computer Science",
                code="CSC",
            ),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert duplicate.value.status_code == 409

    monkeypatch.setattr(
        departments,
        "get_department",
        lambda *_, **__: (_ for _ in ()).throw(
            department_service.DepartmentNotFoundError()
        ),
    )
    with pytest.raises(HTTPException) as missing:
        departments.get_department_endpoint(
            uuid4(),
            FakeSession(),  # type: ignore[arg-type]
            context,
        )
    assert missing.value.status_code == 404

    paths = app.openapi()["paths"]
    assert "/api/v1/departments" in paths
    assert "/api/v1/departments/{department_id}" in paths
