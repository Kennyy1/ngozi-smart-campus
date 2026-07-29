import pytest

from app.core.security import (
    hash_password,
    password_hash_needs_update,
    verify_password,
)


TEST_PASSWORD = "correct horse battery staple"


def test_password_hashing_and_verification() -> None:
    password_hash = hash_password(TEST_PASSWORD)

    assert password_hash != TEST_PASSWORD
    assert password_hash.startswith("$argon2id$")
    assert verify_password(TEST_PASSWORD, password_hash)
    assert not verify_password("incorrect password", password_hash)


def test_malformed_hash_returns_false() -> None:
    assert not verify_password(TEST_PASSWORD, "not-a-supported-hash")


def test_empty_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_null_byte_password_is_rejected() -> None:
    with pytest.raises(ValueError):
        hash_password("invalid\x00password")


def test_hashes_use_unique_salts_and_both_verify() -> None:
    first_hash = hash_password(TEST_PASSWORD)
    second_hash = hash_password(TEST_PASSWORD)

    assert first_hash != second_hash
    assert verify_password(TEST_PASSWORD, first_hash)
    assert verify_password(TEST_PASSWORD, second_hash)


def test_password_hash_update_check_returns_boolean() -> None:
    result = password_hash_needs_update(hash_password(TEST_PASSWORD))

    assert isinstance(result, bool)
    assert password_hash_needs_update("malformed-hash") is False


def test_password_functions_do_not_print_plaintext(
    capsys: pytest.CaptureFixture[str],
) -> None:
    password_hash = hash_password(TEST_PASSWORD)
    assert verify_password(TEST_PASSWORD, password_hash)
    password_hash_needs_update(password_hash)

    captured = capsys.readouterr()
    assert TEST_PASSWORD not in captured.out
    assert TEST_PASSWORD not in captured.err
