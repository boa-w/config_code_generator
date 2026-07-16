from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
import stat
import zipfile


MAX_EXTRACTED_SIZE = 1024 * 1024 * 1024
MAX_ARCHIVE_FILES = 20_000


class IntegrityError(ValueError):
    pass


def verify_file(path: Path, expected_size: int, expected_sha256: str) -> None:
    if path.stat().st_size != expected_size:
        raise IntegrityError("下载文件大小与更新清单不一致")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest().lower() != expected_sha256.lower():
        raise IntegrityError("下载文件 SHA-256 校验失败")


def safely_extract_zip(archive_path: Path, destination: Path, archive_root: str) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ARCHIVE_FILES:
            raise IntegrityError("更新包文件数量超出允许范围")
        if sum(member.file_size for member in members) > MAX_EXTRACTED_SIZE:
            raise IntegrityError("更新包解压后大小超出允许范围")
        for member in members:
            relative = _safe_member_path(member, archive_root)
            target = (destination / Path(*relative.parts)).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                raise IntegrityError(f"更新包包含越界路径: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
    extracted_root = destination / archive_root
    if not (extracted_root / "config-code-generator.exe").is_file():
        raise IntegrityError("更新包缺少主程序")
    if not (extracted_root / "config-code-generator-updater.exe").is_file():
        raise IntegrityError("更新包缺少更新器")
    return extracted_root


def _safe_member_path(member: zipfile.ZipInfo, archive_root: str) -> PurePosixPath:
    raw = member.filename.replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or path.parts[0] != archive_root:
        raise IntegrityError(f"更新包根目录无效: {member.filename}")
    if any(part in ("", ".", "..") or ":" in part for part in path.parts):
        raise IntegrityError(f"更新包包含不安全路径: {member.filename}")
    unix_mode = member.external_attr >> 16
    if unix_mode and stat.S_ISLNK(unix_mode):
        raise IntegrityError(f"更新包不允许符号链接: {member.filename}")
    return path
