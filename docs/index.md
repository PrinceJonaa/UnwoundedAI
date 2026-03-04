# Unwounded AI

Uncertainty-first agent runtime focused on calibrated behavior and safe mode gating.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

## Repository

- Source: [GitHub repository](https://github.com/PrinceJonaa/UnwoundedAI)
- API runtime: `app/main.py`
- Policies: `app/graph/policies.py`
- Tests: `tests/`
