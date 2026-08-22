"""Build the container database URL safely, then run the requested command."""

from __future__ import annotations

import os
import sys
from urllib.parse import quote


def build_database_url(
    *, user: str, password: str, host: str, port: str, database: str
) -> str:
    """Return an asyncpg URL with each user-controlled component encoded."""
    return (
        "postgresql+asyncpg://"
        f"{quote(user, safe='')}:{quote(password, safe='')}@{host}:{port}/"
        f"{quote(database, safe='')}"
    )


def main() -> None:
    """Populate DATABASE_URL from Compose inputs and replace this process."""
    password = os.environ.get("POSTGRES_PASSWORD")
    if password is not None:
        os.environ["DATABASE_URL"] = build_database_url(
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=password,
            host=os.environ.get("POSTGRES_HOST", "db"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
            database=os.environ.get("POSTGRES_DB", "invoro"),
        )
    if len(sys.argv) < 2:
        raise SystemExit("No container command provided")
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
