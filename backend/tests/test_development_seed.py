from collections.abc import Sequence
from typing import Any
from uuid import uuid4

import pytest

from app.models.institution import Institution
from app.models.institution_setting import InstitutionSetting
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole
from app.services import development_seed


PASSWORD = "local-development-password"
HASHED_PASSWORD = "securely-hashed-password"


class FakeSession:
    def __init__(self, results: Sequence[object | None]) -> None:
        self.results = iter(results)
        self.added: list[object] = []
        self.statements: list[Any] = []
        self.flush_count = 0
        self.commit_count = 0
        self.rollback_count = 0
        self.close_count = 0

    def scalar(self, statement: Any) -> object | None:
        self.statements.append(statement)
        return next(self.results)

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def flush(self) -> None:
        self.flush_count += 1

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


def _seed(
    session: FakeSession,
    monkeypatch: pytest.MonkeyPatch,
    **overrides: str,
) -> development_seed.DevelopmentSeedResult:
    monkeypatch.setattr(
        development_seed,
        "hash_password",
        lambda _: HASHED_PASSWORD,
    )
    inputs = {
        "institution_code": "  ngozi  ",
        "institution_name": "  Ngozi University  ",
        "administrator_email": "  ADMIN@NGOZI.LOCAL  ",
        "administrator_password": PASSWORD,
    }
    inputs.update(overrides)
    return development_seed.seed_development_data(
        session,  # type: ignore[arg-type]
        **inputs,
    )


def _new_seed_session() -> FakeSession:
    return FakeSession([None, None, None, None, None, None, None])


def _existing_records() -> tuple[
    Institution,
    InstitutionSetting,
    Role,
    Role,
    User,
    UserRole,
    UserRole,
]:
    institution = Institution(
        id=uuid4(),
        code="NGOZI",
        name="Existing University",
        status="active",
    )
    setting = InstitutionSetting(
        id=uuid4(),
        institution_id=institution.id,
        setting_key="timezone",
        setting_value="Africa/Lagos",
        value_type="string",
        is_public=False,
    )
    administrator_role = Role(
        id=uuid4(),
        name="administrator",
        description="Existing administrator role.",
    )
    system_role = Role(
        id=uuid4(),
        name="system_super_admin",
        description="Existing system role.",
    )
    user = User(
        id=uuid4(),
        institution_id=institution.id,
        email="admin@ngozi.local",
        password_hash="existing-password-hash",
        first_name="Existing",
        last_name="Administrator",
        is_active=True,
        is_verified=True,
    )
    administrator_assignment = UserRole(
        id=uuid4(),
        user_id=user.id,
        role_id=administrator_role.id,
        institution_id=institution.id,
    )
    system_assignment = UserRole(
        id=uuid4(),
        user_id=user.id,
        role_id=system_role.id,
        institution_id=institution.id,
    )
    return (
        institution,
        setting,
        administrator_role,
        system_role,
        user,
        administrator_assignment,
        system_assignment,
    )


def test_new_seed_normalizes_identity_and_hashes_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = _new_seed_session()

    result = _seed(session, monkeypatch)

    institution = next(
        item for item in session.added if isinstance(item, Institution)
    )
    user = next(item for item in session.added if isinstance(item, User))
    assignments = [
        item for item in session.added if isinstance(item, UserRole)
    ]

    assert institution.code == "NGOZI"
    assert institution.name == "Ngozi University"
    assert user.email == "admin@ngozi.local"
    assert user.password_hash == HASHED_PASSWORD
    assert user.password_hash != PASSWORD
    assert len(assignments) == 2
    assert all(
        assignment.institution_id == institution.id
        for assignment in assignments
    )
    assert result.changed
    assert all(vars(result).values())
    assert session.commit_count == 1
    assert session.rollback_count == 0
    assert session.close_count == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("institution_code", "  "),
        ("institution_name", ""),
        ("administrator_email", "invalid-address"),
        ("administrator_password", ""),
        ("administrator_password", "invalid\x00password"),
    ],
)
def test_invalid_seed_input_is_rejected_and_rolled_back(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    session = _new_seed_session()

    with pytest.raises(ValueError):
        _seed(session, monkeypatch, **{field: value})

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 0


def test_existing_records_are_reused_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _existing_records()
    session = FakeSession(records)
    existing_user = records[4]
    original_password_hash = existing_user.password_hash

    result = _seed(session, monkeypatch)

    assert session.added == []
    assert existing_user.password_hash == original_password_hash
    assert result == development_seed.DevelopmentSeedResult(
        institution_created=False,
        institution_setting_created=False,
        administrator_role_created=False,
        system_super_admin_role_created=False,
        administrator_user_created=False,
        administrator_role_assigned=False,
        system_super_admin_role_assigned=False,
    )
    assert not result.changed
    assert session.commit_count == 1
    assert session.rollback_count == 0


def test_only_missing_role_assignment_is_created(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records = _existing_records()
    session = FakeSession([*records[:6], None])

    result = _seed(session, monkeypatch)

    assignments = [
        item for item in session.added if isinstance(item, UserRole)
    ]
    assert len(assignments) == 1
    assert assignments[0].role_id == records[3].id
    assert assignments[0].institution_id == records[0].id
    assert not result.administrator_role_assigned
    assert result.system_super_admin_role_assigned


def test_second_seed_run_creates_no_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_session = _new_seed_session()
    first_result = _seed(first_session, monkeypatch)
    created_by_type = {
        type(item): item
        for item in first_session.added
        if not isinstance(item, UserRole)
    }
    assignments = [
        item for item in first_session.added if isinstance(item, UserRole)
    ]
    second_session = FakeSession(
        [
            created_by_type[Institution],
            created_by_type[InstitutionSetting],
            next(
                role
                for role in first_session.added
                if isinstance(role, Role) and role.name == "administrator"
            ),
            next(
                role
                for role in first_session.added
                if isinstance(role, Role)
                and role.name == "system_super_admin"
            ),
            created_by_type[User],
            assignments[0],
            assignments[1],
        ]
    )

    second_result = _seed(second_session, monkeypatch)

    assert first_result.changed
    assert not second_result.changed
    assert second_session.added == []
    assert second_session.commit_count == 1


def test_service_rolls_back_hashing_failure_without_closing_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([None, None, None, None, None])

    def fail_hash(_: str) -> str:
        raise RuntimeError("hashing failed")

    monkeypatch.setattr(development_seed, "hash_password", fail_hash)

    with pytest.raises(RuntimeError):
        development_seed.seed_development_data(
            session,  # type: ignore[arg-type]
            institution_code="NGOZI",
            institution_name="Ngozi University",
            administrator_email="admin@ngozi.local",
            administrator_password=PASSWORD,
        )

    assert session.commit_count == 0
    assert session.rollback_count == 1
    assert session.close_count == 0


def test_seed_service_does_not_print_or_store_plaintext_password(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session = _new_seed_session()

    _seed(session, monkeypatch)

    captured = capsys.readouterr()
    assert PASSWORD not in captured.out
    assert PASSWORD not in captured.err
    assert all(
        PASSWORD not in vars(item).values()
        for item in session.added
        if hasattr(item, "__dict__")
    )
