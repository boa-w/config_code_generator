from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from config_codegen.update.integrity import IntegrityError, safely_extract_zip, verify_file
from config_codegen.update.models import ManifestError, UpdateManifest
from config_codegen.version import VersionInfo


def _manifest(**overrides) -> dict:
    data = {
        "schema_version": 1,
        "channel": "nightly",
        "version": "0.1.0+g12345678",
        "commit": "1234567890abcdef1234567890abcdef12345678",
        "build_number": 42,
        "published_at": "2026-07-16T00:00:00Z",
        "archive_root": "config-code-generator",
        "minimum_updater_version": 1,
        "asset": {
            "name": "config-code-generator-nightly-windows-x64.zip",
            "url": "https://github.com/boa-w/config_code_generator/releases/download/nightly/config-code-generator-nightly-windows-x64.zip",
            "size": 100,
            "sha256": "a" * 64,
        },
    }
    data.update(overrides)
    return data


def test_manifest_parses_and_compares_builds() -> None:
    manifest = UpdateManifest.from_json(json.dumps(_manifest()))
    old = VersionInfo("0.1.0", "aaaaaaaa", "0.1.0+gaaaaaaaa", 41)
    same_commit = VersionInfo("0.1.0", "12345678", "0.1.0+g12345678", 1)
    newer_build = VersionInfo("0.1.0", "bbbbbbbb", "0.1.0+gbbbbbbbb", 43)

    assert manifest.is_newer_than(old)
    assert not manifest.is_newer_than(same_commit)
    assert not manifest.is_newer_than(newer_build)


def test_manifest_rejects_untrusted_asset_url() -> None:
    data = _manifest()
    data["asset"]["url"] = "https://example.com/update.zip"
    with pytest.raises(ManifestError, match="GitHub"):
        UpdateManifest.from_json(json.dumps(data))


def test_verify_and_extract_update_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "update.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("config-code-generator/config-code-generator.exe", b"main")
        archive.writestr("config-code-generator/config-code-generator-updater.exe", b"updater")
        archive.writestr("config-code-generator/data/file.txt", b"data")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()

    verify_file(archive_path, archive_path.stat().st_size, digest)
    root = safely_extract_zip(archive_path, tmp_path / "out", "config-code-generator")

    assert (root / "data" / "file.txt").read_bytes() == b"data"


def test_extract_rejects_path_traversal(tmp_path: Path) -> None:
    archive_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("config-code-generator/../outside.txt", b"bad")
    with pytest.raises(IntegrityError, match="不安全路径"):
        safely_extract_zip(archive_path, tmp_path / "out", "config-code-generator")
