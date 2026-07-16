from __future__ import annotations

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
RUNTIME_HOOK = BUILD_DIR / "version_runtime_hook.py"
WINDOWS_VERSION_FILE = BUILD_DIR / "windows_version_info.txt"


def _remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != ROOT:
        raise RuntimeError(f"refusing to remove path outside project root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def _load_version() -> tuple[str, str, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from config_codegen.version import BASE_VERSION, get_commit_hash, format_version

    commit = get_commit_hash()
    return BASE_VERSION, commit, format_version(BASE_VERSION, commit)


def _write_build_metadata(base_version: str, commit: str, version: str) -> None:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_HOOK.write_text(
        "import os\n"
        f"os.environ['CONFIG_CODE_GENERATOR_COMMIT'] = {commit!r}\n",
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


def main() -> int:
    _remove_tree(BUILD_DIR)
    _remove_tree(DIST_DIR)
    base_version, commit, version = _load_version()
    _write_build_metadata(base_version, commit, version)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_PATH.unlink(missing_ok=True)

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

    config_dir = BUNDLE_DIR / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "config" / "protocol.example.yaml", config_dir / "protocol.example.yaml")
    shutil.copy2(ROOT / "README.md", BUNDLE_DIR / "README.md")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(BUNDLE_DIR.rglob("*")):
            if path.is_file():
                archive.write(path, Path(BUNDLE_DIR.name) / path.relative_to(BUNDLE_DIR))

    print(f"bundle: {BUNDLE_DIR}")
    print(f"artifact: {ZIP_PATH}")
    print(f"version: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
