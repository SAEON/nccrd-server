"""
One-off activation script for legacy-migrated users.

Every ``nccrd.user`` row with ``password_hash IS NULL`` (i.e. every user that
existed before local JWT auth was introduced — the ~257 users migrated from
the old SQL Server database) gets a random temporary password. Each user's
``password_set_at`` is left NULL, which the login endpoint treats as a
"must change password" sentinel — the frontend forces a change-password step
immediately after their first login.

Usage:
    python -m scripts.set_legacy_passwords [--out FILE]

Writes ``email,temp_password`` pairs (CSV, no header) to FILE (default
``legacy_passwords.csv`` in the current directory) for an admin to distribute
out-of-band. This file contains plaintext credentials — treat it as sensitive,
delete it once distributed, and never commit it.
"""

import argparse
import csv

from nccrd.api.lib.auth import generate_temp_password, hash_password
from nccrd.db import get_db
from nccrd.db.models.rbac import User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="legacy_passwords.csv", help="Output CSV path.")
    args = parser.parse_args()

    db = next(get_db())
    try:
        users = db.query(User).filter(User.password_hash.is_(None)).all()

        if not users:
            print("No users need activation — every user already has a password_hash set.")
            return

        rows = []
        for user in users:
            temp_password = generate_temp_password()
            user.password_hash = hash_password(temp_password)
            user.password_set_at = None  # sentinel: must change on first login
            rows.append((user.email, temp_password))

        db.commit()

        with open(args.out, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerows(rows)

        print(f"Activated {len(rows)} users. Temporary passwords written to {args.out}.")
        print("Distribute this file to affected users out-of-band, then delete it.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
