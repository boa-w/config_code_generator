from __future__ import annotations

import ctypes
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


EXE_NAME = "config-code-generator.exe"
PRESERVED_NAMES = {"config"}


def wait_for_process(pid: int, timeout_seconds: int = 60) -> bool:
    if sys.platform != "win32":
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                __import__("os").kill(pid, 0)
            except OSError:
                return True
            time.sleep(0.25)
        return False
    synchronize = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
    if not handle:
        return True
    try:
        return ctypes.windll.kernel32.WaitForSingleObject(handle, timeout_seconds * 1000) == 0
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def _children_except_preserved(directory: Path) -> list[Path]:
    return [child for child in directory.iterdir() if child.name.lower() not in PRESERVED_NAMES]


def replace_installation(source: Path, target: Path, backup: Path) -> None:
    backup.mkdir(parents=True)
    for child in _children_except_preserved(target):
        shutil.move(str(child), backup / child.name)
    try:
        for child in _children_except_preserved(source):
            destination = target / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)
    except Exception:
        restore_installation(target, backup)
        raise


def restore_installation(target: Path, backup: Path) -> None:
    for child in _children_except_preserved(target):
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    if backup.exists():
        for child in list(backup.iterdir()):
            shutil.move(str(child), target / child.name)


def launch_and_check(
    target: Path, marker: Path, timeout_seconds: int = 30
) -> tuple[bool, subprocess.Popen]:
    process = subprocess.Popen(
        [str(target / EXE_NAME), "--update-health-file", str(marker)],
        cwd=target,
        close_fds=True,
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if marker.is_file():
            return True, process
        if process.poll() is not None:
            return False, process
        time.sleep(0.25)
    return False, process


def run_update(source: Path, target: Path, pid: int, staging: Path) -> int:
    source = source.resolve()
    target = target.resolve()
    staging = staging.resolve()
    log_path = Path(tempfile.gettempdir()) / "config-code-generator-update.log"
    backup: Path | None = None
    replacement_active = False
    old_version_started = False
    try:
        if source == target or staging not in source.parents:
            raise RuntimeError("更新目录关系无效")
        if not (source / EXE_NAME).is_file() or not (target / EXE_NAME).is_file():
            raise RuntimeError("主程序文件不存在")
        if not wait_for_process(pid):
            raise RuntimeError("等待主程序退出超时")
        backup = target.parent / f".{target.name}-backup-{pid}"
        if backup.exists():
            shutil.rmtree(backup)
        replace_installation(source, target, backup)
        replacement_active = True
        marker = staging / "update-health.ok"
        marker.unlink(missing_ok=True)
        healthy, process = launch_and_check(target, marker)
        if not healthy:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(5)
                except subprocess.TimeoutExpired:
                    process.kill()
            restore_installation(target, backup)
            replacement_active = False
            shutil.rmtree(backup, ignore_errors=True)
            subprocess.Popen([str(target / EXE_NAME)], cwd=target, close_fds=True)
            old_version_started = True
            raise RuntimeError("新版启动检查失败，已恢复旧版本")
        shutil.rmtree(backup, ignore_errors=True)
        shutil.rmtree(staging, ignore_errors=True)
        log_path.write_text("update completed\n", encoding="utf-8")
        return 0
    except Exception as exc:
        if replacement_active and backup is not None and backup.exists():
            try:
                restore_installation(target, backup)
                shutil.rmtree(backup, ignore_errors=True)
                if not old_version_started:
                    subprocess.Popen([str(target / EXE_NAME)], cwd=target, close_fds=True)
            except Exception as rollback_exc:
                exc = RuntimeError(f"{exc}; 回滚失败: {rollback_exc}")
        log_path.write_text(f"update failed: {exc}\n", encoding="utf-8")
        return 1
