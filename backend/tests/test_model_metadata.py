from sqlalchemy import UniqueConstraint

import app.models  # noqa: F401
from app.db.base import Base


EXPECTED_TABLES = {
    "institutions",
    "institution_settings",
    "roles",
    "users",
    "user_roles",
}


def _unique_column_sets(table_name: str) -> set[tuple[str, ...]]:
    table = Base.metadata.tables[table_name]
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _foreign_key_target(table_name: str, column_name: str) -> str:
    column = Base.metadata.tables[table_name].columns[column_name]
    return next(iter(column.foreign_keys)).target_fullname


def test_all_models_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_expected_unique_constraints() -> None:
    assert ("code",) in _unique_column_sets("institutions")
    assert ("name",) in _unique_column_sets("roles")
    assert ("institution_id", "email") in _unique_column_sets("users")
    assert (
        "institution_id",
        "setting_key",
    ) in _unique_column_sets("institution_settings")
    assert (
        "user_id",
        "role_id",
        "institution_id",
    ) in _unique_column_sets("user_roles")


def test_expected_foreign_keys() -> None:
    assert (
        _foreign_key_target("institution_settings", "institution_id")
        == "institutions.id"
    )
    assert _foreign_key_target("users", "institution_id") == "institutions.id"
    assert _foreign_key_target("user_roles", "user_id") == "users.id"
    assert _foreign_key_target("user_roles", "role_id") == "roles.id"
    assert (
        _foreign_key_target("user_roles", "institution_id")
        == "institutions.id"
    )
