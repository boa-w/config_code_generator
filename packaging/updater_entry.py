from __future__ import annotations

import argparse
from pathlib import Path

from config_codegen.update.installer import run_update


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Config Code Generator updater")
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--staging", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    return run_update(args.source, args.target, args.pid, args.staging)


if __name__ == "__main__":
    raise SystemExit(main())
