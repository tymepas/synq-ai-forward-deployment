from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Settings, default_settings
from .context import ingest_context
from .db import ContextStore
from .exporter import export_all
from .ingest import ingest_tickets
from .pipeline import process_tickets
from .redaction import PIIRedactor


def _settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(root=Path(args.root).resolve()) if args.root else default_settings()


def _store(settings: Settings) -> ContextStore:
    store = ContextStore(settings.database_path)
    store.initialize()
    return store


def command_ingest(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = _store(settings)
    context = ingest_context(settings, store)
    result = ingest_tickets(settings, store, PIIRedactor())
    print(json.dumps({"context": context, "tickets": result}, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = _store(settings)
    context = ingest_context(settings, store)
    result = ingest_tickets(settings, store, PIIRedactor())
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps({"context": context, "validation": result, "status": "PASS"}, sort_keys=True))
    return 0


def command_run(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = _store(settings)
    context = ingest_context(settings, store)
    result = ingest_tickets(settings, store, PIIRedactor())
    processing = process_tickets(store)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps({"context": context, "ingestion": result, "processing": processing, "status": "PASS"}, sort_keys=True))
    return 0


def command_process(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = _store(settings)
    result = process_tickets(store)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


def command_query(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = _store(settings)
    if args.ticket_id:
        rows = store.read_rows(
            "SELECT ticket_id, normalized_vehicle, created_at FROM tickets WHERE ticket_id = ?", (args.ticket_id.upper(),)
        )
    else:
        rows = store.read_rows("SELECT ticket_id, normalized_vehicle, created_at FROM tickets ORDER BY ticket_id")
    print(json.dumps(rows, ensure_ascii=True, sort_keys=True))
    return 0


def command_approve(args: argparse.Namespace) -> int:
    print("approve is unavailable until pending-message processing is installed", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.run")
    parser.add_argument("--root", help="Project root containing candidate_bundle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, handler in {
        "ingest": command_ingest,
        "validate": command_validate,
        "run": command_run,
        "process": command_process,
        "query": command_query,
        "approve": command_approve,
    }.items():
        child = subparsers.add_parser(name)
        child.set_defaults(handler=handler)
        child.add_argument("--root", help=argparse.SUPPRESS)
        if name == "query":
            child.add_argument("--ticket-id")
    return parser


def main(default_command: str | None = None) -> int:
    parser = build_parser()
    argv = sys.argv[1:]
    if default_command and (not argv or argv[0].startswith("-")):
        argv = [default_command, *argv]
    args = parser.parse_args(argv)
    return args.handler(args)
