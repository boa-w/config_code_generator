from __future__ import annotations

import platform
import sys

import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from config_codegen.version import VersionInfo, get_version_info


class AboutPage(QWidget):
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
        form.addRow("Python", self._selectable(platform.python_version()))
        form.addRow("PySide6", self._selectable(PySide6.__version__))

        copy_button = QPushButton("复制版本信息")
        copy_button.clicked.connect(self.copy_version_info)

        content = QWidget()
        content.setMaximumWidth(680)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(14)
        content_layout.addWidget(heading)
        content_layout.addLayout(form)
        content_layout.addSpacing(8)
        content_layout.addWidget(copy_button, 0, Qt.AlignLeft)
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
            f"Python: {platform.python_version()}\n"
            f"PySide6: {PySide6.__version__}\n"
            f"Platform: {sys.platform}"
        )
        QGuiApplication.clipboard().setText(text)
