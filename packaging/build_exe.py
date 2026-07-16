from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
ARTIFACT_DIR = ROOT / "artifacts"
BUNDLE_DIR = DIST_DIR / "config-code-generator"
ZIP_PATH = ARTIFACT_DIR / "config-code-generator-nightly-windows-x64.zip"
MANIFEST_PATH = ARTIFACT_DIR / "update-manifest.json"
RUNTIME_HOOK = BUILD_DIR / "version_runtime_hook.py"
WINDOWS_VERSION_FILE = BUILD_DIR / "windows_version_info.txt"


def _remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != ROOT:
        raise RuntimeError(f"refusing to remove path outside project root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _load_version() -> tuple[str, str, str, str, int]:
    sys.path.insert(0, str(ROOT / "src"))
    from config_codegen.version import BASE_VERSION, get_commit_hash, format_version

    short_commit = get_commit_hash()
    full_commit = os.environ.get("GITHUB_SHA", "").strip().lower()
    if len(full_commit) != 40:
        full_commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip().lower()
    build_number = int(os.environ.get("GITHUB_RUN_NUMBER", "1"))
    return BASE_VERSION, short_commit, full_commit, format_version(BASE_VERSION, short_commit), build_number


def _write_build_metadata(base_version: str, commit: str, version: str, build_number: int) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_HOOK.write_text(
        "import os\n"
        f"os.environ['CONFIG_CODE_GENERATOR_COMMIT'] = {commit!r}\n"
        f"os.environ['CONFIG_CODE_GENERATOR_BUILD_NUMBER'] = {str(build_number)!r}\n",
        encoding="utf-8",
        newline="\n",
    )
    parts = [int(part) for part in base_version.split(".")]
    if len(parts) != 3:
        raise RuntimeError("BASE_VERSION must use major.minor.patch format")
    major, minor, patch = parts
    WINDOWS_VERSION_FILE.write_text(
        f"""VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('FileDescription', 'Config Code Generator'),
        StringStruct('FileVersion', '{version}'),
        StringStruct('InternalName', 'config-code-generator'),
        StringStruct('OriginalFilename', 'config-code-generator.exe'),
        StringStruct('ProductName', 'Config Code Generator'),
        StringStruct('ProductVersion', '{version}')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""",
        encoding="utf-8",
        newline="\n",
    )


def _write_update_manifest(version: str, commit: str, build_number: int) -> None:
    digest = hashlib.sha256(ZIP_PATH.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "channel": "nightly",
        "version": version,
        "commit": commit,
        "build_number": build_number,
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "archive_root": BUNDLE_DIR.name,
        "minimum_updater_version": 1,
        "asset": {
            "name": ZIP_PATH.name,
            "url": f"https://github.com/boa-w/config_code_generator/releases/download/nightly/{ZIP_PATH.name}",
            "size": ZIP_PATH.stat().st_size,
            "sha256": digest,
        },
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    _remove_tree(BUILD_DIR)
    _remove_tree(DIST_DIR)
    base_version, commit, full_commit, version, build_number = _load_version()
    _write_build_metadata(base_version, commit, version, build_number)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.unlink(missing_ok=True)
    MANIFEST_PATH.unlink(missing_ok=True)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "packaging" / "config-code-generator.spec"),
        ],
        cwd=ROOT,
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(ROOT / "packaging" / "config-code-generator-updater.spec"),
        ],
        cwd=ROOT,
        check=True,
    )
    shutil.copy2(DIST_DIR / "config-code-generator-updater.exe", BUNDLE_DIR)

    config_dir = BUNDLE_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "protocol.example.yaml", config_dir / "protocol.example.yaml")
    shutil.copy2(ROOT / "README.md", BUNDLE_DIR / "README.md")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUNDLE_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path(BUNDLE_DIR.name) / path.relative_to(BUNDLE_DIR))
    _write_update_manifest(version, full_commit, build_number)

    print(f"bundle: {BUNDLE_DIR}")
    print(f"artifact: {ZIP_PATH}")
    print(f"manifest: {MANIFEST_PATH}")
    print(f"version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
