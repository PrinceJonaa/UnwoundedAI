from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import GateDecision, OperatingMode, QualityVector


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    requested_mode: OperatingMode | None = None
    allow_mode_downgrade: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: OperatingMode
    gate_decision: GateDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    quality_vector: QualityVector | None = None
    answer: str
    fact_block: str | None = None
    idea_block: str | None = None
    citations: list[str] = Field(default_factory=list)
    asked_clarifying_question: str | None = None
    header: str
