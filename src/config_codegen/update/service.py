from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from PySide6.QtCore import QCoreApplication, QFile, QIODevice, QObject, QStandardPaths, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from config_codegen.update.integrity import safely_extract_zip, verify_file
from config_codegen.update.models import ManifestError, UpdateManifest
from config_codegen.version import VersionInfo, get_version_info


MANIFEST_URL = (
    "https://github.com/boa-w/config_code_generator/releases/download/nightly/"
    "update-manifest.json"
)


class UpdateService(QObject):
    state_changed = Signal(str)
    progress_changed = Signal(int, int)
    update_available = Signal(object)
    up_to_date = Signal(object)
    download_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.network = QNetworkAccessManager(self)
        self.current_version: VersionInfo = get_version_info()
        self.manifest: UpdateManifest | None = None
        self.extracted_root: Path | None = None
        self._reply: QNetworkReply | None = None
        self._download_file: QFile | None = None
        self._staging_dir: Path | None = None
        self.state = "idle"
        self.auto_check_enabled = False
        application = QCoreApplication.instance()
        if application is not None:
            application.aboutToQuit.connect(self.shutdown)

    def configure_auto_check(self, enabled: bool) -> None:
        """Reserved integration point; scheduling is intentionally not implemented."""
        self.auto_check_enabled = enabled

    def check_for_updates(self, manifest_url: str = MANIFEST_URL) -> None:
        if self.state in {"checking", "downloading", "installing"}:
            return
        self._cleanup_staging()
        self.manifest = None
        self._set_state("checking")
        request = self._request(manifest_url)
        self._reply = self.network.get(request)
        self._reply.finished.connect(self._manifest_finished)

    def download_update(self) -> None:
        if self.manifest is None or self.state not in {"available", "error"}:
            return
        self._cleanup_staging()
        cache_root = Path(QStandardPaths.writableLocation(QStandardPaths.CacheLocation))
        cache_root.mkdir(parents=True, exist_ok=True)
        self._staging_dir = Path(tempfile.mkdtemp(prefix="update-", dir=cache_root))
        package_path = self._staging_dir / self.manifest.asset.name
        self._download_file = QFile(str(package_path))
        if not self._download_file.open(QIODevice.WriteOnly):
            self._fail(f"无法创建更新包: {self._download_file.errorString()}")
            return
        self._set_state("downloading")
        self._reply = self.network.get(self._request(self.manifest.asset.url))
        self._reply.readyRead.connect(self._download_ready_read)
        self._reply.downloadProgress.connect(self.progress_changed)
        self._reply.finished.connect(self._download_finished)

    def install_update(self) -> None:
        if self.state != "ready" or self.extracted_root is None:
            return
        if not getattr(sys, "frozen", False):
            self._fail("开发环境不能执行自更新，请使用打包后的 EXE 验证安装")
            return
        target = Path(sys.executable).resolve().parent
        updater = self.extracted_root / "config-code-generator-updater.exe"
        try:
            runner_dir = Path(tempfile.gettempdir()) / "config-code-generator-updater"
            runner_dir.mkdir(parents=True, exist_ok=True)
            runner = runner_dir / updater.name
            shutil.copy2(updater, runner)
            command = [
                str(runner),
                "--source", str(self.extracted_root),
                "--target", str(target),
                "--pid", str(__import__("os").getpid()),
                "--staging", str(self._staging_dir),
            ]
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(command, close_fds=True, creationflags=creation_flags)
            self._set_state("installing")
        except OSError as exc:
            self._fail(f"无法启动更新器: {exc}")

    def cancel(self) -> None:
        if self._reply is not None and self._reply.isRunning():
            self._reply.abort()

    def shutdown(self) -> None:
        if self.state == "installing":
            return
        self.cancel()
        if self._download_file is not None:
            self._download_file.close()
            self._download_file = None
        self._cleanup_staging()

    def _manifest_finished(self) -> None:
        reply = self._take_reply()
        if reply is None:
            return
        try:
            self._ensure_success(reply)
            payload = bytes(reply.readAll())
            if len(payload) > 1024 * 1024:
                raise RuntimeError("更新清单大小超出允许范围")
            manifest = UpdateManifest.from_json(payload)
            self.manifest = manifest
            if manifest.is_newer_than(self.current_version):
                self._set_state("available")
                self.update_available.emit(manifest)
            else:
                self._set_state("up_to_date")
                self.up_to_date.emit(manifest)
        except (OSError, ManifestError, RuntimeError) as exc:
            self._fail(str(exc))
        finally:
            reply.deleteLater()

    def _download_ready_read(self) -> None:
        if self._reply is None or self._download_file is None:
            return
        data = self._reply.readAll()
        if self._download_file.pos() + data.size() > 512 * 1024 * 1024:
            self._reply.abort()
            return
        if self._download_file.write(data) != data.size():
            self._reply.abort()

    def _download_finished(self) -> None:
        reply = self._take_reply()
        download_file = self._download_file
        self._download_file = None
        if reply is None or download_file is None or self.manifest is None or self._staging_dir is None:
            return
        package_path = Path(download_file.fileName())
        download_file.close()
        try:
            self._ensure_success(reply)
            verify_file(package_path, self.manifest.asset.size, self.manifest.asset.sha256)
            extract_dir = self._staging_dir / "extracted"
            self.extracted_root = safely_extract_zip(
                package_path, extract_dir, self.manifest.archive_root
            )
            self._set_state("ready")
            self.download_ready.emit(self.extracted_root)
        except (OSError, ValueError, RuntimeError) as exc:
            self._cleanup_staging()
            self._fail(str(exc))
        finally:
            reply.deleteLater()

    @staticmethod
    def _request(url: str) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.UserAgentHeader, "ConfigCodeGenerator-Updater/1")
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.NoLessSafeRedirectPolicy,
        )
        return request

    @staticmethod
    def _ensure_success(reply: QNetworkReply) -> None:
        if reply.error() != QNetworkReply.NoError:
            raise RuntimeError(f"网络请求失败: {reply.errorString()}")
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
        if status is not None and not 200 <= int(status) < 300:
            raise RuntimeError(f"更新服务器返回 HTTP {status}")
        if reply.url().host().lower() not in {
            "github.com",
            "objects.githubusercontent.com",
            "release-assets.githubusercontent.com",
        }:
            raise RuntimeError("更新服务器重定向到了不受信任的地址")

    def _take_reply(self) -> QNetworkReply | None:
        reply = self._reply
        self._reply = None
        return reply

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)

    def _fail(self, message: str) -> None:
        self._set_state("error")
        self.failed.emit(message)

    def _cleanup_staging(self) -> None:
        self.extracted_root = None
        if self._staging_dir is not None:
            shutil.rmtree(self._staging_dir, ignore_errors=True)
            self._staging_dir = None
