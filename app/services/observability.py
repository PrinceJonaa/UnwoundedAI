from __future__ import annotations

import logging
import uuid
from typing import Any

from app.schemas import L1State

logger = logging.getLogger(__name__)


class ObservabilityService:
    async def start_turn(self, state: L1State) -> tuple[str, str]:
        raise NotImplementedError

    async def log_quality(self, state: L1State) -> None:
        raise NotImplementedError

    async def log_gate(self, state: L1State) -> None:
        raise NotImplementedError

    async def end_turn(self, state: L1State) -> None:
        raise NotImplementedError


class NullObservabilityService(ObservabilityService):
    async def start_turn(self, state: L1State) -> tuple[str, str]:
        return str(uuid.uuid4()), str(uuid.uuid4())

    async def log_quality(self, state: L1State) -> None:
        return None

    async def log_gate(self, state: L1State) -> None:
        return None

    async def end_turn(self, state: L1State) -> None:
        return None


class BraintrustObservabilityService(ObservabilityService):
    def __init__(self, project: str, api_key: str | None = None) -> None:
        self.project = project
        self._braintrust: Any = None
        try:
            import braintrust

            self._braintrust = braintrust
            # API differences exist across versions; this is best-effort and optional.
            if hasattr(braintrust, "init_logger"):
                kwargs: dict[str, Any] = {"project": project}
                if api_key:
                    kwargs["api_key"] = api_key
                braintrust.init_logger(**kwargs)
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            logger.warning("Braintrust init failed, falling back to null logging: %s", exc)
            self._braintrust = None

    async def start_turn(self, state: L1State) -> tuple[str, str]:
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        self._log(
            event="turn_start",
            payload={
                "session_id": state.session_id,
                "user_id": state.user_id,
                "turn_id": state.turn_id,
                "mode": state.active_mode.value,
                "trace_id": trace_id,
                "span_id": span_id,
            },
        )
        return trace_id, span_id

    async def log_quality(self, state: L1State) -> None:
        if state.quality_vector is None:
            return
        self._log(
            event="quality_vector",
            payload={
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "mode": state.active_mode.value,
                "quality_vector": state.quality_vector.model_dump(),
            },
        )

    async def log_gate(self, state: L1State) -> None:
        self._log(
            event="gate_decision",
            payload={
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "gate_decision": state.gate_decision.value if state.gate_decision else None,
                "gate_reason": state.gate_reason,
                "retrieval_attempts": state.retrieval_attempts,
            },
        )

    async def end_turn(self, state: L1State) -> None:
        self._log(
            event="turn_end",
            payload={
                "session_id": state.session_id,
                "turn_id": state.turn_id,
                "mode": state.active_mode.value,
                "gate_decision": state.gate_decision.value if state.gate_decision else None,
            },
        )

    def _log(self, event: str, payload: dict[str, Any]) -> None:
        if self._braintrust is None:
            logger.info("%s: %s", event, payload)
            return
        try:  # pragma: no cover - versioned SDK behavior
            if hasattr(self._braintrust, "log"):
                self._braintrust.log(event=event, **payload)
            else:
                logger.info("%s: %s", event, payload)
        except Exception:
            logger.info("%s: %s", event, payload)


class LangSmithObservabilityAdapter(ObservabilityService):
    def __init__(self, project: str) -> None:
        self.project = project
        self._client: Any = None
        try:
            from langsmith import Client

            self._client = Client()
        except Exception as exc:  # pragma: no cover - optional dependency behavior
            logger.warning("LangSmith init failed, falling back to null logging: %s", exc)
            self._client = None

    async def start_turn(self, state: L1State) -> tuple[str, str]:
        return str(uuid.uuid4()), str(uuid.uuid4())

    async def log_quality(self, state: L1State) -> None:
        if self._client is None or state.quality_vector is None:
            return
        logger.debug("LangSmith quality log: %s", state.quality_vector.model_dump())

    async def log_gate(self, state: L1State) -> None:
        if self._client is None:
            return
        logger.debug("LangSmith gate log: %s", state.gate_decision)

    async def end_turn(self, state: L1State) -> None:
        if self._client is None:
            return
        logger.debug("LangSmith end turn: %s", state.turn_id)
