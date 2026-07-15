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


def _remove_tree(path: Path) -> None:
    resolved = path.resolve()
    if resolved.parent != ROOT:
        raise RuntimeError(f"refusing to remove path outside project root: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


def main() -> int:
    _remove_tree(BUILD_DIR)
    _remove_tree(DIST_DIR)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
