from app.graph.policies import gate_decision, threshold_for_mode
from app.schemas import (
    CandidateDraft,
    GateDecision,
    L1State,
    OperatingMode,
    QualityVector,
    RiskClass,
)


def _base_state() -> L1State:
    return L1State(
        session_id="s1",
        user_id="u1",
        turn_id=1,
        user_message="verify this factual claim",
        active_mode=OperatingMode.TRUTH_MODE,
        thresholds=threshold_for_mode(OperatingMode.TRUTH_MODE),
        max_retrieval_attempts=2,
        candidate_draft=CandidateDraft(
            text="Claim A is true [EVID:e1]",
            claims=["Claim A is true"],
            claim_citations={"Claim A is true": ["e1"]},
        ),
        quality_vector=QualityVector(
            internal_consistency=0.9,
            external_correspondence=0.2,
            mode_compliance=0.98,
            calibration_signal=0.7,
            citation_fidelity=0.1,
            claim_coverage=0.1,
            adversarial_resistance=0.85,
        ),
    )


def test_requires_retrieval_when_evidence_insufficient_and_attempts_remain() -> None:
    state = _base_state()
    decision, _ = gate_decision(state)
    assert decision == GateDecision.REQUIRE_RETRIEVAL


def test_downgrades_when_truth_fails_after_max_attempts_non_high_stakes() -> None:
    state = _base_state()
    state.retrieval_attempts = state.max_retrieval_attempts
    state.allow_mode_downgrade = True
    state.risk_class = RiskClass.LOW

    decision, _ = gate_decision(state)
    assert decision == GateDecision.DOWNGRADE_MODE


def test_high_stakes_never_downgrades() -> None:
    state = _base_state()
    state.retrieval_attempts = state.max_retrieval_attempts
    state.risk_class = RiskClass.HIGH_STAKES

    decision, _ = gate_decision(state)
    assert decision in {GateDecision.HALT, GateDecision.ASK}
    assert decision != GateDecision.DOWNGRADE_MODE


def test_stagnation_with_no_retrieval_budget_is_terminal() -> None:
    state = _base_state()
    state.stagnation_count = 2
    state.retrieval_attempts = state.max_retrieval_attempts

    decision, _ = gate_decision(state)
    assert decision in {GateDecision.HALT, GateDecision.ASK}
