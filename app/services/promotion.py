from __future__ import annotations

from app.schemas import L3PromotionCandidate


class L3PromotionPolicy:
    """Controls promotion of candidate memories into L3 (Mem0)."""

    def should_promote(
        self,
        candidate: L3PromotionCandidate,
        *,
        user_confirmed: bool = False,
    ) -> bool:
        # Never auto-ingest assistant or tool emissions into long-term memory.
        if candidate.source != "user_message":
            return False

        allowed_types = {"preference", "boundary", "stable_rule"}
        if candidate.memory_type not in allowed_types and candidate.memory_type != "scar":
            return False

        # Scars are highly sensitive and only written with explicit user approval.
        if candidate.memory_type == "scar":
            return user_confirmed and candidate.confidence >= 0.85

        # Primary path: explicit user confirmation.
        if user_confirmed and candidate.confidence >= 0.6:
            return True

        # Secondary path: repeated cross-turn verification.
        return candidate.verification_count >= 2 and candidate.confidence >= 0.8
