"""Playground session schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlaygroundSessionCreate(BaseModel):
    url: str


class PlaygroundSelectRequest(BaseModel):
    """User selects which discovered product URLs to extract (max 50)."""
    urls: list[str] = Field(..., max_length=50)


class PlaygroundPipelineRequest(BaseModel):
    """User selects which downstream operations to run."""
    enrich: bool = False
    compare: bool = False
    monitor: bool = False
    audit: bool = False


class PlaygroundStepResult(BaseModel):
    status: str  # pending | running | completed | failed
    run_id: int | None = None
    job_id: int | None = None
    error: str | None = None
    data: dict = Field(default_factory=dict)


class PlaygroundSessionResponse(BaseModel):
    id: int
    input_url: str
    state: str
    step_data: dict
    created_at: datetime
    updated_at: datetime


class PlaygroundDiscoverResponse(BaseModel):
    session_id: int
    state: str
    run_id: int
    message: str


class PlaygroundExtractResponse(BaseModel):
    session_id: int
    state: str
    run_id: int
    url_count: int


class PlaygroundPipelineResponse(BaseModel):
    session_id: int
    state: str
    launched: dict  # which ops were launched with their job/run IDs
