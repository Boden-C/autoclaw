from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from skills.drake.pages import get_page, render_search_results
from skills.drake.validate import parse_load_payload, render_summary, validate_form


def emit(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    sys.stdout.buffer.write((text + "\n").encode(encoding, errors="backslashreplace"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and load Drake CSV input page forms.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search local Drake input page instructions.")
    search_parser.add_argument("query", help="Input page or search text.")

    load_parser = subparsers.add_parser("load", help="Validate CSV payloads and open the Drake load UI.")
    load_parser.add_argument(
        "--json",
        type=Path,
        help="Read load payload JSON from a file instead of stdin.",
    )
    load_parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Validate and print summaries without opening the UI.",
    )

    return parser.parse_args()


def run_search(args: argparse.Namespace) -> int:
    emit(render_search_results(args.query))
    return 0


def run_load(args: argparse.Namespace) -> int:
    payload_text = args.json.read_text(encoding="utf-8") if args.json else sys.stdin.read()
    if not payload_text.strip():
        raise RuntimeError("load requires JSON on stdin or --json path.")

    payload = json.loads(payload_text)
    form_inputs = parse_load_payload(payload)
    validated_forms = []
    for form_input in form_inputs:
        page = get_page(form_input["page"])
        validated = validate_form(page, form_input["csv_text"], form_input["activation_key"])
        validated_forms.append(validated)

    emit("\n\n".join(render_summary(form) for form in validated_forms))
    if not args.no_ui:
        from skills.drake.ui import launch

        launch(validated_forms)
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "search":
        return run_search(args)
    if args.command == "load":
        return run_load(args)
    raise RuntimeError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
