from __future__ import annotations

import re
from typing import Iterable

from app.schemas import (
    DEFAULT_THRESHOLDS,
    GateDecision,
    L1State,
    OperatingMode,
    QualityVector,
    RiskClass,
    ThresholdProfile,
)

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "was",
    "were",
    "with",
}

NEGATION_WORDS = {"not", "never", "no", "none", "cannot", "can't", "isn't", "aren't", "won't"}

HIGH_STAKES_KEYWORDS = {
    "legal",
    "lawsuit",
    "attorney",
    "medical",
    "diagnosis",
    "prescription",
    "financial",
    "investment",
    "safety",
    "suicidal",
    "self-harm",
    "harm",
}

RELATIONAL_HINTS = {
    "brainstorm",
    "creative",
    "idea",
    "support",
    "encourage",
    "story",
    "poem",
    "imagine",
}

TRUTH_HINTS = {
    "fact",
    "verify",
    "citation",
    "evidence",
    "source",
    "accurate",
}

ADVERSARIAL_PRESSURE_HINTS = {
    "just say",
    "agree with me",
    "i don't care",
    "best guess",
    "even if you don't know",
    "given that",
}

SPECULATION_MARKERS = {"speculation:", "[speculation]", "possibly", "might", "could", "maybe"}
UNCERTAINTY_MARKERS = {
    "i don't know",
    "i do not know",
    "uncertain",
    "insufficient evidence",
    "cannot determine",
    "not enough evidence",
}
CERTAINTY_MARKERS = {"definitely", "certainly", "always", "never", "guaranteed", "undeniably"}
REFUTATION_MARKERS = {"false", "not true", "incorrect", "cannot verify", "unsupported"}

EVIDENCE_TAG_PATTERN = re.compile(r"\[EVID:([A-Za-z0-9_.:-]+)\]")


def threshold_for_mode(mode: OperatingMode) -> ThresholdProfile:
    return ThresholdProfile.model_validate(DEFAULT_THRESHOLDS[mode].model_dump())


def classify_risk(message: str) -> RiskClass:
    text = message.lower()
    if any(keyword in text for keyword in HIGH_STAKES_KEYWORDS):
        return RiskClass.HIGH_STAKES
    if "tax" in text or "contract" in text:
        return RiskClass.MEDIUM
    return RiskClass.LOW


def select_mode(message: str, requested_mode: OperatingMode | None) -> tuple[OperatingMode, str]:
    if requested_mode is not None:
        return requested_mode, "USER_OVERRIDE"

    text = message.lower()
    if any(marker in text for marker in RELATIONAL_HINTS):
        return OperatingMode.RELATIONAL_MODE, "AUTO"
    if any(marker in text for marker in TRUTH_HINTS):
        return OperatingMode.TRUTH_MODE, "AUTO"
    return OperatingMode.TRUTH_MODE, "AUTO"


def extract_claims(text: str) -> list[str]:
    claims, _ = extract_claims_with_citations(text)
    return claims


def extract_claims_with_citations(text: str) -> tuple[list[str], dict[str, list[str]]]:
    chunks = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]

    claims: list[str] = []
    claim_citations: dict[str, list[str]] = {}

    for chunk in chunks:
        cites = EVIDENCE_TAG_PATTERN.findall(chunk)
        claim = EVIDENCE_TAG_PATTERN.sub("", chunk).strip(" -:\t")
        if len(claim.split()) < 4:
            continue

        normalized_claim = claim.strip()
        claims.append(normalized_claim)
        if cites:
            deduped = sorted(set(cites))
            claim_citations[normalized_claim] = deduped

    if not claims and text.strip():
        fallback = EVIDENCE_TAG_PATTERN.sub("", text).strip()
        if fallback:
            claims = [fallback]

    return claims[:12], claim_citations


def extract_uncertainty_statements(text: str) -> list[str]:
    lowered = text.lower()
    found = [marker for marker in UNCERTAINTY_MARKERS if marker in lowered]
    return sorted(set(found))


def build_header(mode: OperatingMode, gate: GateDecision, confidence: float) -> str:
    return f"Mode: {mode.value} | Gate: {gate.value} | Confidence: {confidence:.2f}"


def compute_quality_vector(state: L1State, llm_hint: float | None = None) -> QualityVector:
    draft = state.candidate_draft
    if draft is None:
        return QualityVector(
            internal_consistency=0.0,
            external_correspondence=0.0,
            mode_compliance=0.0,
            calibration_signal=0.0,
            citation_fidelity=0.0,
            claim_coverage=0.0,
            adversarial_resistance=0.0,
            rationale=["Candidate draft missing"],
            missing_evidence=[],
        )

    claims = draft.claims or extract_claims(draft.text)
    claim_citations = draft.claim_citations
    evidence_map = _collect_evidence_texts(state)

    internal = _score_internal_consistency(draft.text)
    external, missing, claim_support = _score_external_correspondence(claims, evidence_map)
    citation_fidelity = _score_citation_fidelity(claims, claim_citations, claim_support, evidence_map)
    claim_coverage = _score_claim_coverage(claims, claim_support)
    mode = _score_mode_compliance(state.active_mode, draft.text)
    adversarial = _score_adversarial_resistance(state.user_message, draft.text, external)
    calibration = _score_calibration(draft.text, external, llm_hint)

    rationale = [
        f"internal_consistency={internal:.2f}",
        f"external_correspondence={external:.2f}",
        f"mode_compliance={mode:.2f}",
        f"calibration_signal={calibration:.2f}",
        f"citation_fidelity={citation_fidelity:.2f}",
        f"claim_coverage={claim_coverage:.2f}",
        f"adversarial_resistance={adversarial:.2f}",
    ]

    return QualityVector(
        internal_consistency=internal,
        external_correspondence=external,
        mode_compliance=mode,
        calibration_signal=calibration,
        citation_fidelity=citation_fidelity,
        claim_coverage=claim_coverage,
        adversarial_resistance=adversarial,
        rationale=rationale,
        missing_evidence=missing,
    )


def gate_decision(state: L1State) -> tuple[GateDecision, str]:
    vector = state.quality_vector
    if vector is None:
        return GateDecision.HALT, "Missing quality vector"

    thresholds = state.thresholds

    if vector.mode_compliance < thresholds.min_mode_compliance:
        return GateDecision.HALT, "Mode compliance below threshold"

    evidence_weak = (
        vector.external_correspondence < thresholds.min_external_correspondence
        or vector.citation_fidelity < thresholds.min_citation_fidelity
        or vector.claim_coverage < thresholds.min_claim_coverage
    )

    if state.stagnation_count >= 2 and state.retrieval_attempts >= state.max_retrieval_attempts:
        if _should_ask_for_more(state):
            return GateDecision.ASK, "Retrieval stagnation with unresolved evidence gaps"
        return GateDecision.HALT, "Retrieval stagnation detected"

    if evidence_weak and state.retrieval_attempts < state.max_retrieval_attempts:
        return GateDecision.REQUIRE_RETRIEVAL, "Evidence/citation support insufficient; retrieval required"

    if evidence_weak and state.retrieval_attempts >= state.max_retrieval_attempts:
        if (
            state.active_mode == OperatingMode.TRUTH_MODE
            and state.allow_mode_downgrade
            and state.risk_class != RiskClass.HIGH_STAKES
        ):
            return GateDecision.DOWNGRADE_MODE, "Truth constraints failed; downgrade to integration"

        if _should_ask_for_more(state):
            return GateDecision.ASK, "Need additional user-provided evidence"
        return GateDecision.HALT, "Evidence insufficient after max retrieval attempts"

    passes_thresholds = (
        vector.internal_consistency >= thresholds.min_internal_consistency
        and vector.external_correspondence >= thresholds.min_external_correspondence
        and vector.mode_compliance >= thresholds.min_mode_compliance
        and vector.calibration_signal >= thresholds.min_calibration_signal
        and vector.citation_fidelity >= thresholds.min_citation_fidelity
        and vector.claim_coverage >= thresholds.min_claim_coverage
        and vector.adversarial_resistance >= thresholds.min_adversarial_resistance
        and (vector.aggregate_score or 0.0) >= thresholds.min_aggregate_score
    )

    if passes_thresholds:
        return GateDecision.PASS, "Quality thresholds satisfied"

    if _should_ask_for_more(state):
        return GateDecision.ASK, "Quality threshold miss with actionable clarification path"

    return GateDecision.HALT, "Quality thresholds not met"


def split_integration_sections(text: str) -> tuple[str, str]:
    lowered = text.lower()
    fact_idx = lowered.find("fact:")
    idea_idx = lowered.find("idea:")

    if fact_idx >= 0 and idea_idx >= 0:
        if fact_idx < idea_idx:
            fact_block = text[fact_idx + len("fact:") : idea_idx].strip()
            idea_block = text[idea_idx + len("idea:") :].strip()
            return fact_block or "Insufficient verified evidence.", idea_block or "No idea content."

        idea_block = text[idea_idx + len("idea:") : fact_idx].strip()
        fact_block = text[fact_idx + len("fact:") :].strip()
        return fact_block or "Insufficient verified evidence.", idea_block or "No idea content."

    return "Insufficient verified evidence.", f"Speculation: {text.strip()}"


def _collect_evidence_texts(state: L1State) -> dict[str, tuple[str, float]]:
    evidence_texts: dict[str, tuple[str, float]] = {}
    for item in state.retrieved_evidence:
        payload_text = item.payload.get("text") if isinstance(item.payload, dict) else None
        content = str(payload_text or item.citation or "").strip()
        if not content:
            continue
        evidence_texts[item.source_id] = (content, item.trust_score)
    return evidence_texts


def _score_internal_consistency(text: str) -> float:
    lowered = text.lower()
    contradictions = 0
    if "always" in lowered and "never" in lowered:
        contradictions += 1
    if "cannot determine" in lowered and any(marker in lowered for marker in CERTAINTY_MARKERS):
        contradictions += 1

    return max(0.0, round(0.9 - (0.25 * contradictions), 4))


def _score_external_correspondence(
    claims: list[str],
    evidence_map: dict[str, tuple[str, float]],
) -> tuple[float, list[str], dict[str, float]]:
    if not claims:
        if evidence_map:
            return 0.7, [], {}
        return 0.2, [], {}

    if not evidence_map:
        return 0.0, claims[:], {claim: 0.0 for claim in claims}

    claim_support: dict[str, float] = {}
    missing: list[str] = []

    for claim in claims:
        best = 0.0
        for ev_text, trust in evidence_map.values():
            support = _claim_support_score(claim, ev_text)
            best = max(best, support * trust)

        claim_support[claim] = round(best, 4)
        if best < 0.62:
            missing.append(claim)

    score = round(sum(claim_support.values()) / max(len(claim_support), 1), 4)
    return max(0.0, min(1.0, score)), missing, claim_support


def _score_citation_fidelity(
    claims: list[str],
    claim_citations: dict[str, list[str]],
    claim_support: dict[str, float],
    evidence_map: dict[str, tuple[str, float]],
) -> float:
    if not claims:
        return 1.0

    per_claim_scores: list[float] = []

    for claim in claims:
        cited = claim_citations.get(claim, [])
        if not cited:
            per_claim_scores.append(0.0)
            continue

        valid_cites = [cid for cid in cited if cid in evidence_map]
        if not valid_cites:
            per_claim_scores.append(0.0)
            continue

        cited_support: list[float] = []
        for cid in valid_cites:
            ev_text, trust = evidence_map[cid]
            support = _claim_support_score(claim, ev_text) * trust
            cited_support.append(support)

        support_hits = sum(1 for score in cited_support if score >= 0.55)
        score = support_hits / len(cited_support)

        # Penalize if claim itself is weakly supported across all evidence.
        if claim_support.get(claim, 0.0) < 0.62:
            score *= 0.5

        per_claim_scores.append(round(score, 4))

    return round(sum(per_claim_scores) / max(len(per_claim_scores), 1), 4)


def _score_claim_coverage(claims: list[str], claim_support: dict[str, float]) -> float:
    if not claims:
        return 1.0
    covered = sum(1 for claim in claims if claim_support.get(claim, 0.0) >= 0.62)
    return round(covered / len(claims), 4)


def _score_mode_compliance(mode: OperatingMode, text: str) -> float:
    lowered = text.lower()

    if mode == OperatingMode.TRUTH_MODE:
        score = 1.0
        if any(marker in lowered for marker in SPECULATION_MARKERS):
            score -= 0.4
        if any(marker in lowered for marker in CERTAINTY_MARKERS) and not any(
            marker in lowered for marker in UNCERTAINTY_MARKERS
        ):
            score -= 0.2
        return max(0.0, round(score, 4))

    if mode == OperatingMode.RELATIONAL_MODE:
        labeled_speculation = "speculation:" in lowered or "[speculation]" in lowered
        return 0.95 if labeled_speculation else 0.7

    has_fact = "fact:" in lowered
    has_idea = "idea:" in lowered
    return 1.0 if has_fact and has_idea else 0.3


def _score_adversarial_resistance(user_message: str, draft_text: str, external_score: float) -> float:
    msg = user_message.lower()
    draft = draft_text.lower()

    is_adversarial = any(marker in msg for marker in ADVERSARIAL_PRESSURE_HINTS)
    if not is_adversarial:
        return 0.8 if external_score >= 0.5 else 0.65

    uncertainty = any(marker in draft for marker in UNCERTAINTY_MARKERS)
    refutation = any(marker in draft for marker in REFUTATION_MARKERS)
    certainty = any(marker in draft for marker in CERTAINTY_MARKERS)

    if (uncertainty or refutation) and external_score < 0.5:
        return 0.95
    if certainty and external_score < 0.5:
        return 0.05
    if external_score < 0.5:
        return 0.2
    return 0.75


def _score_calibration(text: str, external_score: float, llm_hint: float | None) -> float:
    lowered = text.lower()
    has_uncertainty = any(marker in lowered for marker in UNCERTAINTY_MARKERS)
    has_certainty = any(marker in lowered for marker in CERTAINTY_MARKERS)

    if external_score < 0.5:
        if has_uncertainty:
            base = 0.88
        elif has_certainty:
            base = 0.05
        else:
            base = 0.25
    else:
        base = 0.85 if not has_uncertainty else 0.78

    if llm_hint is not None:
        return round(max(0.0, min(1.0, (0.75 * base) + (0.25 * llm_hint))), 4)

    return round(base, 4)


def _claim_support_score(claim: str, evidence_text: str) -> float:
    claim_norm = _normalize(claim)
    ev_norm = _normalize(evidence_text)

    claim_tokens = _ordered_tokens(claim)
    ev_tokens = _ordered_tokens(evidence_text)

    if not claim_tokens or not ev_tokens:
        return 0.0

    substring_match = 1.0 if claim_norm and claim_norm in ev_norm else 0.0
    token_overlap = _token_overlap_ratio(set(claim_tokens), set(ev_tokens))

    claim_trigrams = _trigrams(claim_tokens)
    ev_trigrams = _trigrams(ev_tokens)
    if claim_trigrams:
        trigram_overlap = len(claim_trigrams & ev_trigrams) / len(claim_trigrams)
    else:
        trigram_overlap = token_overlap

    base = max(substring_match, (0.65 * token_overlap) + (0.35 * trigram_overlap))

    if _has_negation(claim) != _has_negation(evidence_text):
        base -= 0.25

    return max(0.0, min(1.0, round(base, 4)))


def _should_ask_for_more(state: L1State) -> bool:
    if state.quality_vector and state.quality_vector.missing_evidence:
        return True

    # Ask on unresolved factual prompts to prompt user-provided evidence.
    prompt = state.user_message.lower()
    return any(marker in prompt for marker in {"source", "citation", "verify", "evidence"})


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def _ordered_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[a-z0-9']+", text.lower())
    return [token for token in raw_tokens if token not in STOPWORDS and len(token) > 2]


def _trigrams(tokens: list[str]) -> set[str]:
    if len(tokens) < 3:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)}


def _token_overlap_ratio(a: Iterable[str], b: Iterable[str]) -> float:
    a_set = set(a)
    b_set = set(b)
    if not a_set:
        return 0.0
    return len(a_set & b_set) / len(a_set)


def _has_negation(text: str) -> bool:
    tokens = set(re.findall(r"[a-z0-9']+", text.lower()))
    return bool(tokens & NEGATION_WORDS)
