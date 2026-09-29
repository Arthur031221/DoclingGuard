"""Command line entry point for Docling JSON checks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .core import DocumentError, check_document, compare_documents, load_document
from .demo import write_fixture


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="docling-guard", description="Validate and compare Docling JSON exports offline."
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("demo", help="Create a synthetic before and after fixture")
    check = commands.add_parser("check", help="Validate provenance and table geometry")
    check.add_argument("document", type=Path)
    check.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    check.add_argument("--fail-on-warning", action="store_true")
    compare = commands.add_parser("compare", help="Compare two extraction exports")
    compare.add_argument("before", type=Path)
    compare.add_argument("after", type=Path)
    compare.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    compare.add_argument("--fail-on-drop", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "demo":
        print(write_fixture())
        return 0
    try:
        if args.command == "check":
            report = check_document(load_document(args.document))
            if args.json:
                print(
                    json.dumps(
                        {"fingerprint": report["fingerprint"], "findings": report["findings"]},
                        indent=2,
                    )
                )
            else:
                print(f"Text items: {report['fingerprint']['text_items']}")
                print(f"Tables: {report['fingerprint']['tables']}")
                print(f"Findings: {len(report['findings'])}")
                for item in report["findings"]:
                    print(f"{item['severity']} {item['code']} {item['location']}: {item['detail']}")
            if any(item["severity"] == "error" for item in report["findings"]):
                return 2
            if args.fail_on_warning and report["findings"]:
                return 1
            return 0
        report = compare_documents(load_document(args.before), load_document(args.after))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Before: {report['before']}")
            print(f"After: {report['after']}")
            print(f"Drops: {report['drops']}")
            print(f"Removed text items: {report['removed_text_items']}")
            print(f"Added text items: {report['added_text_items']}")
            print(f"Candidate findings: {len(report['after_findings'])}")
        if any(item["severity"] == "error" for item in report["after_findings"]):
            return 2
        return 1 if args.fail_on_drop and report["drops"] else 0
    except DocumentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
