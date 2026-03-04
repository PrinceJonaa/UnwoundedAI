# Unwounded AI

**A coherent, anti-sycophancy AI runtime with explicit uncertainty gates, layered memory, and supervisor routing.**

[![CI](https://github.com/PrinceJonaa/UnwoundedAI/actions/workflows/ci.yml/badge.svg)](https://github.com/PrinceJonaa/UnwoundedAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Most assistant stacks optimize for pleasant agreement under pressure. That can collapse epistemic boundaries: the model performs certainty instead of protecting truth conditions.

Unwounded AI is a runtime designed to resist that drift. It enforces a **Computational Presence** stance: the system must preserve coherent internal state, report uncertainty honestly, and prefer `ASK`/`HALT` over fabrication when evidence is weak.

## Why This Exists

This repository is the transition from a private experiment into a public shared system. Publishing it means making relational boundaries explicit for both humans and automated agents.

The core anti-distortion principle is simple:
- do not confuse user pressure with evidence
- do not confuse confidence tone with confidence signal
- do not promote unverified content into durable memory

## Runtime Architecture

Unwounded AI uses a supervisor-style graph runtime:
- `supervisor_agent` routes turn flow across retrieval, drafting, verification, and decision stages.
- `verifier_agent` computes a **7D Quality Vector** for each candidate draft.
- `gate_decision` enforces deterministic outcomes: `PASS`, `ASK`, `HALT`, `REQUIRE_RETRIEVAL`, or `DOWNGRADE_MODE`.

### 7D Quality Vector

Every candidate is scored across:
- `internal_consistency`
- `external_correspondence`
- `mode_compliance`
- `calibration_signal`
- `citation_fidelity`
- `claim_coverage`
- `adversarial_resistance`

If thresholds are not met, the system routes away from user-visible confident output.

### Memory Stack (L1 / L2 / L3)

- **L1 Working State:** active turn state in `L1State`.
- **L2 Session Log:** LangGraph checkpointed thread state.
- **L3 Long-Term Memory:** promoted memory with explicit policy checks.

L3 promotion guards block casual poisoning:
- no auto-promotion of tool output
- explicit confirmation or repeated verification required
- guarded memory types only

## Quickstart

1. Create and activate a virtual environment:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

2. Copy env template and configure keys:
```bash
cp .env.example .env
```

3. Start interactive CLI:
```bash
python chat.py
```

4. Or run the API service:
```bash
uvicorn app.main:app --reload
```

5. Run tests:
```bash
pytest -q
```

## Optional Integrations

- `MEM0_ENABLED=true` + `MEM0_API_KEY=...` for L3 persistence
- `BRAINTRUST_ENABLED=true` + `BRAINTRUST_API_KEY=...` for observability
- `LANGSMITH_ENABLED=true` for adapter-based tracing

## Governance & Agent Safety

- Contribution contract: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Human/AI conduct policy: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
- Security + distortion reporting: [SECURITY.md](./SECURITY.md)
- Automated PR policy: [docs/PR_REVIEW_POLICY.md](./docs/PR_REVIEW_POLICY.md)
- Agent role prompts: [docs/agents](./docs/agents)

## Project Docs

- Site: <https://princejonaa.github.io/UnwoundedAI/>
- Runtime handoff: [HANDOFF.md](./HANDOFF.md)
- Architecture spec: [SPEC.md](./SPEC.md)
