from __future__ import annotations

import platform
import sys

import PySide6
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config_codegen.update.models import UpdateManifest
from config_codegen.update.service import UpdateService
from config_codegen.version import VersionInfo, get_version_info


class AboutPage(QWidget):
    install_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.version_info: VersionInfo = get_version_info()

        heading = QLabel("Config Code Generator")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 5)
        heading.setFont(heading_font)

        version = QLabel(self.version_info.version)
        version.setObjectName("aboutVersion")
        version.setTextInteractionFlags(Qt.TextSelectableByMouse)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("版本号", version)
        form.addRow("手动版本", self._selectable(self.version_info.base_version))
        form.addRow("Commit", self._selectable(self.version_info.commit))
        form.addRow(
            "构建号",
            self._selectable(str(self.version_info.build_number) if self.version_info.build_number else "本地构建"),
        )
        form.addRow("Python", self._selectable(platform.python_version()))
        form.addRow("PySide6", self._selectable(PySide6.__version__))

        copy_button = QPushButton("复制版本信息")
        copy_button.clicked.connect(self.copy_version_info)

        self.update_service = UpdateService(self)
        self.update_status = QLabel("尚未检查更新")
        self.update_status.setObjectName("updateStatus")
        self.update_status.setWordWrap(True)
        self.remote_version = QLabel("-")
        self.remote_version.setTextInteractionFlags(Qt.TextSelectableByMouse)
        update_form = QFormLayout()
        update_form.addRow("更新通道", QLabel("Nightly"))
        update_form.addRow("远端版本", self.remote_version)
        update_form.addRow("状态", self.update_status)

        self.update_progress = QProgressBar()
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(0)
        self.update_progress.hide()
        self.check_button = QPushButton("检查更新")
        self.download_button = QPushButton("下载更新")
        self.install_button = QPushButton("安装并重启")
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)
        update_buttons = QHBoxLayout()
        update_buttons.addWidget(self.check_button)
        update_buttons.addWidget(self.download_button)
        update_buttons.addWidget(self.install_button)
        update_buttons.addStretch(1)

        update_group = QGroupBox("软件更新")
        update_layout = QVBoxLayout(update_group)
        update_layout.addLayout(update_form)
        update_layout.addWidget(self.update_progress)
        update_layout.addLayout(update_buttons)

        self.check_button.clicked.connect(self.update_service.check_for_updates)
        self.download_button.clicked.connect(self.update_service.download_update)
        self.install_button.clicked.connect(self.install_requested)
        self.update_service.state_changed.connect(self._update_state)
        self.update_service.update_available.connect(self._update_available)
        self.update_service.up_to_date.connect(self._up_to_date)
        self.update_service.download_ready.connect(self._download_ready)
        self.update_service.progress_changed.connect(self._download_progress)
        self.update_service.failed.connect(self._update_failed)

        content = QWidget()
        content.setMinimumWidth(620)
        content.setMaximumWidth(680)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(14)
        content_layout.addWidget(heading)
        content_layout.addLayout(form)
        content_layout.addSpacing(8)
        content_layout.addWidget(copy_button, 0, Qt.AlignLeft)
        content_layout.addSpacing(10)
        content_layout.addWidget(update_group)
        content_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content, 0, Qt.AlignTop | Qt.AlignLeft)

    @staticmethod
    def _selectable(text: str) -> QLabel:
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return label

    def copy_version_info(self) -> None:
        text = (
            f"Config Code Generator {self.version_info.version}\n"
            f"Commit: {self.version_info.commit}\n"
            f"Build: {self.version_info.build_number or 'local'}\n"
            f"Python: {platform.python_version()}\n"
            f"PySide6: {PySide6.__version__}\n"
            f"Platform: {sys.platform}"
        )
        QGuiApplication.clipboard().setText(text)

    def _update_state(self, state: str) -> None:
        busy = state in {"checking", "downloading", "installing"}
        self.check_button.setEnabled(not busy)
        if state == "checking":
            self.update_status.setText("正在检查更新...")
        elif state == "downloading":
            self.update_status.setText("正在下载并校验更新包...")
            self.update_progress.show()
        elif state == "installing":
            self.update_status.setText("正在启动更新器...")

    def _update_available(self, manifest: UpdateManifest) -> None:
        self.remote_version.setText(f"{manifest.version}（构建 {manifest.build_number}）")
        self.update_status.setText("发现新版本，可下载安装")
        self.download_button.setEnabled(True)
        self.install_button.setEnabled(False)

    def _up_to_date(self, manifest: UpdateManifest) -> None:
        self.remote_version.setText(f"{manifest.version}（构建 {manifest.build_number}）")
        self.update_status.setText("当前已是最新版本")
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(False)

    def _download_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.update_progress.setRange(0, 100)
            self.update_progress.setValue(min(100, int(received * 100 / total)))
        else:
            self.update_progress.setRange(0, 0)

    def _download_ready(self, _path: object) -> None:
        self.update_progress.setRange(0, 100)
        self.update_progress.setValue(100)
        self.update_status.setText("更新包已下载并通过完整性校验")
        self.download_button.setEnabled(False)
        self.install_button.setEnabled(True)

    def _update_failed(self, message: str) -> None:
        self.update_status.setText(f"更新失败：{message}")
        self.check_button.setEnabled(True)
        self.download_button.setEnabled(self.update_service.manifest is not None)
        self.install_button.setEnabled(False)
