from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from app.schemas import L3PromotionCandidate, RetrievedEvidence

logger = logging.getLogger(__name__)


class MemoryService:
    async def recall(self, user_id: str, message: str, limit: int = 5) -> list[RetrievedEvidence]:
        raise NotImplementedError

    async def promote(self, user_id: str, candidate: L3PromotionCandidate) -> bool:
        raise NotImplementedError


class InMemoryMemoryService(MemoryService):
    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = defaultdict(list)

    async def recall(self, user_id: str, message: str, limit: int = 5) -> list[RetrievedEvidence]:
        memories = self._store.get(user_id, [])[-limit:]
        results: list[RetrievedEvidence] = []
        for idx, memory in enumerate(memories):
            results.append(
                RetrievedEvidence(
                    source_id=f"mem-{idx}",
                    source_type="mem0",
                    citation=memory.get("key"),
                    trust_score=0.65,
                    supports_claims=[],
                    payload=memory,
                )
            )
        return results

    async def promote(self, user_id: str, candidate: L3PromotionCandidate) -> bool:
        self._store[user_id].append(candidate.model_dump())
        return True


class Mem0MemoryService(MemoryService):
    def __init__(self, api_key: str | None = None) -> None:
        self._client = self._build_client(api_key)

    def _build_client(self, api_key: str | None):
        try:
            from mem0 import MemoryClient

            kwargs: dict[str, Any] = {}
            if api_key:
                kwargs["api_key"] = api_key
            return MemoryClient(**kwargs)
        except Exception:
            pass

        try:
            from mem0 import Memory

            config: dict[str, Any] = {}
            if api_key:
                config["api_key"] = api_key
            return Memory.from_config(config=config)
        except Exception as exc:
            logger.warning("Mem0 unavailable, memory integration disabled: %s", exc)
            return None

    async def recall(self, user_id: str, message: str, limit: int = 5) -> list[RetrievedEvidence]:
        if self._client is None:
            return []

        raw_results: Any = None
        try:
            if hasattr(self._client, "search"):
                raw_results = self._client.search(message, user_id=user_id, limit=limit)
            elif hasattr(self._client, "query"):
                raw_results = self._client.query(message, user_id=user_id, limit=limit)
        except Exception as exc:  # pragma: no cover - networked SDK variability
            logger.warning("Mem0 recall failed: %s", exc)
            return []

        normalized: list[dict[str, Any]] = self._normalize_results(raw_results)
        output: list[RetrievedEvidence] = []
        for idx, item in enumerate(normalized):
            output.append(
                RetrievedEvidence(
                    source_id=str(item.get("id", f"mem0-{idx}")),
                    source_type="mem0",
                    citation=item.get("memory") or item.get("text") or item.get("id"),
                    trust_score=float(item.get("score", 0.7) or 0.7),
                    supports_claims=item.get("supports_claims", []) or [],
                    payload=item,
                )
            )
        return output

    async def promote(self, user_id: str, candidate: L3PromotionCandidate) -> bool:
        if self._client is None:
            return False

        payload = {
            "key": candidate.key,
            "value": candidate.value,
            "memory_type": candidate.memory_type,
            "confidence": candidate.confidence,
        }
        try:
            if hasattr(self._client, "add"):
                self._client.add(payload, user_id=user_id)
                return True
            if hasattr(self._client, "append"):
                self._client.append(payload, user_id=user_id)
                return True
            return False
        except Exception as exc:  # pragma: no cover - networked SDK variability
            logger.warning("Mem0 promotion failed: %s", exc)
            return False

    def _normalize_results(self, raw_results: Any) -> list[dict[str, Any]]:
        if raw_results is None:
            return []
        if isinstance(raw_results, list):
            return [item for item in raw_results if isinstance(item, dict)]
        if isinstance(raw_results, dict):
            if isinstance(raw_results.get("results"), list):
                return [item for item in raw_results["results"] if isinstance(item, dict)]
            if isinstance(raw_results.get("data"), list):
                return [item for item in raw_results["data"] if isinstance(item, dict)]
        return []
