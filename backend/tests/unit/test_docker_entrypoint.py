import pytest

from docker_entrypoint import build_database_url, configure_database_url


@pytest.mark.unit
def test_database_url_percent_encodes_credentials_and_database_name() -> None:
    url = build_database_url(
        user="invoro/user",
        password="slash/question?#hash",
        host="db",
        port="5432",
        database="invoro db",
    )

    assert url == (
        "postgresql+asyncpg://invoro%2Fuser:slash%2Fquestion%3F%23hash"
        "@db:5432/invoro%20db"
    )


@pytest.mark.unit
def test_explicit_database_url_takes_precedence_over_compose_parts() -> None:
    environment = {
        "DATABASE_URL": "postgresql+asyncpg://external.example/invoro",
        "POSTGRES_PASSWORD": "compose-password",
        "POSTGRES_HOST": "db",
    }

    configure_database_url(environment)

    assert environment["DATABASE_URL"] == (
        "postgresql+asyncpg://external.example/invoro"
    )
