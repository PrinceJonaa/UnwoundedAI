from __future__ import annotations

import hashlib
import re
from typing import Any

from app.graph.policies import (
    build_header,
    classify_risk,
    compute_quality_vector,
    extract_claims_with_citations,
    extract_uncertainty_statements,
    gate_decision,
    select_mode,
    split_integration_sections,
    threshold_for_mode,
)
from app.schemas import (
    CandidateDraft,
    FinalResponse,
    GateDecision,
    L1State,
    L3PromotionCandidate,
    ModeSource,
    OperatingMode,
    SupervisorStage,
)
from app.services.llm import LiteLLMService
from app.services.memory import MemoryService
from app.services.observability import ObservabilityService
from app.services.promotion import L3PromotionPolicy
from app.services.retrieval import RetrievalService

EVID_PATTERN = re.compile(r"\[EVID:([A-Za-z0-9_.:-]+)\]")


class RuntimeNodes:
    def __init__(
        self,
        *,
        llm_service: LiteLLMService,
        retrieval_service: RetrievalService,
        memory_service: MemoryService,
        observability_service: ObservabilityService,
        promotion_policy: L3PromotionPolicy,
    ) -> None:
        self.llm_service = llm_service
        self.retrieval_service = retrieval_service
        self.memory_service = memory_service
        self.observability_service = observability_service
        self.promotion_policy = promotion_policy
        # Process-local verification counters for repeated user-confirmed patterns.
        self._verification_ledger: dict[tuple[str, str], int] = {}
        self._promoted_signatures: set[tuple[str, str]] = set()

    async def ingest(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        trace_id, span_id = await self.observability_service.start_turn(l1)
        l1.trace_id = trace_id
        l1.span_id = span_id

        mem0_context = await self.memory_service.recall(user_id=l1.user_id, message=l1.user_message, limit=5)
        l1.retrieved_evidence = mem0_context
        l1.mem0_context_ids = [item.source_id for item in mem0_context]

        l1.supervisor_stage = SupervisorStage.NEEDS_DRAFT
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def action(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        selected_mode, source = select_mode(l1.user_message, l1.requested_mode)
        l1.active_mode = selected_mode
        l1.mode_source = ModeSource(source)
        l1.thresholds = threshold_for_mode(l1.active_mode)

        l1.risk_class = classify_risk(l1.user_message)
        if l1.risk_class.value == "HIGH_STAKES":
            l1.allow_mode_downgrade = False

        prefetch = await self.retrieval_service.retrieve(
            user_id=l1.user_id,
            user_message=l1.user_message,
            metadata=l1.metadata,
            query_override=l1.metadata.get("search_query_override"),
        )
        if prefetch:
            l1.retrieved_evidence = self._merge_evidence(l1.retrieved_evidence, prefetch)
            l1.retrieval_attempts = max(l1.retrieval_attempts, 1)
            l1.last_retrieval_fingerprint = self._fingerprint_evidence(l1.retrieved_evidence)

        l1.supervisor_stage = SupervisorStage.NEEDS_DRAFT
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def supervisor_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        if l1.supervisor_stage == SupervisorStage.NEEDS_RETRIEVAL:
            l1.next_node = "retriever_agent"
            return l1.model_dump(mode="python")

        if l1.supervisor_stage == SupervisorStage.NEEDS_DRAFT:
            l1.next_node = "drafter_agent"
            return l1.model_dump(mode="python")

        if l1.supervisor_stage == SupervisorStage.NEEDS_VERIFY:
            l1.next_node = "verifier_agent"
            return l1.model_dump(mode="python")

        if l1.supervisor_stage == SupervisorStage.NEEDS_DECISION:
            decision = l1.verifier_recommendation or l1.gate_decision or GateDecision.HALT
            l1.gate_decision = decision

            if decision == GateDecision.PASS:
                l1.next_node = "finalize"
            elif decision == GateDecision.REQUIRE_RETRIEVAL:
                l1.next_node = "retriever_agent"
                l1.supervisor_stage = SupervisorStage.NEEDS_RETRIEVAL
            elif decision == GateDecision.DOWNGRADE_MODE:
                l1.next_node = "downgrade_mode"
            elif decision in {GateDecision.HALT, GateDecision.ASK}:
                l1.next_node = "honest_halt_ask"
            else:
                l1.next_node = "honest_halt_ask"
                l1.gate_decision = GateDecision.HALT

            return l1.model_dump(mode="python")

        l1.gate_decision = GateDecision.HALT
        l1.gate_reason = "Unknown supervisor stage"
        l1.next_node = "honest_halt_ask"
        return l1.model_dump(mode="python")

    async def retriever_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        if l1.retrieval_attempts >= l1.max_retrieval_attempts:
            l1.verifier_recommendation = self._fallback_terminal_decision(l1)
            l1.gate_reason = "Max retrieval attempts reached"
            l1.supervisor_stage = SupervisorStage.NEEDS_DECISION
            l1.next_node = None
            return l1.model_dump(mode="python")

        l1.retrieval_attempts += 1
        query_override = self._build_refined_query(l1)

        new_evidence = await self.retrieval_service.retrieve(
            user_id=l1.user_id,
            user_message=l1.user_message,
            metadata=l1.metadata,
            query_override=query_override,
        )

        l1.retrieved_evidence = self._merge_evidence(l1.retrieved_evidence, new_evidence)

        fingerprint = self._fingerprint_evidence(l1.retrieved_evidence)
        if l1.last_retrieval_fingerprint == fingerprint:
            l1.stagnation_count += 1
        else:
            l1.stagnation_count = 0
        l1.last_retrieval_fingerprint = fingerprint

        l1.supervisor_stage = SupervisorStage.NEEDS_DRAFT
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def drafter_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        evidence_snippets: list[str] = []
        evidence_ids: list[str] = []
        for evidence in l1.retrieved_evidence[:12]:
            text = evidence.payload.get("text") if isinstance(evidence.payload, dict) else None
            snippet = (text or evidence.citation or "").strip()
            if not snippet:
                continue
            snippet = snippet[:240]
            evidence_snippets.append(f"[EVID:{evidence.source_id}] {snippet}")
            evidence_ids.append(evidence.source_id)

        llm_draft = await self.llm_service.draft(
            user_message=l1.user_message,
            mode=l1.active_mode,
            evidence_snippets=evidence_snippets,
        )

        draft_text = self._ensure_draft_citations(llm_draft.text, evidence_ids)
        claims, claim_citations = extract_claims_with_citations(draft_text)

        l1.candidate_draft = CandidateDraft(
            text=draft_text,
            claims=claims,
            claim_citations=claim_citations,
            uncertainty_statements=extract_uncertainty_statements(draft_text),
            citations=sorted({cid for cids in claim_citations.values() for cid in cids}),
        )
        l1.metadata["_llm_confidence_hint"] = llm_draft.confidence_hint

        l1.supervisor_stage = SupervisorStage.NEEDS_VERIFY
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def verifier_agent(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        llm_hint = l1.metadata.get("_llm_confidence_hint")
        hint = float(llm_hint) if isinstance(llm_hint, (int, float)) else None
        l1.quality_vector = compute_quality_vector(l1, llm_hint=hint)

        decision, reason = gate_decision(l1)
        l1.verifier_recommendation = decision
        l1.gate_reason = reason

        await self.observability_service.log_quality(l1)
        await self.observability_service.log_gate(l1)

        l1.supervisor_stage = SupervisorStage.NEEDS_DECISION
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def downgrade_mode(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        l1.active_mode = OperatingMode.INTEGRATION_MODE
        l1.mode_source = ModeSource.GATE_DOWNGRADE
        l1.thresholds = threshold_for_mode(l1.active_mode)
        l1.gate_decision = None
        l1.verifier_recommendation = None
        l1.gate_reason = "Mode downgraded to INTEGRATION_MODE; regenerating draft"

        l1.supervisor_stage = SupervisorStage.NEEDS_DRAFT
        l1.next_node = None
        return l1.model_dump(mode="python")

    async def honest_halt_ask(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        confidence = (l1.quality_vector.aggregate_score if l1.quality_vector else 0.0) or 0.0
        decision = l1.gate_decision or l1.verifier_recommendation or GateDecision.HALT

        if decision == GateDecision.ASK:
            answer = "I need more evidence before I can answer that safely."
        else:
            decision = GateDecision.HALT
            answer = "I can't determine that from available evidence."

        clarifying_question = self._clarifying_question(l1)

        l1.final_response = FinalResponse(
            mode=l1.active_mode,
            gate_decision=decision,
            confidence=round(confidence, 4),
            header=build_header(l1.active_mode, decision, confidence),
            answer=answer,
            clarifying_question=clarifying_question,
            citations=[item.citation for item in l1.retrieved_evidence if item.citation],
        )

        return l1.model_dump(mode="python")

    async def finalize(self, state: dict[str, Any]) -> dict[str, Any]:
        l1 = L1State.model_validate(state)

        if l1.final_response is None:
            confidence = (l1.quality_vector.aggregate_score if l1.quality_vector else 0.0) or 0.0
            decision = l1.gate_decision or GateDecision.HALT

            draft_text = l1.candidate_draft.text if l1.candidate_draft else "I can't determine that from available evidence."
            fact_block: str | None = None
            idea_block: str | None = None
            answer = draft_text

            if l1.active_mode == OperatingMode.INTEGRATION_MODE:
                fact_block, idea_block = split_integration_sections(draft_text)
                answer = f"FACT:\n{fact_block}\n\nIDEA:\n{idea_block}"

            if l1.active_mode == OperatingMode.RELATIONAL_MODE:
                lowered = answer.lower()
                if "speculation:" not in lowered and "[speculation]" not in lowered:
                    answer = f"Speculation: {answer}"

            l1.final_response = FinalResponse(
                mode=l1.active_mode,
                gate_decision=decision,
                confidence=round(confidence, 4),
                header=build_header(l1.active_mode, decision, confidence),
                answer=answer,
                fact_block=fact_block,
                idea_block=idea_block,
                citations=[item.citation for item in l1.retrieved_evidence if item.citation],
            )

        l1 = await self._apply_l3_promotions(l1)
        await self.observability_service.end_turn(l1)

        return l1.model_dump(mode="python")

    async def _apply_l3_promotions(self, l1: L1State) -> L1State:
        extracted = self._extract_memory_candidates(l1)
        if extracted:
            l1.l3_promotion_candidates.extend(extracted)

        user_confirmed = bool(l1.metadata.get("confirm_memory_promotion", False))

        approved: list[L3PromotionCandidate] = []
        for candidate in l1.l3_promotion_candidates:
            # Enforce strict source/type gating before policy checks.
            if candidate.source != "user_message":
                continue
            if candidate.memory_type not in {"preference", "boundary", "stable_rule", "scar"}:
                continue

            signature = self._candidate_signature(candidate)
            key = (l1.user_id, signature)
            verification_count = self._verification_ledger.get(key, 0) + 1
            self._verification_ledger[key] = verification_count
            candidate.verification_count = verification_count

            if self.promotion_policy.should_promote(candidate, user_confirmed=user_confirmed):
                if key in self._promoted_signatures:
                    continue
                approved.append(candidate)

        for candidate in approved:
            await self.memory_service.promote(l1.user_id, candidate)
            signature = self._candidate_signature(candidate)
            self._promoted_signatures.add((l1.user_id, signature))

        return l1

    def _extract_memory_candidates(self, l1: L1State) -> list[L3PromotionCandidate]:
        text = l1.user_message.strip()
        lowered = text.lower()
        candidates: list[L3PromotionCandidate] = []

        if lowered.startswith("remember ") or "remember that" in lowered:
            candidates.append(
                L3PromotionCandidate(
                    key=f"rule.turn.{l1.turn_id}",
                    value=text,
                    memory_type="stable_rule",
                    confidence=0.8,
                    requires_user_confirmation=True,
                    verification_count=0,
                    source="user_message",
                )
            )

        if "my preference is" in lowered:
            candidates.append(
                L3PromotionCandidate(
                    key=f"preference.turn.{l1.turn_id}",
                    value=text,
                    memory_type="preference",
                    confidence=0.75,
                    requires_user_confirmation=True,
                    verification_count=0,
                    source="user_message",
                )
            )

        if self._looks_like_boundary(lowered):
            candidates.append(
                L3PromotionCandidate(
                    key=f"boundary.turn.{l1.turn_id}",
                    value=text,
                    memory_type="boundary",
                    confidence=0.82,
                    requires_user_confirmation=True,
                    verification_count=0,
                    source="user_message",
                )
            )

        return candidates

    def _clarifying_question(self, l1: L1State) -> str | None:
        if l1.quality_vector and l1.quality_vector.missing_evidence:
            gap = l1.quality_vector.missing_evidence[0]
            return f"Can you share a reliable source that supports: '{gap[:120]}'?"

        return "Can you provide a specific source or narrower question so I can verify it?"

    def _fingerprint_evidence(self, evidence: list[Any]) -> str:
        tokens: list[str] = []
        for item in evidence:
            source_id = getattr(item, "source_id", "")
            citation = getattr(item, "citation", "") or ""
            payload = getattr(item, "payload", {})
            url = ""
            if isinstance(payload, dict):
                url = str(payload.get("url") or "")
            tokens.append(f"{source_id}:{citation}:{url}")
        raw = "|".join(sorted(tokens))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _merge_evidence(self, current: list[Any], incoming: list[Any]) -> list[Any]:
        merged: dict[str, Any] = {}

        for item in list(current) + list(incoming):
            payload = getattr(item, "payload", {})
            url = ""
            if isinstance(payload, dict):
                url = str(payload.get("url") or "")
            key = f"url:{url}" if url else f"id:{getattr(item, 'source_id', '')}"
            merged[key] = item

        return list(merged.values())

    def _build_refined_query(self, l1: L1State) -> str:
        if l1.quality_vector and l1.quality_vector.missing_evidence:
            return l1.quality_vector.missing_evidence[0][:200]
        return l1.user_message

    def _fallback_terminal_decision(self, l1: L1State) -> GateDecision:
        if l1.quality_vector and l1.quality_vector.missing_evidence:
            return GateDecision.ASK
        return GateDecision.HALT

    def _ensure_draft_citations(self, text: str, evidence_ids: list[str]) -> str:
        if not evidence_ids:
            return text

        if EVID_PATTERN.search(text):
            return text

        lines = [line.rstrip() for line in text.splitlines()]
        default_id = evidence_ids[0]

        output_lines: list[str] = []
        for line in lines:
            if not line.strip():
                output_lines.append(line)
                continue
            if len(line.split()) < 4:
                output_lines.append(line)
                continue
            output_lines.append(f"{line} [EVID:{default_id}]")

        return "\n".join(output_lines)

    def _candidate_signature(self, candidate: L3PromotionCandidate) -> str:
        normalized = re.sub(r"\s+", " ", candidate.value.lower()).strip()
        raw = f"{candidate.memory_type}:{normalized}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _looks_like_boundary(self, lowered_message: str) -> bool:
        direct_markers = (
            "do not ",
            "don't ",
            "never ",
            "please don't",
            "please do not",
            "avoid ",
        )
        if any(marker in lowered_message for marker in direct_markers):
            return True

        starts_markers = ("dont ", "do not", "never", "avoid")
        return lowered_message.startswith(starts_markers)
