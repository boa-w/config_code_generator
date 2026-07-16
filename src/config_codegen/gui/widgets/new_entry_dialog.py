from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from config_codegen.gui.entry_capabilities import TEMPLATE_OPTIONS


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class NewEntryDialog(QDialog):
    def __init__(
        self,
        subindex: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新增协议条目")
        self.setMinimumWidth(420)
        self.template = QComboBox()
        for code, label in TEMPLATE_OPTIONS:
            self.template.addItem(label, code)
        self.subindex = QLineEdit(str(subindex))
        self.name = QLineEdit(f"new_entry_{subindex:02x}")
        self.description = QLineEdit("新协议条目")
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #A32727;")
        self.error_label.setWordWrap(True)
        form = QFormLayout()
        form.addRow("条目模板", self.template)
        form.addRow("SubIndex", self.subindex)
        form.addRow("内部名称", self.name)
        form.addRow("显示名称", self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addWidget(buttons)

    def _accept_if_valid(self) -> None:
        try:
            subindex = int(self.subindex.text().strip(), 0)
        except ValueError:
            self.error_label.setText("SubIndex 必须是 0~255 的整数。")
            return
        if not 0 <= subindex <= 0xFF:
            self.error_label.setText("SubIndex 必须是 0~255 的整数。")
            return
        if not _IDENTIFIER.fullmatch(self.name.text().strip()):
            self.error_label.setText("内部名称必须是有效的 C 标识符。")
            return
        if not self.description.text().strip():
            self.error_label.setText("显示名称不能为空。")
            return
        self.accept()

    def values(self) -> tuple[str, int, str, str]:
        return (
            str(self.template.currentData()),
            int(self.subindex.text().strip(), 0),
            self.name.text().strip(),
            self.description.text().strip(),
        )
