from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)
from ruamel.yaml.comments import CommentedMap

from config_codegen.gui.controller import DocumentController


class EntryEditor(QWidget):
    def __init__(self, controller: DocumentController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.entry: CommentedMap | None = None
        self._refreshing = False

        self.enabled = QCheckBox("生成此条目")
        self.protocol_ref = QLineEdit()
        self.name = QLineEdit()
        self.description = QLineEdit()
        self.status = QComboBox()
        self.status.setEditable(True)
        self.status.addItems(["planned", "implemented", "verified", "deprecated"])
        self.access = QComboBox()
        self.access.addItems(["read_only", "write_only", "read_write"])
        self.kind = QComboBox()
        self.kind.addItems(["scalar", "bitfield", "hook", "action", "transaction_fields", "chunked_buffer"])
        self.read_enabled = QCheckBox("读取代码")
        self.write_enabled = QCheckBox("写入代码")

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.addRow("启用", self.enabled)
        form.addRow("协议编号", self.protocol_ref)
        form.addRow("内部名称", self.name)
        form.addRow("显示名称", self.description)
        form.addRow("状态", self.status)
        form.addRow("访问权限", self.access)
        form.addRow("实现类型", self.kind)
        form.addRow("操作", self.read_enabled)
        form.addRow("", self.write_enabled)

        self.raw_yaml = QPlainTextEdit()
        self.raw_yaml.setReadOnly(True)
        self.raw_yaml.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.raw_yaml.setMinimumHeight(180)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addLayout(form)
        layout.addWidget(QLabel("条目 YAML"))
        layout.addWidget(self.raw_yaml, 1)

        self.enabled.clicked.connect(lambda value: self._set("enabled", value, "切换协议条目"))
        self.protocol_ref.editingFinished.connect(lambda: self._set("protocol_ref", self.protocol_ref.text(), "编辑协议编号"))
        self.name.editingFinished.connect(lambda: self._set("name", self.name.text(), "编辑内部名称"))
        self.description.editingFinished.connect(lambda: self._set("description", self.description.text(), "编辑显示名称"))
        self.status.currentTextChanged.connect(lambda value: self._set("status", value, "编辑状态"))
        self.access.currentTextChanged.connect(lambda value: self._set("access", value, "编辑访问权限"))
        self.kind.currentTextChanged.connect(lambda value: self._set("kind", value, "编辑实现类型"))
        self.read_enabled.clicked.connect(lambda value: self._set_operation("read", value))
        self.write_enabled.clicked.connect(lambda value: self._set_operation("write", value))
        self.controller.changed.connect(self.refresh)
        self.set_entry(None)

    def set_entry(self, entry: CommentedMap | None) -> None:
        self.entry = entry
        self.refresh()

    def _set(self, key: str, value: object, label: str) -> None:
        if self._refreshing or self.entry is None:
            return
        self.controller.set_value(self.entry, key, value, label)

    def _set_operation(self, operation: str, value: bool) -> None:
        if self._refreshing or self.entry is None:
            return
        node = self.entry.get(operation)
        if isinstance(node, dict):
            self.controller.set_value(node, "enabled", value, f"切换{operation}代码")

    def refresh(self) -> None:
        self._refreshing = True
        try:
            available = self.entry is not None
            for widget in (
                self.enabled,
                self.protocol_ref,
                self.name,
                self.description,
                self.status,
                self.access,
                self.kind,
            ):
                widget.setEnabled(available)
            if not available:
                self.protocol_ref.clear()
                self.name.clear()
                self.description.clear()
                self.raw_yaml.clear()
                self.read_enabled.setEnabled(False)
                self.write_enabled.setEnabled(False)
                return
            assert self.entry is not None
            self.enabled.setChecked(bool(self.entry.get("enabled", True)))
            self.protocol_ref.setText(str(self.entry.get("protocol_ref", "")))
            self.name.setText(str(self.entry.get("name", "")))
            self.description.setText(str(self.entry.get("description", "")))
            self.status.setCurrentText(str(self.entry.get("status", "")))
            self.access.setCurrentText(str(self.entry.get("access", "read_write")))
            self.kind.setCurrentText(str(self.entry.get("kind", "scalar")))
            read = self.entry.get("read")
            write = self.entry.get("write")
            self.read_enabled.setEnabled(isinstance(read, dict))
            self.read_enabled.setChecked(isinstance(read, dict) and bool(read.get("enabled", True)))
            self.write_enabled.setEnabled(isinstance(write, dict))
            self.write_enabled.setChecked(isinstance(write, dict) and bool(write.get("enabled", True)))
            self.raw_yaml.setPlainText(self.controller.document.dump_node(self.entry))
        finally:
            self._refreshing = False
