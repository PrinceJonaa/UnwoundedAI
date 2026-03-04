from __future__ import annotations

from typing import Any

from app.schemas import RetrievedEvidence
from app.services.memory import MemoryService
from app.services.search import WebSearchClient


class RetrievalService:
    def __init__(
        self,
        memory_service: MemoryService,
        search_client: WebSearchClient,
        *,
        search_max_results: int = 5,
        search_timeout_seconds: float = 8.0,
    ) -> None:
        self.memory_service = memory_service
        self.search_client = search_client
        self.search_max_results = search_max_results
        self.search_timeout_seconds = search_timeout_seconds

    async def retrieve(
        self,
        user_id: str,
        user_message: str,
        metadata: dict[str, Any] | None = None,
        query_override: str | None = None,
    ) -> list[RetrievedEvidence]:
        metadata = metadata or {}
        evidence: list[RetrievedEvidence] = []

        # L3 retrieval from Mem0 / in-memory memory.
        evidence.extend(await self.memory_service.recall(user_id=user_id, message=user_message, limit=5))

        search_disabled = bool(metadata.get("search_disabled", False))
        if not search_disabled:
            query = (
                query_override
                or metadata.get("search_query_override")
                or user_message
            )
            web_results = await self.search_client.search(
                str(query),
                max_results=self.search_max_results,
                timeout_seconds=self.search_timeout_seconds,
            )
            for result in web_results:
                evidence.append(
                    RetrievedEvidence(
                        source_id=result.id,
                        source_type="tool",
                        citation=f"{result.title} ({result.url})" if result.url else result.title,
                        trust_score=0.68,
                        supports_claims=[],
                        payload={
                            "text": result.content or result.snippet,
                            "url": result.url,
                            "title": result.title,
                            "snippet": result.snippet,
                            "query": query,
                        },
                    )
                )

        # Optional caller-supplied retrieval documents.
        for idx, doc in enumerate(metadata.get("documents", []) or []):
            if not isinstance(doc, dict):
                continue
            evidence.append(
                RetrievedEvidence(
                    source_id=str(doc.get("id", f"doc-{idx}")),
                    source_type="retrieval",
                    citation=doc.get("citation") or doc.get("title"),
                    trust_score=float(doc.get("trust_score", 0.72)),
                    supports_claims=doc.get("supports_claims", []) or [],
                    payload={
                        "text": doc.get("text", ""),
                        "url": doc.get("url", ""),
                        "title": doc.get("title", ""),
                    },
                )
            )

        return self._dedupe_evidence(evidence)

    def _dedupe_evidence(self, evidence: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
        merged: dict[str, RetrievedEvidence] = {}
        for item in evidence:
            key = self._evidence_key(item)
            merged[key] = item
        return list(merged.values())

    def _evidence_key(self, item: RetrievedEvidence) -> str:
        if isinstance(item.payload, dict):
            url = str(item.payload.get("url") or "").strip()
            if url:
                return f"url:{url}"
        return f"id:{item.source_id}"
