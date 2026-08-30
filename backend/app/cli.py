from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import Settings, default_settings
from .approval import approve_message
from .exporter import export_all
from .pipeline import process_tickets
from .query_service import query_ticket, query_vehicle
from .service import get_store, ingest_selected_input, run_pipeline


def _settings_from_args(args: argparse.Namespace) -> Settings:
    return Settings(root=Path(args.root).resolve()) if args.root else default_settings()


def command_ingest(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = get_store(settings)
    from .context import ingest_context
    context = ingest_context(settings, store)
    result, input_status = ingest_selected_input(settings, store, args.input)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps({"context": context, "tickets": result, "input": input_status}, sort_keys=True))
    return 0


def command_validate(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = get_store(settings)
    from .context import ingest_context
    context = ingest_context(settings, store)
    result, input_status = ingest_selected_input(settings, store, args.input)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps({"context": context, "validation": result, "input": input_status, "status": "PASS"}, sort_keys=True))
    return 0


def command_run(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    result = run_pipeline(settings, args.input)
    print(json.dumps(result, sort_keys=True))
    return 0


def command_process(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = get_store(settings)
    result = process_tickets(store)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


def command_query(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = get_store(settings)
    if args.ticket_id:
        result = query_ticket(store, args.ticket_id)
    elif args.vehicle_reg:
        result = query_vehicle(store, args.vehicle_reg)
    else:
        result = {"status": "INSUFFICIENT_DATA", "reason": "supply_ticket_id_or_vehicle_reg", "citations": []}
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


def command_approve(args: argparse.Namespace) -> int:
    settings = _settings_from_args(args)
    store = get_store(settings)
    result = approve_message(store, args.ticket_id, args.approved_by, args.approved_at)
    export_all(store, settings.outputs_dir, settings.audit_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


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
        if name in {"ingest", "validate", "run"}:
            child.add_argument("--input", help="Changed-format surprise ticket file")
        if name == "query":
            child.add_argument("--ticket-id")
            child.add_argument("--vehicle-reg")
        if name == "approve":
            child.add_argument("--ticket-id", required=True)
            child.add_argument("--approved-by", required=True)
            child.add_argument("--approved-at", required=True)
    return parser


def main(default_command: str | None = None) -> int:
    parser = build_parser()
    argv = sys.argv[1:]
    if default_command and (not argv or argv[0].startswith("-")):
        argv = [default_command, *argv]
    args = parser.parse_args(argv)
    return args.handler(args)
