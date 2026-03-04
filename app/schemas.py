from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OperatingMode(str, Enum):
    TRUTH_MODE = "TRUTH_MODE"
    RELATIONAL_MODE = "RELATIONAL_MODE"
    INTEGRATION_MODE = "INTEGRATION_MODE"


class GateDecision(str, Enum):
    PASS = "PASS"
    HALT = "HALT"
    ASK = "ASK"
    REQUIRE_RETRIEVAL = "REQUIRE_RETRIEVAL"
    DOWNGRADE_MODE = "DOWNGRADE_MODE"


class RiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH_STAKES = "HIGH_STAKES"


class ModeSource(str, Enum):
    AUTO = "AUTO"
    USER_OVERRIDE = "USER_OVERRIDE"
    GATE_DOWNGRADE = "GATE_DOWNGRADE"


class SupervisorStage(str, Enum):
    NEEDS_RETRIEVAL = "NEEDS_RETRIEVAL"
    NEEDS_DRAFT = "NEEDS_DRAFT"
    NEEDS_VERIFY = "NEEDS_VERIFY"
    NEEDS_DECISION = "NEEDS_DECISION"


class ThresholdProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_internal_consistency: float = Field(..., ge=0.0, le=1.0)
    min_external_correspondence: float = Field(..., ge=0.0, le=1.0)
    min_mode_compliance: float = Field(..., ge=0.0, le=1.0)
    min_calibration_signal: float = Field(..., ge=0.0, le=1.0)
    min_citation_fidelity: float = Field(default=0.0, ge=0.0, le=1.0)
    min_claim_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    min_adversarial_resistance: float = Field(default=0.0, ge=0.0, le=1.0)
    min_aggregate_score: float = Field(..., ge=0.0, le=1.0)


class QualityVector(BaseModel):
    model_config = ConfigDict(extra="forbid")

    internal_consistency: float = Field(..., ge=0.0, le=1.0)
    external_correspondence: float = Field(..., ge=0.0, le=1.0)
    mode_compliance: float = Field(..., ge=0.0, le=1.0)
    calibration_signal: float = Field(..., ge=0.0, le=1.0)

    citation_fidelity: float = Field(default=0.0, ge=0.0, le=1.0)
    claim_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    adversarial_resistance: float = Field(default=0.0, ge=0.0, le=1.0)

    aggregate_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rationale: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def compute_aggregate(self) -> "QualityVector":
        if self.aggregate_score is None:
            self.aggregate_score = round(
                (0.20 * self.internal_consistency)
                + (0.25 * self.external_correspondence)
                + (0.15 * self.mode_compliance)
                + (0.10 * self.calibration_signal)
                + (0.10 * self.citation_fidelity)
                + (0.10 * self.claim_coverage)
                + (0.10 * self.adversarial_resistance),
                4,
            )
        return self


class RetrievedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_type: Literal["retrieval", "mem0", "tool", "user", "system"]
    citation: Optional[str] = None
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0)
    supports_claims: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class CandidateDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    claims: list[str] = Field(default_factory=list)
    claim_citations: dict[str, list[str]] = Field(default_factory=dict)
    uncertainty_statements: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)


class FinalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: OperatingMode
    gate_decision: GateDecision
    confidence: float = Field(..., ge=0.0, le=1.0)
    header: str
    answer: str
    fact_block: Optional[str] = None
    idea_block: Optional[str] = None
    clarifying_question: Optional[str] = None
    citations: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_integration_sections(self) -> "FinalResponse":
        if self.mode == OperatingMode.INTEGRATION_MODE and self.gate_decision not in {
            GateDecision.HALT,
            GateDecision.ASK,
        }:
            if not self.fact_block or not self.idea_block:
                raise ValueError("INTEGRATION_MODE requires both fact_block and idea_block.")
        return self


class L3PromotionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: str
    memory_type: Literal["preference", "boundary", "stable_rule", "scar"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_user_confirmation: bool = True
    verification_count: int = Field(default=0, ge=0)
    source: Literal["user_message", "assistant_output", "tool_output"] = "assistant_output"


class L1State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    user_id: str
    turn_id: int = Field(..., ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user_message: str
    goal: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    active_mode: OperatingMode = OperatingMode.TRUTH_MODE
    requested_mode: Optional[OperatingMode] = None
    mode_source: ModeSource = ModeSource.AUTO
    allow_mode_downgrade: bool = True
    risk_class: RiskClass = RiskClass.MEDIUM

    thresholds: ThresholdProfile
    retrieval_attempts: int = Field(default=0, ge=0)
    max_retrieval_attempts: int = Field(default=2, ge=0)
    last_retrieval_fingerprint: Optional[str] = None
    stagnation_count: int = Field(default=0, ge=0)
    retrieved_evidence: list[RetrievedEvidence] = Field(default_factory=list)

    mem0_context_ids: list[str] = Field(default_factory=list)
    scratchpad: list[str] = Field(default_factory=list)

    supervisor_stage: SupervisorStage = SupervisorStage.NEEDS_DRAFT
    verifier_recommendation: Optional[GateDecision] = None
    next_node: Optional[str] = None

    candidate_draft: Optional[CandidateDraft] = None
    quality_vector: Optional[QualityVector] = None
    gate_decision: Optional[GateDecision] = None
    gate_reason: Optional[str] = None

    final_response: Optional[FinalResponse] = None
    l3_promotion_candidates: list[L3PromotionCandidate] = Field(default_factory=list)

    trace_id: Optional[str] = None
    span_id: Optional[str] = None

    @model_validator(mode="after")
    def enforce_gate_invariants(self) -> "L1State":
        if self.retrieval_attempts > self.max_retrieval_attempts:
            raise ValueError("retrieval_attempts cannot exceed max_retrieval_attempts")

        if self.gate_decision == GateDecision.DOWNGRADE_MODE:
            if self.active_mode != OperatingMode.TRUTH_MODE:
                raise ValueError("DOWNGRADE_MODE is only valid when active_mode is TRUTH_MODE")
            if not self.allow_mode_downgrade:
                raise ValueError("allow_mode_downgrade must be true for DOWNGRADE_MODE")
            if self.risk_class == RiskClass.HIGH_STAKES:
                raise ValueError("HIGH_STAKES requests cannot use DOWNGRADE_MODE")

        if self.gate_decision == GateDecision.PASS and self.quality_vector is None:
            raise ValueError("PASS requires quality_vector")

        return self


DEFAULT_THRESHOLDS: dict[OperatingMode, ThresholdProfile] = {
    OperatingMode.TRUTH_MODE: ThresholdProfile(
        min_internal_consistency=0.85,
        min_external_correspondence=0.82,
        min_mode_compliance=0.95,
        min_calibration_signal=0.75,
        min_citation_fidelity=0.75,
        min_claim_coverage=0.70,
        min_adversarial_resistance=0.85,
        min_aggregate_score=0.82,
    ),
    OperatingMode.RELATIONAL_MODE: ThresholdProfile(
        min_internal_consistency=0.60,
        min_external_correspondence=0.35,
        min_mode_compliance=0.90,
        min_calibration_signal=0.55,
        min_citation_fidelity=0.20,
        min_claim_coverage=0.30,
        min_adversarial_resistance=0.70,
        min_aggregate_score=0.64,
    ),
    OperatingMode.INTEGRATION_MODE: ThresholdProfile(
        min_internal_consistency=0.75,
        min_external_correspondence=0.62,
        min_mode_compliance=0.90,
        min_calibration_signal=0.65,
        min_citation_fidelity=0.55,
        min_claim_coverage=0.55,
        min_adversarial_resistance=0.80,
        min_aggregate_score=0.74,
    ),
}
