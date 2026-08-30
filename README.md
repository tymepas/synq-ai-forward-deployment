# Meridian Freight breakdown-to-resolution MVP

This is a deterministic, local, CLI-first implementation for the Synq AI FDE challenge. It has no server, frontend, or network delivery path.

## Run

From this directory on a clean Windows machine with Python 3.11+:

```powershell
./run.ps1
```

The command creates a virtual environment, installs the single XLSX dependency, ingests the local corpus, processes valid tickets, and regenerates all exports.

## Commands

```powershell
python -m app.run
python -m app.ingest
python -m app.process
python -m app.query --ticket-id TKT-0020
python -m app.query --vehicle-reg UP86CM7252
python -m app.approve --ticket-id TKT-0020 --approved-by role-dispatch --approved-at 2026-08-30T10:00:00+05:30
python -m app.validate
python -m app.run --input C:\path\to\surprise.csv
```

`approved_by` must be an opaque `role-*` or `operator-*` handle. Approval writes only to the local `comms_sent` outbox; it never sends a network request.

## Safety model

- Raw source files remain in `candidate_bundle` and are never copied into the SQLite context store.
- Ticket and maintenance free text are reduced to safe structured features before persistence.
- Names, phones, emails, Aadhaar, license values, and mechanic fields are not persisted or exported.
- Rules are deterministic. Missing live availability, service due date, route topology, refrigeration, pairing, or hub-distance evidence creates a manual hold.
- SQLite unique constraints and deterministic IDs prevent duplicate work orders and messages.
- JSONL exports are regenerated in deterministic sort order and written atomically.

## Outputs

- `outputs/work_orders.jsonl`: exactly one work order per valid canonical ticket.
- `outputs/comms_pending.jsonl`: approval-gated client drafts with safe decision context and citations.
- `outputs/comms_sent.jsonl`: approved local outbox records only.
- `outputs/quarantine.jsonl`: invalid tickets and unmappable surprise files, with reason codes.
- `audit/audit.jsonl`: deterministic, cited decision trail.

## Surprise files

The adapter supports documented JSON/CSV aliases such as `ticketId`, `timestamp`, `vehicleReg`, `origin`, `problem`, `priority`, and `customer`. Missing or ambiguous mappings produce a file-level quarantine and zero actions. It never guesses a schema.

## Tests

```powershell
python -m unittest discover -s tests -v
```
