# Unwounded AI

Production-oriented runtime implementing uncertainty-first agent behavior.

[![CI](https://github.com/PrinceJonaa/UnwoundedAI/actions/workflows/ci.yml/badge.svg)](https://github.com/PrinceJonaa/UnwoundedAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run

```bash
uvicorn app.main:app --reload
```

## Demo

```bash
python demo.py
```

## Test

```bash
pytest -q
```

## Optional Integrations

- `MEM0_ENABLED=true` with `MEM0_API_KEY=...` to enable Mem0 L3 persistence.
- `BRAINTRUST_ENABLED=true` with `BRAINTRUST_API_KEY=...` to enable Braintrust logging.
- `LANGSMITH_ENABLED=true` to use LangSmith adapter.

## Project Docs

- Website (GitHub Pages): <https://princejonaa.github.io/UnwoundedAI/>
- Contributing guide: [CONTRIBUTING.md](./CONTRIBUTING.md)
- Security policy: [SECURITY.md](./SECURITY.md)
- Code of conduct: [CODE_OF_CONDUCT.md](./CODE_OF_CONDUCT.md)
