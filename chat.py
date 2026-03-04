from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from app.api.models import AgentRequest, AgentResponse
from app.deps import get_runtime_service
from app.runtime import AgentRuntimeService
from app.schemas import GateDecision, OperatingMode


def _parse_mode(raw: str) -> Optional[OperatingMode]:
    token = raw.strip().lower()
    if token == "truth":
        return OperatingMode.TRUTH_MODE
    if token == "relational":
        return OperatingMode.RELATIONAL_MODE
    if token == "integration":
        return OperatingMode.INTEGRATION_MODE
    return None


def _looks_memory_candidate(text: str) -> bool:
    lowered = text.lower().strip()
    memory_markers = (
        "remember ",
        "remember that",
        "my preference is",
        "do not ",
        "don't ",
        "never ",
        "please do not",
        "please don't",
        "avoid ",
    )
    return any(marker in lowered for marker in memory_markers)


def _print_response(response: AgentResponse) -> None:
    print()
    print(f"Mode: {response.mode.value} | Gate: {response.gate_decision.value} | Confidence: {response.confidence:.2f}")
    print("-" * 72)
    print(response.answer)

    if response.asked_clarifying_question:
        print()
        print(f"Clarifying question: {response.asked_clarifying_question}")

    if response.citations:
        print()
        print("Citations:")
        for citation in response.citations:
            print(f"- {citation}")

    print()


async def _send_turn(
    runtime: AgentRuntimeService,
    *,
    session_id: str,
    user_id: str,
    message: str,
    requested_mode: Optional[OperatingMode],
    allow_mode_downgrade: bool,
    confirm_memory_promotion: bool,
    extra_evidence: Optional[str] = None,
) -> AgentResponse:
    metadata: dict = {}

    if confirm_memory_promotion:
        metadata["confirm_memory_promotion"] = True

    if extra_evidence and extra_evidence.strip():
        metadata["documents"] = [
            {
                "id": f"user-doc-{uuid.uuid4().hex[:8]}",
                "title": "User-provided evidence",
                "citation": "User-provided evidence",
                "text": extra_evidence.strip(),
                "trust_score": 0.78,
            }
        ]

    request = AgentRequest(
        session_id=session_id,
        user_id=user_id,
        message=message,
        requested_mode=requested_mode,
        allow_mode_downgrade=allow_mode_downgrade,
        metadata=metadata,
    )
    return await runtime.respond(request)


async def main() -> None:
    runtime = get_runtime_service()

    print("Unwounded AI CLI")
    print("Commands: /mode truth | /mode relational | /mode integration | /quit")
    print()

    raw_user = input("User ID [local-user]: ").strip()
    user_id = raw_user or "local-user"
    session_id = f"session-{uuid.uuid4().hex[:8]}"

    forced_mode: Optional[OperatingMode] = None

    print(f"Session: {session_id}")
    print()

    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        if user_input.lower() in {"/quit", "/exit"}:
            print("Exiting.")
            break

        if user_input.lower().startswith("/mode"):
            parts = user_input.split(maxsplit=1)
            if len(parts) != 2:
                print("Usage: /mode truth|relational|integration")
                continue

            mode = _parse_mode(parts[1])
            if mode is None:
                print("Invalid mode. Use: truth, relational, integration")
                continue

            forced_mode = mode
            print(f"Forced mode set to {mode.value}")
            continue

        confirm_memory = False
        if _looks_memory_candidate(user_input):
            promote = input("Promote this to long-term memory? [y/N]: ").strip().lower()
            confirm_memory = promote in {"y", "yes"}

        response = await _send_turn(
            runtime,
            session_id=session_id,
            user_id=user_id,
            message=user_input,
            requested_mode=forced_mode,
            allow_mode_downgrade=True,
            confirm_memory_promotion=confirm_memory,
        )
        _print_response(response)

        if response.gate_decision in {GateDecision.HALT, GateDecision.ASK}:
            followup = input("Provide additional evidence/context (or press Enter to continue): ").strip()
            if followup:
                follow_response = await _send_turn(
                    runtime,
                    session_id=session_id,
                    user_id=user_id,
                    message=user_input,
                    requested_mode=forced_mode,
                    allow_mode_downgrade=True,
                    confirm_memory_promotion=False,
                    extra_evidence=followup,
                )
                _print_response(follow_response)


if __name__ == "__main__":
    asyncio.run(main())
