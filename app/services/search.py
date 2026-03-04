from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Protocol

import anyio

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    id: str
    title: str
    url: str
    snippet: str
    content: str


class WebSearchClient(Protocol):
    async def search(self, query: str, max_results: int = 5, timeout_seconds: float = 8.0) -> list[SearchResult]:
        ...


class NullSearchClient:
    async def search(self, query: str, max_results: int = 5, timeout_seconds: float = 8.0) -> list[SearchResult]:
        return []


class DuckDuckGoSearchClient:
    async def search(self, query: str, max_results: int = 5, timeout_seconds: float = 8.0) -> list[SearchResult]:
        def _run() -> list[SearchResult]:
            try:
                from duckduckgo_search import DDGS
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.warning("duckduckgo-search unavailable, returning no web results: %s", exc)
                return []

            rows: list[dict] = []
            with DDGS(timeout=timeout_seconds) as ddgs:
                for item in ddgs.text(query, max_results=max_results):
                    if isinstance(item, dict):
                        rows.append(item)

            output: list[SearchResult] = []
            for item in rows:
                title = str(item.get("title") or "").strip()
                url = str(item.get("href") or item.get("url") or "").strip()
                snippet = str(item.get("body") or item.get("snippet") or "").strip()
                if not url and not snippet:
                    continue

                source_id = "ddg-" + hashlib.sha1(f"{url}|{title}|{snippet}".encode("utf-8")).hexdigest()[:10]
                output.append(
                    SearchResult(
                        id=source_id,
                        title=title or "DuckDuckGo Result",
                        url=url,
                        snippet=snippet,
                        content=snippet,
                    )
                )
            return output

        try:
            return await anyio.to_thread.run_sync(_run)
        except Exception as exc:  # pragma: no cover - network/runtime variability
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []


class TavilySearchClient:
    def __init__(self, api_key: str | None) -> None:
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 5, timeout_seconds: float = 8.0) -> list[SearchResult]:
        if not self.api_key:
            return []

        def _run() -> list[SearchResult]:
            try:
                from tavily import TavilyClient
            except Exception as exc:  # pragma: no cover - optional dependency
                logger.warning("tavily-python unavailable, returning no web results: %s", exc)
                return []

            client = TavilyClient(api_key=self.api_key)
            result = client.search(query=query, max_results=max_results, search_depth="basic")
            items = result.get("results", []) if isinstance(result, dict) else []

            output: list[SearchResult] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                url = str(item.get("url") or "").strip()
                content = str(item.get("content") or item.get("snippet") or "").strip()
                snippet = content[:280]
                if not url and not content:
                    continue

                source_id = "tavily-" + hashlib.sha1(f"{url}|{title}|{content}".encode("utf-8")).hexdigest()[:10]
                output.append(
                    SearchResult(
                        id=source_id,
                        title=title or "Tavily Result",
                        url=url,
                        snippet=snippet,
                        content=content,
                    )
                )
            return output

        try:
            return await anyio.to_thread.run_sync(_run)
        except Exception as exc:  # pragma: no cover - network/runtime variability
            logger.warning("Tavily search failed: %s", exc)
            return []
