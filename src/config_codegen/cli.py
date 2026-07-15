from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .errors import ConfigError
from .generator import generate
from .models import load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cfggen", description="Generate C switch-case handlers from YAML")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a configuration")
    validate.add_argument("config", type=Path)

    list_parser = subparsers.add_parser("list", help="list protocol items and enabled state")
    list_parser.add_argument("config", type=Path)
    list_parser.add_argument("--enabled-only", action="store_true")

    generate_parser = subparsers.add_parser("generate", help="generate C source and header")
    generate_parser.add_argument("config", type=Path)
    generate_parser.add_argument("--output-root", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            config = load_config(args.config)
            enabled = sum(entry.enabled for entry in config.entries)
            print(f"valid: {len(config.entries)} protocol entries, {enabled} enabled")
            return 0
        if args.command == "list":
            config = load_config(args.config)
            seen: set[tuple[str, str]] = set()
            for entry in config.entries:
                protocol_ref = entry.raw.get("protocol_ref", f"0x{entry.index:04X}:{entry.subindex}")
                identity = (protocol_ref, entry.name)
                if identity in seen:
                    continue
                seen.add(identity)
                read_on = entry.enabled and entry.access != "write_only" and entry.raw.get("read", {}).get("enabled", True)
                write_on = entry.enabled and entry.access != "read_only" and entry.raw.get("write", {}).get("enabled", True)
                enabled = read_on or write_on
                if args.enabled_only and not enabled:
                    continue
                state = "ON " if enabled else "OFF"
                directions = f"{'R' if read_on else '-'}/{'W' if write_on else '-'}"
                status = entry.raw.get("status", "-")
                print(f"{state} {directions}  {protocol_ref:<16} {status:<12} {entry.description or entry.name}")
            return 0
        fragment = generate(args.config, args.output_root)
        print(f"generated: {fragment}")
        return 0
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
