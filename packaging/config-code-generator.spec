from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


root = Path(SPECPATH).parent
datas = collect_data_files("config_codegen")

analysis = Analysis(
    [str(root / "packaging" / "gui_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(root / "build" / "version_runtime_hook.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="config-code-generator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    version=str(root / "build" / "windows_version_info.txt"),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="config-code-generator",
)
