# Contributing

## Scope

Keep changes deterministic, PII-safe, auditable, and small. Do not modify files in `candidate_bundle/`; they are challenge source material.

## Development setup

Use Python 3.11 or newer and install the backend from `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[test]
```

## Before submitting a change

1. Add or update deterministic tests for behavioral changes.
2. Run `python -m unittest discover -s tests -v` from `backend/`.
3. Confirm API payloads, logs, exports, and audits contain no raw PII.
4. Preserve unique constraints, stable IDs, atomic exports, and quarantine behavior.
5. Keep commits focused and describe the behavioral result.

## Engineering constraints

- Dispatch actions must be based on explicit, testable application rules—not model inference.
- Unknown operational evidence must produce an explicit insufficient-data/manual-review outcome.
- New input-file formats must be mapped explicitly; ambiguous mappings must quarantine rather than guess.
- Any future AI capability may explain cited evidence only. It must receive minimized/redacted context and cannot approve, dispatch, or mutate operational state.

## Pull requests

Describe the operational behavior changed, affected data contract, test evidence, and any security or PII implications. Avoid bundling unrelated refactors with behavior changes.
