# Contributing

Thanks for contributing to Unwounded AI.

## Development setup

1. Create and activate a virtual environment.
2. Install dependencies.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run locally

```bash
uvicorn app.main:app --reload
```

## Tests

```bash
pytest -q
```

## Pull request expectations

- Keep changes focused and explain intent in the PR description.
- Add or update tests when behavior changes.
- Keep CI green before requesting review.
- Use clear commit messages.

## Branching

- Base branch: `main`
- Feature branches: `feature/<short-name>` or `fix/<short-name>`

## Code style

- Follow existing patterns in `app/` and `tests/`.
- Prefer small, composable functions.
- Keep high-risk decisions explicit and test-covered.
