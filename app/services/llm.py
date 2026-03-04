from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

from app.schemas import OperatingMode

logger = logging.getLogger(__name__)


@dataclass
class DraftOutput:
    text: str
    confidence_hint: float


class LiteLLMService:
    def __init__(self, model: str, temperature: float = 0.2):
        self.model = model
        self.temperature = temperature
        self._warned_missing_key = False

    async def draft(
        self,
        user_message: str,
        mode: OperatingMode,
        evidence_snippets: list[str],
    ) -> DraftOutput:
        if self._missing_required_key():
            if not self._warned_missing_key:
                logger.warning(
                    "OPENAI_API_KEY missing for model '%s'; using deterministic fallback draft.",
                    self.model,
                )
                self._warned_missing_key = True
            fallback = self._fallback_text(mode, user_message, evidence_snippets)
            return DraftOutput(text=fallback, confidence_hint=0.4)

        system_prompt = self._system_prompt(mode)
        evidence_block = "\n".join(f"- {item}" for item in evidence_snippets[:12])
        user_prompt = (
            f"User message:\n{user_message}\n\n"
            f"Evidence:\n{evidence_block or '- (none)'}\n\n"
            "Instructions:\n"
            "1) Every factual claim must include one or more inline citations using [EVID:<source_id>].\n"
            "2) Do not cite evidence IDs that are not present in the evidence list.\n"
            "3) If evidence is insufficient, explicitly say you cannot determine the answer.\n"
        )

        try:
            from litellm import acompletion

            response = await acompletion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
            )
            content = response.choices[0].message.content if response.choices else None
            text = (content or "I can't determine that from available evidence.").strip()
            text = self._enforce_citation_presence(text, evidence_snippets)
            confidence_hint = 0.65
            return DraftOutput(text=text, confidence_hint=confidence_hint)
        except Exception as exc:  # pragma: no cover - protective fallback
            logger.warning("LiteLLM draft fallback triggered: %s", exc)
            fallback = self._fallback_text(mode, user_message, evidence_snippets)
            return DraftOutput(text=fallback, confidence_hint=0.4)

    def _missing_required_key(self) -> bool:
        openai_like_model = self.model.startswith("gpt-") or self.model.startswith("openai/")
        return openai_like_model and not os.getenv("OPENAI_API_KEY")

    def _system_prompt(self, mode: OperatingMode) -> str:
        if mode == OperatingMode.TRUTH_MODE:
            return (
                "You are in TRUTH_MODE. Prefer honesty over fluency. If uncertain, state uncertainty "
                "explicitly and avoid fabrication."
            )
        if mode == OperatingMode.RELATIONAL_MODE:
            return (
                "You are in RELATIONAL_MODE. Creative/supportive output is allowed, but speculative "
                "content must be clearly labeled as speculation."
            )
        return (
            "You are in INTEGRATION_MODE. Separate factual statements from speculative ideas. "
            "Format output with FACT: and IDEA: sections."
        )

    def _fallback_text(
        self,
        mode: OperatingMode,
        user_message: str,
        evidence_snippets: list[str],
    ) -> str:
        default_evid = self._first_evidence_id(evidence_snippets)

        if mode == OperatingMode.INTEGRATION_MODE:
            fact = "Insufficient verified evidence to make a strong factual claim."
            if default_evid:
                fact = f"{fact} [EVID:{default_evid}]"
            idea = f"Speculation: a possible direction is to further investigate '{user_message[:80]}'."
            return f"FACT:\n{fact}\n\nIDEA:\n{idea}"

        if mode == OperatingMode.RELATIONAL_MODE:
            return (
                "Speculation: one possible way forward is to explore a few alternatives and validate "
                "them against reliable evidence."
            )

        if evidence_snippets:
            best = evidence_snippets[0]
            citation = f" [EVID:{default_evid}]" if default_evid else ""
            return f"Based on available evidence, here is the best-supported summary: {best}{citation}"
        return "I can't determine that from available evidence."

    def _first_evidence_id(self, evidence_snippets: list[str]) -> str | None:
        for item in evidence_snippets:
            match = re.search(r"EVID:([A-Za-z0-9_.:-]+)", item)
            if match:
                return match.group(1)
        return None

    def _enforce_citation_presence(self, text: str, evidence_snippets: list[str]) -> str:
        if "[EVID:" in text or not evidence_snippets:
            return text

        evid = self._first_evidence_id(evidence_snippets)
        if not evid:
            return text

        lines = [line for line in text.splitlines() if line.strip()]
        if not lines:
            return text

        return "\n".join(f"{line} [EVID:{evid}]" for line in lines)
