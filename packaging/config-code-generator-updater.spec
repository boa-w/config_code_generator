from pathlib import Path


root = Path(SPECPATH).parent
analysis = Analysis(
    [str(root / "packaging" / "updater_entry.py")],
    pathex=[str(root), str(root / "src")],
    binaries=[],
    datas=[],
    hiddenimports=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="config-code-generator-updater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
