import os
import sys

from app.db.session import SessionLocal
from app.services.development_seed import (
    DevelopmentSeedResult,
    seed_development_data,
)


REQUIRED_ENVIRONMENT_VARIABLES = (
    "DEVELOPMENT_SEED_INSTITUTION_CODE",
    "DEVELOPMENT_SEED_INSTITUTION_NAME",
    "DEVELOPMENT_SEED_ADMIN_EMAIL",
    "DEVELOPMENT_SEED_ADMIN_PASSWORD",
)
PASSWORD_PLACEHOLDER = "replace-with-a-local-development-password"


def main() -> int:
    try:
        configuration = _load_configuration()
    except ValueError:
        print(
            "Development seed configuration is missing or still uses a "
            "documented placeholder.",
            file=sys.stderr,
        )
        return 2

    session = SessionLocal()
    try:
        result = seed_development_data(
            session,
            institution_code=configuration[
                "DEVELOPMENT_SEED_INSTITUTION_CODE"
            ],
            institution_name=configuration[
                "DEVELOPMENT_SEED_INSTITUTION_NAME"
            ],
            administrator_email=configuration[
                "DEVELOPMENT_SEED_ADMIN_EMAIL"
            ],
            administrator_password=configuration[
                "DEVELOPMENT_SEED_ADMIN_PASSWORD"
            ],
        )
    except Exception:
        print(
            "Development seed failed. Review the local configuration and "
            "database availability.",
            file=sys.stderr,
        )
        return 1
    finally:
        session.close()

    _print_success_summary(
        configuration["DEVELOPMENT_SEED_INSTITUTION_CODE"].strip().upper(),
        configuration["DEVELOPMENT_SEED_ADMIN_EMAIL"].strip().lower(),
        result,
    )
    return 0


def _load_configuration() -> dict[str, str]:
    configuration = {
        name: os.getenv(name, "")
        for name in REQUIRED_ENVIRONMENT_VARIABLES
    }
    if any(not value.strip() for value in configuration.values()):
        raise ValueError("Missing development seed configuration")
    if (
        configuration["DEVELOPMENT_SEED_ADMIN_PASSWORD"].strip()
        == PASSWORD_PLACEHOLDER
    ):
        raise ValueError("Development password placeholder is not valid")
    return configuration


def _print_success_summary(
    institution_code: str,
    administrator_email: str,
    result: DevelopmentSeedResult,
) -> None:
    categories = (
        ("institution", result.institution_created),
        ("institution setting", result.institution_setting_created),
        ("administrator role", result.administrator_role_created),
        ("system super admin role", result.system_super_admin_role_created),
        ("administrator user", result.administrator_user_created),
        ("administrator assignment", result.administrator_role_assigned),
        (
            "system super admin assignment",
            result.system_super_admin_role_assigned,
        ),
    )
    outcome = ", ".join(
        f"{category}: {'created' if created else 'already existed'}"
        for category, created in categories
    )
    print(
        f"Development seed complete for {institution_code} "
        f"({administrator_email}). {outcome}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
