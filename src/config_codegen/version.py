from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess


# This is the only manually maintained version value.
BASE_VERSION = "0.1.0"
_COMMIT_ENV = "CONFIG_CODE_GENERATOR_COMMIT"
_BUILD_NUMBER_ENV = "CONFIG_CODE_GENERATOR_BUILD_NUMBER"
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


@dataclass(frozen=True)
class VersionInfo:
    base_version: str
    commit: str
    version: str
    build_number: int


def _normalize_commit(value: str | None) -> str:
    candidate = (value or "").strip()
    if not _COMMIT_PATTERN.fullmatch(candidate):
        return "unknown"
    return candidate[:8].lower()


def get_commit_hash() -> str:
    embedded = _normalize_commit(os.environ.get(_COMMIT_ENV))
    if embedded != "unknown":
        return embedded

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return _normalize_commit(result.stdout)


def format_version(base_version: str, commit: str) -> str:
    normalized = _normalize_commit(commit)
    return base_version if normalized == "unknown" else f"{base_version}+g{normalized}"


def get_version_info() -> VersionInfo:
    commit = get_commit_hash()
    try:
        build_number = max(0, int(os.environ.get(_BUILD_NUMBER_ENV, "0")))
    except ValueError:
        build_number = 0
    return VersionInfo(
        base_version=BASE_VERSION,
        commit=commit,
        version=format_version(BASE_VERSION, commit),
        build_number=build_number,
    )


def get_version() -> str:
    return get_version_info().version
