from __future__ import annotations

import pytest

from app.core.security import encrypt_secret
from app.api.llm import llm_configs
from app.models.llm import LLMConfig
from app.services.llm.config_service import (
    llm_provider_catalog,
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


def test_llm_provider_catalog_exposes_expected_provider_anchors() -> None:
    catalog = {item["provider"]: item for item in llm_provider_catalog()}

    assert "llama-3.3-70b-versatile" in catalog["groq"]["recommended_models"]
    assert "meta/llama-3.1-70b-instruct" in catalog["nvidia"]["recommended_models"]
    assert "openrouter/free" in catalog["openrouter"]["recommended_models"]
    assert catalog["groq"]["recommended_models"]
    assert catalog["nvidia"]["recommended_models"]
    assert catalog["openrouter"]["recommended_models"]


@pytest.mark.asyncio
async def test_llm_configs_can_include_unsupported_records(db_session, caplog) -> None:
    db_session.add_all(
        [
            LLMConfig(
                provider="groq",
                model="supported-model",
                api_key_encrypted="enc-supported",
                task_type="general",
                is_active=True,
            ),
            LLMConfig(
                provider="legacy-provider",
                model="legacy-model",
                api_key_encrypted="enc-legacy",
                task_type="general",
                is_active=False,
            ),
        ]
    )
    await db_session.commit()

    caplog.clear()
    filtered = await llm_configs(db_session, object(), include_unsupported=False)
    included = await llm_configs(db_session, object(), include_unsupported=True)

    assert [row.provider for row in filtered] == ["groq"]
    assert sorted(row.provider for row in included) == ["groq", "legacy-provider"]
    assert "excluded 1 unsupported provider records" in caplog.text
