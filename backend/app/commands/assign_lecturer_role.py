import argparse
import sys
from uuid import UUID

from app.db.session import SessionLocal
from app.services.role_assignment_service import (
    LecturerRoleRepairTargetNotFoundError,
    repair_lecturer_role,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Assign the established Lecturer role to an existing Lecturer User.",
    )
    parser.add_argument("--user-id", required=True, type=UUID)
    parser.add_argument("--institution-code", required=True)
    arguments = parser.parse_args(argv)

    session = SessionLocal()
    try:
        changed = repair_lecturer_role(
            session,
            user_id=arguments.user_id,
            institution_code=arguments.institution_code,
        )
    except LecturerRoleRepairTargetNotFoundError:
        print(
            "No active Lecturer User matched that institution and User ID.",
            file=sys.stderr,
        )
        return 2
    except Exception:
        print("Lecturer role repair failed.", file=sys.stderr)
        return 1
    finally:
        session.close()

    outcome = "assigned" if changed else "already assigned"
    print(f"Lecturer role {outcome} for User {arguments.user_id}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
