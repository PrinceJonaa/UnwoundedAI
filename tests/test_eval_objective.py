from app.graph.policies import compute_quality_vector, threshold_for_mode
from app.schemas import CandidateDraft, L1State, OperatingMode, RetrievedEvidence


def test_external_correspondence_low_when_claims_not_in_evidence() -> None:
    state = L1State(
        session_id="s1",
        user_id="u1",
        turn_id=1,
        user_message="What is the moon made of?",
        active_mode=OperatingMode.TRUTH_MODE,
        thresholds=threshold_for_mode(OperatingMode.TRUTH_MODE),
        candidate_draft=CandidateDraft(
            text="The moon is made entirely of cheese. [EVID:src-1]",
            claims=["The moon is made entirely of cheese"],
            claim_citations={"The moon is made entirely of cheese": ["src-1"]},
        ),
        retrieved_evidence=[
            RetrievedEvidence(
                source_id="src-1",
                source_type="retrieval",
                citation="Lunar geology summary",
                trust_score=0.9,
                supports_claims=[],
                payload={"text": "The moon is primarily composed of silicate rock."},
            )
        ],
    )

    vector = compute_quality_vector(state)
    assert vector.external_correspondence < 0.45
    assert vector.citation_fidelity < 0.55
    assert vector.missing_evidence


def test_citation_fidelity_low_for_nonexistent_evidence_ids() -> None:
    state = L1State(
        session_id="s2",
        user_id="u2",
        turn_id=1,
        user_message="Verify claim",
        active_mode=OperatingMode.TRUTH_MODE,
        thresholds=threshold_for_mode(OperatingMode.TRUTH_MODE),
        candidate_draft=CandidateDraft(
            text="Earth has two moons. [EVID:missing-1]",
            claims=["Earth has two moons"],
            claim_citations={"Earth has two moons": ["missing-1"]},
        ),
        retrieved_evidence=[
            RetrievedEvidence(
                source_id="src-known",
                source_type="retrieval",
                citation="Astronomy basics",
                trust_score=0.8,
                supports_claims=[],
                payload={"text": "Earth has one natural satellite: the Moon."},
            )
        ],
    )

    vector = compute_quality_vector(state)
    assert vector.citation_fidelity == 0.0
    assert vector.external_correspondence < 0.5
