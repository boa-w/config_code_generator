from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from ruamel.yaml.scalarint import HexInt

from config_codegen.gui.controller import DocumentController


class BasicConfigEditor(QWidget):
    def __init__(self, controller: DocumentController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._refreshing = False

        self.fragment_path = QLineEdit()
        self.response_can_id = QLineEdit()
        self.transmit_function = QLineEdit()
        self.command_reference = QLineEdit()
        self.index_reference = QLineEdit()
        self.subindex_reference = QLineEdit()
        self.data_reference = QLineEdit()

        for editor in (
            self.fragment_path,
            self.response_can_id,
            self.transmit_function,
            self.command_reference,
            self.index_reference,
            self.subindex_reference,
            self.data_reference,
        ):
            editor.setMinimumWidth(420)

        heading = QLabel("基础配置")
        heading_font = heading.font()
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 3)
        heading.setFont(heading_font)

        output_heading = QLabel("输出与响应")
        output_font = output_heading.font()
        output_font.setBold(True)
        output_heading.setFont(output_font)
        output_form = QFormLayout()
        output_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        output_form.addRow("输出片段", self.fragment_path)
        output_form.addRow("响应 CAN ID", self.response_can_id)
        output_form.addRow("发送函数", self.transmit_function)

        reference_heading = QLabel("C 代码引用")
        reference_heading.setFont(output_font)
        reference_form = QFormLayout()
        reference_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        reference_form.addRow("命令引用", self.command_reference)
        reference_form.addRow("Index 引用", self.index_reference)
        reference_form.addRow("SubIndex 引用", self.subindex_reference)
        reference_form.addRow("数据数组引用", self.data_reference)

        content = QWidget()
        content.setMaximumWidth(760)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(12)
        content_layout.addWidget(heading)
        content_layout.addSpacing(8)
        content_layout.addWidget(output_heading)
        content_layout.addLayout(output_form)
        content_layout.addSpacing(16)
        content_layout.addWidget(reference_heading)
        content_layout.addLayout(reference_form)
        content_layout.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content, 0, Qt.AlignTop | Qt.AlignLeft)

        self.fragment_path.editingFinished.connect(
            lambda: self._set(self._generator_output(), "fragment", self.fragment_path.text(), "编辑输出路径")
        )
        self.response_can_id.editingFinished.connect(self._set_can_id)
        self.transmit_function.editingFinished.connect(
            lambda: self._set(self._response(), "transmit_function", self.transmit_function.text(), "编辑发送函数")
        )
        self.command_reference.editingFinished.connect(
            lambda: self._set(self._references(), "command", self.command_reference.text(), "编辑命令引用")
        )
        self.index_reference.editingFinished.connect(
            lambda: self._set(self._references(), "index", self.index_reference.text(), "编辑 Index 引用")
        )
        self.subindex_reference.editingFinished.connect(
            lambda: self._set(self._references(), "subindex", self.subindex_reference.text(), "编辑 SubIndex 引用")
        )
        self.data_reference.editingFinished.connect(
            lambda: self._set(self._references(), "data", self.data_reference.text(), "编辑数据数组引用")
        )
        self.controller.changed.connect(self.refresh)
        self.refresh()

    def _generator_output(self) -> dict:
        return self.controller.document.data["generator"]["output"]

    def _protocol(self) -> dict:
        return self.controller.document.data["protocol"]

    def _response(self) -> dict:
        return self._protocol()["response"]

    def _references(self) -> dict:
        return self._protocol()["code_references"]

    def _set(self, mapping: dict, key: str, value: object, label: str) -> None:
        if not self._refreshing:
            self.controller.set_value(mapping, key, value, label)

    def _set_can_id(self) -> None:
        text = self.response_can_id.text().strip()
        try:
            value: object = HexInt(int(text, 0))
        except ValueError:
            value = text
        self._set(self._response(), "can_id", value, "编辑响应 CAN ID")

    def refresh(self) -> None:
        self._refreshing = True
        try:
            response = self._response()
            references = self._references()
            self.fragment_path.setText(str(self._generator_output().get("fragment", "")))
            can_id = response.get("can_id", "")
            self.response_can_id.setText(f"0x{int(can_id):X}" if isinstance(can_id, int) else str(can_id))
            self.transmit_function.setText(str(response.get("transmit_function", "")))
            self.command_reference.setText(str(references.get("command", "")))
            self.index_reference.setText(str(references.get("index", "")))
            self.subindex_reference.setText(str(references.get("subindex", "")))
            self.data_reference.setText(str(references.get("data", "")))
        finally:
            self._refreshing = False
