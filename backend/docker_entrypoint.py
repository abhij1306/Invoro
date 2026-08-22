"""Build the container database URL safely, then run the requested command."""

from __future__ import annotations

import os
import sys
from collections.abc import MutableMapping
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


def configure_database_url(environment: MutableMapping[str, str]) -> None:
    """Synthesize the Compose URL without overriding an explicit database URL."""
    if environment.get("DATABASE_URL", "").strip():
        return
    password = environment.get("POSTGRES_PASSWORD")
    if password is None:
        return
    environment["DATABASE_URL"] = build_database_url(
        user=environment.get("POSTGRES_USER", "postgres"),
        password=password,
        host=environment.get("POSTGRES_HOST", "db"),
        port=environment.get("POSTGRES_PORT", "5432"),
        database=environment.get("POSTGRES_DB", "invoro"),
    )


def main() -> None:
    """Populate DATABASE_URL from Compose inputs and replace this process."""
    configure_database_url(os.environ)
    if len(sys.argv) < 2:
        raise SystemExit("No container command provided")
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
