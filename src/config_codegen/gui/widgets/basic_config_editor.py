from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarint import HexInt

from config_codegen.gui.controller import DocumentController
from config_codegen.gui.widgets.hook_registry_editor import HookRegistryEditor


class BasicConfigEditor(QWidget):
    def __init__(self, controller: DocumentController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._refreshing = False

        self.project_name = QLineEdit()
        self.project_description = QLineEdit()
        self.source_file = QLineEdit()
        self.source_handler = QLineEdit()
        self.generated_notice = QLineEdit()
        self.fragment_path = QLineEdit()
        self.response_can_id = QLineEdit()
        self.transmit_function = QLineEdit()
        self.command_reference = QLineEdit()
        self.index_reference = QLineEdit()
        self.subindex_reference = QLineEdit()
        self.data_reference = QLineEdit()
        self.error_command = QLineEdit()
        self.value_error_code = QLineEdit()
        self.key_error_code = QLineEdit()
        self.commands_yaml = QPlainTextEdit()
        self.commands_yaml.setMinimumHeight(180)
        self.apply_commands = QPushButton("应用命令配置")
        self.hook_registry = HookRegistryEditor(controller)

        for editor in (
            self.project_name,
            self.project_description,
            self.source_file,
            self.source_handler,
            self.generated_notice,
            self.fragment_path,
            self.response_can_id,
            self.transmit_function,
            self.command_reference,
            self.index_reference,
            self.subindex_reference,
            self.data_reference,
        ):
            editor.setMinimumWidth(420)

        project_content = QWidget()
        project_layout = self._page_layout(project_content, "项目设置")
        project_layout.addWidget(self._section("项目与业务代码来源"))
        project_layout.addLayout(self._form(
            ("项目名称", self.project_name),
            ("项目说明", self.project_description),
            ("业务源码文件", self.source_file),
            ("协议处理函数", self.source_handler),
            ("生成文件声明", self.generated_notice),
        ))
        project_layout.addWidget(self._section("输出、响应与 C 引用"))
        project_layout.addLayout(self._form(
            ("输出片段", self.fragment_path),
            ("响应 CAN ID", self.response_can_id),
            ("发送函数", self.transmit_function),
            ("命令引用", self.command_reference),
            ("Index 引用", self.index_reference),
            ("SubIndex 引用", self.subindex_reference),
            ("数据数组引用", self.data_reference),
        ))
        project_layout.addStretch(1)

        errors_content = QWidget()
        errors_layout = self._page_layout(errors_content, "错误响应")
        errors_layout.addLayout(self._form(
            ("错误响应命令", self.error_command),
            ("数值越界错误码", self.value_error_code),
            ("授权失败错误码", self.key_error_code),
        ))
        errors_layout.addStretch(1)

        commands_content = QWidget()
        commands_layout = self._page_layout(commands_content, "命令定义")
        command_note = QLabel("命令名会出现在条目的写命令选择器中。修改后立即参与校验。")
        command_note.setWordWrap(True)
        commands_layout.addWidget(command_note)
        commands_layout.addWidget(self.commands_yaml)
        commands_layout.addWidget(self.apply_commands, 0, Qt.AlignRight)
        commands_layout.addStretch(1)

        hooks_content = QWidget()
        hooks_layout = self._page_layout(hooks_content, "Hook 管理")
        hooks_layout.addWidget(self.hook_registry)
        hooks_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.pages = {
            "project": self._scroll_page(project_content),
            "commands": self._scroll_page(commands_content),
            "errors": self._scroll_page(errors_content),
            "hooks": self._scroll_page(hooks_content),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

        self._connect_signals()
        self.controller.changed.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    @staticmethod
    def _page_layout(content: QWidget, title: str) -> QVBoxLayout:
        content.setMinimumWidth(680)
        content.setMaximumWidth(820)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        heading = QLabel(title)
        font = heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 3)
        heading.setFont(font)
        layout.addWidget(heading)
        return layout

    @staticmethod
    def _scroll_page(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        return scroll

    def show_section(self, section: str) -> None:
        page = self.pages.get(section)
        if page is not None:
            self.stack.setCurrentWidget(page)

    @staticmethod
    def _form(*rows: tuple[str, QWidget]) -> QFormLayout:
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for label, widget in rows:
            form.addRow(label, widget)
        return form

    def _connect_signals(self) -> None:
        for widget, mapping_getter, key, label in (
            (self.project_name, self._project, "name", "编辑项目名称"),
            (self.project_description, self._project, "description", "编辑项目说明"),
            (self.source_file, self._project, "source_file", "编辑业务源码文件"),
            (self.source_handler, self._project, "source_handler", "编辑协议处理函数"),
            (self.generated_notice, self._project, "generated_notice", "编辑生成文件声明"),
            (self.fragment_path, self._generator_output, "fragment", "编辑输出路径"),
            (self.transmit_function, self._response, "transmit_function", "编辑发送函数"),
            (self.command_reference, self._references, "command", "编辑命令引用"),
            (self.index_reference, self._references, "index", "编辑 Index 引用"),
            (self.subindex_reference, self._references, "subindex", "编辑 SubIndex 引用"),
            (self.data_reference, self._references, "data", "编辑数据数组引用"),
        ):
            widget.editingFinished.connect(
                lambda w=widget, getter=mapping_getter, k=key, l=label: self._set(getter(), k, w.text(), l)
            )
        self.response_can_id.editingFinished.connect(
            lambda: self._set_number(self._response(), "can_id", self.response_can_id.text(), "编辑响应 CAN ID")
        )
        self.error_command.editingFinished.connect(
            lambda: self._set_number(self._errors(), "response_command", self.error_command.text(), "编辑错误响应命令")
        )
        self.value_error_code.editingFinished.connect(
            lambda: self._set_number(self._error_codes(), "value_out_of_range", self.value_error_code.text(), "编辑越界错误码")
        )
        self.key_error_code.editingFinished.connect(
            lambda: self._set_number(self._error_codes(), "invalid_key", self.key_error_code.text(), "编辑授权错误码")
        )
        self.apply_commands.clicked.connect(
            lambda: self._apply_mapping(self.commands_yaml, self._commands(), "编辑命令定义")
        )

    def _project(self) -> dict[str, Any]:
        return self.controller.document.data["project"]

    def _generator_output(self) -> dict[str, Any]:
        return self.controller.document.data["generator"]["output"]

    def _protocol(self) -> dict[str, Any]:
        return self.controller.document.data["protocol"]

    def _response(self) -> dict[str, Any]:
        return self._protocol()["response"]

    def _references(self) -> dict[str, Any]:
        return self._protocol()["code_references"]

    def _commands(self) -> dict[str, Any]:
        return self._protocol()["commands"]

    def _errors(self) -> dict[str, Any]:
        return self._protocol()["errors"]

    def _error_codes(self) -> dict[str, Any]:
        return self._errors()["codes"]

    def _set(self, mapping: dict[str, Any], key: str, value: object, label: str) -> None:
        if not self._refreshing:
            self.controller.set_value(mapping, key, value, label)

    def _set_number(self, mapping: dict[str, Any], key: str, text: str, label: str) -> None:
        value: object
        try:
            value = HexInt(int(text.strip(), 0))
        except ValueError:
            value = text.strip()
        self._set(mapping, key, value, label)

    def _apply_mapping(self, editor: QPlainTextEdit, target: dict[str, Any], label: str) -> None:
        yaml = YAML(typ="rt")
        try:
            value = yaml.load(editor.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "YAML 格式错误", str(exc))
            return
        if not isinstance(value, CommentedMap):
            QMessageBox.critical(self, "YAML 格式错误", "配置必须是一个 YAML 映射。")
            return
        self.controller.replace_mapping(target, value, label)

    @staticmethod
    def _number(value: object) -> str:
        return f"0x{int(value):X}" if isinstance(value, int) else str(value or "")

    def refresh(self) -> None:
        self._refreshing = True
        try:
            project = self._project()
            response = self._response()
            references = self._references()
            errors = self._errors()
            codes = self._error_codes()
            self.project_name.setText(str(project.get("name", "")))
            self.project_description.setText(str(project.get("description", "")))
            self.source_file.setText(str(project.get("source_file", "")))
            self.source_handler.setText(str(project.get("source_handler", "")))
            self.generated_notice.setText(str(project.get("generated_notice", "")))
            self.fragment_path.setText(str(self._generator_output().get("fragment", "")))
            self.response_can_id.setText(self._number(response.get("can_id")))
            self.transmit_function.setText(str(response.get("transmit_function", "")))
            self.command_reference.setText(str(references.get("command", "")))
            self.index_reference.setText(str(references.get("index", "")))
            self.subindex_reference.setText(str(references.get("subindex", "")))
            self.data_reference.setText(str(references.get("data", "")))
            self.error_command.setText(self._number(errors.get("response_command")))
            self.value_error_code.setText(self._number(codes.get("value_out_of_range")))
            self.key_error_code.setText(self._number(codes.get("invalid_key")))
            self.commands_yaml.setPlainText(self.controller.document.dump_node(self._commands()))
        finally:
            self._refreshing = False
