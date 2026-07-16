from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from config_codegen.version import VersionInfo


_SHA256_PATTERN = re.compile(r"^[0-9a-fA-F]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{40}$")
_HTTPS_PATTERN = re.compile(r"^https://(?:github\.com|objects\.githubusercontent\.com)/")


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class UpdateAsset:
    name: str
    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class UpdateManifest:
    schema_version: int
    channel: str
    version: str
    commit: str
    build_number: int
    published_at: str
    archive_root: str
    minimum_updater_version: int
    asset: UpdateAsset

    @classmethod
    def from_json(cls, payload: bytes | str) -> "UpdateManifest":
        try:
            data = json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ManifestError(f"更新清单不是有效的 JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ManifestError("更新清单根节点必须是对象")
        try:
            asset_data = data["asset"]
            if not isinstance(asset_data, dict):
                raise TypeError("asset")
            manifest = cls(
                schema_version=_integer(data, "schema_version"),
                channel=_string(data, "channel"),
                version=_string(data, "version"),
                commit=_string(data, "commit").lower(),
                build_number=_integer(data, "build_number"),
                published_at=_string(data, "published_at"),
                archive_root=_string(data, "archive_root"),
                minimum_updater_version=_integer(data, "minimum_updater_version"),
                asset=UpdateAsset(
                    name=_string(asset_data, "name"),
                    url=_string(asset_data, "url"),
                    size=_integer(asset_data, "size"),
                    sha256=_string(asset_data, "sha256").lower(),
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ManifestError(f"更新清单字段无效: {exc}") from exc
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if self.schema_version != 1:
            raise ManifestError(f"不支持的更新清单版本: {self.schema_version}")
        if self.channel != "nightly":
            raise ManifestError(f"不支持的更新通道: {self.channel}")
        if not _COMMIT_PATTERN.fullmatch(self.commit):
            raise ManifestError("commit 必须是 40 位十六进制值")
        if self.build_number < 1:
            raise ManifestError("build_number 必须大于 0")
        if self.minimum_updater_version > 1:
            raise ManifestError("当前更新器版本过低，请手动下载安装")
        if self.archive_root != "config-code-generator":
            raise ManifestError("更新包根目录无效")
        if self.asset.name != "config-code-generator-nightly-windows-x64.zip":
            raise ManifestError("更新包文件名无效")
        if self.asset.size < 1 or self.asset.size > 512 * 1024 * 1024:
            raise ManifestError("更新包大小超出允许范围")
        if not _SHA256_PATTERN.fullmatch(self.asset.sha256):
            raise ManifestError("更新包 SHA-256 无效")
        if not _HTTPS_PATTERN.match(self.asset.url):
            raise ManifestError("更新包必须来自受信任的 GitHub HTTPS 地址")

    def is_newer_than(self, current: VersionInfo) -> bool:
        if current.commit != "unknown" and self.commit.startswith(current.commit):
            return False
        if current.build_number > 0:
            return self.build_number > current.build_number
        return True


def _string(data: dict[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise TypeError(key)
    return value.strip()


def _integer(data: dict[str, Any], key: str) -> int:
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(key)
    return value
