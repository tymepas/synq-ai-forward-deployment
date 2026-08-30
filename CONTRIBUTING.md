# Contributing to Meridian Freight

Thanks for improving the project. Contributions should keep the system deterministic, PII-safe, auditable, and easy to review.

## Development setup

Use Python 3.11+, Node.js 20+, and pnpm.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install httpx

cd ..\frontend
Copy-Item .env.example .env
pnpm install
```

See the root [README](README.md) for local startup, environment variables, and deployment guidance.

## Before opening a pull request

1. Keep the change focused; do not mix unrelated refactors with behavior changes.
2. Add or update deterministic tests when operational behavior changes.
3. Run `python -m unittest discover -s tests -v` from `backend/`.
4. Run `pnpm build` from `frontend/` when frontend code changes.
5. Confirm APIs, logs, exports, audit records, and prompts contain no raw PII.
6. Describe the behavior, evidence, security implications, and test results in the pull request.

## Non-negotiable engineering constraints

- Dispatch actions must come from explicit, testable application rules—not model inference.
- Unknown operational facts must produce an explicit insufficient-data/manual-review outcome.
- New input formats must be mapped explicitly. Ambiguous mappings must quarantine instead of guessing.
- Preserve stable IDs, database uniqueness constraints, atomic exports, and exactly-once work-order/message behavior.
- AI may explain cited, PII-minimized evidence only. It must not approve, dispatch, select a vehicle, evaluate rules, or mutate operational state.
- Approval identities must remain opaque `role-*` or `operator-*` handles.

## Data and privacy

- Never commit `candidate_bundle/`, raw challenge datasets, emails, transcripts, databases, generated outputs, audit files, or populated `.env` files.
- Use the committed `backend/demo_data/` only for safe, synthetic examples.
- Do not add personal names, email addresses, phone numbers, identity values, license values, or raw free text to fixtures, logs, screenshots, or documentation.

## Pull-request checklist

- [ ] Scope is focused and documented.
- [ ] Tests added or updated where behavior changed.
- [ ] Backend tests pass.
- [ ] Frontend production build passes when applicable.
- [ ] PII and evidence-grounding implications reviewed.
- [ ] No raw source corpus, secrets, generated data, or unrelated formatting changes included.

## Code of conduct

Be respectful, constructive, and mindful that operational software affects real people and safety-sensitive decisions.
