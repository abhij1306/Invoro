from __future__ import annotations

import pytest

from app.core.security import encrypt_secret
from app.models.llm import LLMConfig
from app.services.llm.config_service import (
    resolve_active_config,
    resolve_provider_api_key,
    serialize_config_snapshot,
)


@pytest.mark.asyncio
async def test_resolve_active_config_prefers_task_then_general(db_session) -> None:
    db_session.add_all(
        [
            LLMConfig(
                provider="groq",
                model="general-model",
                api_key_encrypted="enc-general",
                task_type="general",
                is_active=True,
            ),
            LLMConfig(
                provider="groq",
                model="task-model",
                api_key_encrypted="enc-task",
                task_type="missing_field_extraction",
                is_active=True,
            ),
        ]
    )
    await db_session.commit()

    task_config = await resolve_active_config(db_session, "missing_field_extraction")
    fallback_config = await resolve_active_config(db_session, "direct_record_extraction")

    assert task_config is not None
    assert task_config.model == "task-model"
    assert fallback_config is not None
    assert fallback_config.model == "general-model"


def test_resolve_provider_api_key_prefers_encrypted_value(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.llm.config_service.settings.groq_api_key",
        "env-secret",
    )
    encrypted = encrypt_secret("stored-secret")

    assert (
        resolve_provider_api_key(provider="groq", encrypted_value=encrypted)
        == "stored-secret"
    )
    assert resolve_provider_api_key(provider="groq", encrypted_value="") == "env-secret"


def test_serialize_config_snapshot_keeps_encrypted_key() -> None:
    config = LLMConfig(
        id=7,
        provider="groq",
        model="llama",
        api_key_encrypted="encrypted",
        task_type="general",
    )

    assert serialize_config_snapshot(config) == {
        "id": 7,
        "provider": "groq",
        "model": "llama",
        "api_key_encrypted": "encrypted",
        "task_type": "general",
    }
