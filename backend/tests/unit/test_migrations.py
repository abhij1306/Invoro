from types import SimpleNamespace

import pytest

from app.core import migrations


@pytest.mark.unit
def test_build_alembic_config_accepts_percent_encoded_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = "postgresql+asyncpg://invoro:password%21@db:5432/invoro%20database"
    monkeypatch.setattr(
        migrations,
        "settings",
        SimpleNamespace(database_url=database_url),
    )

    config = migrations.build_alembic_config()

    assert config.get_main_option("sqlalchemy.url") == database_url
