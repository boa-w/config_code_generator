from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ruamel.yaml.comments import CommentedMap

from config_codegen.gui.controller import DocumentController
from config_codegen.gui.i18n import HOOK_CONTRACT_DESCRIPTIONS, HOOK_CONTRACT_OPTIONS


_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _CommitTextEdit(QPlainTextEdit):
    editingFinished = Signal()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class HookRegistryEditor(QWidget):
    def __init__(self, controller: DocumentController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._refreshing = False
        self._selected_alias = ""

        self.hook_list = QListWidget()
        self.hook_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.hook_list.setMinimumWidth(220)
        self.hook_list.setMinimumHeight(230)
        self.add_button = self._tool_button(QStyle.SP_FileIcon, "新增 Hook")
        self.rename_button = QPushButton("重命名")
        self.delete_button = self._tool_button(QStyle.SP_TrashIcon, "删除 Hook")

        tools = QHBoxLayout()
        tools.addWidget(self.add_button)
        tools.addWidget(self.rename_button)
        tools.addWidget(self.delete_button)
        tools.addStretch(1)

        self.alias_label = QLabel("-")
        self.function = QLineEdit()
        self.contract = QComboBox()
        for code, label in HOOK_CONTRACT_OPTIONS:
            self.contract.addItem(label, code)
        self.signature = QLabel()
        self.signature.setObjectName("kindDescription")
        self.signature.setWordWrap(True)
        self.description = _CommitTextEdit()
        self.description.setMaximumHeight(90)
        self.generate_enabled = QCheckBox("生成 Hook 函数")
        self.generate_mode = QComboBox()
        self.generate_mode.addItem("包装调用业务函数", "wrapper")
        self.generate_mode.addItem("自定义 C 函数体", "body")
        self.call_function = QLineEdit()
        self.call_function.setPlaceholderText("实际业务函数名称")
        self.arguments = QComboBox()
        self.return_policy = QComboBox()
        self.return_policy.addItem("转发调用结果", "forward")
        self.return_policy.addItem("调用后固定返回成功", "always_success")
        self.body = _CommitTextEdit()
        self.body.setPlaceholderText("填写函数大括号内的 C 代码")
        self.body.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.body.setMinimumHeight(220)
        detail_form = QFormLayout()
        detail_form.addRow("配置别名", self.alias_label)
        detail_form.addRow("C 函数", self.function)
        detail_form.addRow("调用契约", self.contract)
        detail_form.addRow("函数签名", self.signature)
        detail_form.addRow("用途说明", self.description)
        detail_form.addRow("代码生成", self.generate_enabled)
        detail_form.addRow("生成方式", self.generate_mode)
        detail_form.addRow("实际调用函数", self.call_function)
        detail_form.addRow("参数传递", self.arguments)
        detail_form.addRow("返回策略", self.return_policy)
        detail_form.addRow("C 函数体", self.body)
        self.detail_form = detail_form

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.hook_list)
        left_layout.addLayout(tools)
        detail = QWidget()
        detail.setLayout(detail_form)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(left, 2)
        layout.addWidget(detail, 3)

        self.hook_list.currentTextChanged.connect(self._select_alias)
        self.add_button.clicked.connect(self._prompt_add)
        self.rename_button.clicked.connect(self._prompt_rename)
        self.delete_button.clicked.connect(self._prompt_delete)
        self.function.editingFinished.connect(self._save_definition)
        self.contract.currentIndexChanged.connect(self._contract_changed)
        self.description.editingFinished.connect(self._save_definition)
        self.generate_enabled.clicked.connect(self._save_definition)
        self.generate_mode.currentIndexChanged.connect(self._generation_mode_changed)
        self.call_function.editingFinished.connect(self._save_definition)
        self.arguments.currentIndexChanged.connect(self._save_definition)
        self.return_policy.currentIndexChanged.connect(self._save_definition)
        self.body.editingFinished.connect(self._save_definition)
        self.controller.changed.connect(self.refresh)
        self.refresh()

    def _tool_button(self, icon: QStyle.StandardPixmap, tooltip: str) -> QToolButton:
        button = QToolButton()
        if tooltip == "新增 Hook":
            button.setText("+")
        else:
            button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        return button

    def _hooks(self) -> dict[str, Any]:
        hooks = self.controller.document.data.get("hooks")
        if not isinstance(hooks, dict):
            hooks = CommentedMap()
            self.controller.document.data["hooks"] = hooks
        return hooks

    @staticmethod
    def _parts(definition: Any) -> tuple[str, str, str, dict[str, Any]]:
        if isinstance(definition, dict):
            return (
                str(definition.get("function", "")),
                str(definition.get("contract", "")),
                str(definition.get("description", "")),
                definition.get("generate", {})
                if isinstance(definition.get("generate"), dict)
                else {},
            )
        return "", "", "", {}

    def create_hook(self, alias: str) -> bool:
        alias = alias.strip()
        if not _IDENTIFIER.fullmatch(alias) or alias in self._hooks():
            return False
        definition = CommentedMap(
            {
                "function": alias,
                "contract": "write",
                "description": "",
            }
        )
        self.controller.set_value(self._hooks(), alias, definition, "新增 Hook")
        self._selected_alias = alias
        self.refresh()
        return True

    def rename_hook(self, old_alias: str, new_alias: str) -> bool:
        new_alias = new_alias.strip()
        hooks = self._hooks()
        if old_alias not in hooks or not _IDENTIFIER.fullmatch(new_alias):
            return False
        if new_alias != old_alias and new_alias in hooks:
            return False
        if new_alias == old_alias:
            return True
        replacement = CommentedMap()
        for alias, definition in hooks.items():
            replacement[new_alias if alias == old_alias else alias] = definition
        self.controller.undo_stack.beginMacro("重命名 Hook 并更新引用")
        try:
            self.controller.replace_mapping(hooks, replacement, "重命名 Hook")
            for operation in self._references(old_alias):
                self.controller.set_value(operation, "hook", new_alias, "更新 Hook 引用")
        finally:
            self.controller.undo_stack.endMacro()
        self._selected_alias = new_alias
        self.refresh()
        return True

    def delete_hook(self, alias: str) -> bool:
        hooks = self._hooks()
        if alias not in hooks:
            return False
        references = self._references(alias)
        self.controller.undo_stack.beginMacro("删除 Hook 并停用引用")
        try:
            self.controller.delete_value(hooks, alias, "删除 Hook")
            for operation in references:
                self.controller.delete_value(operation, "hook", "清除 Hook 引用")
                self.controller.set_value(operation, "enabled", False, "停用缺少 Hook 的操作")
        finally:
            self.controller.undo_stack.endMacro()
        self._selected_alias = ""
        self.refresh()
        return True

    def _references(self, alias: str) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        for _object_node, entry in self.controller.document.iter_entries():
            for operation_name in ("read", "write"):
                operation = entry.get(operation_name)
                if isinstance(operation, dict) and operation.get("hook") == alias:
                    references.append(operation)
        return references

    def _prompt_add(self) -> None:
        alias, accepted = QInputDialog.getText(self, "新增 Hook", "配置别名")
        if accepted and not self.create_hook(alias):
            QMessageBox.warning(self, "无法新增", "别名必须是未使用的 C 标识符。")

    def _prompt_rename(self) -> None:
        if not self._selected_alias:
            return
        alias, accepted = QInputDialog.getText(
            self, "重命名 Hook", "新别名", text=self._selected_alias
        )
        if accepted and not self.rename_hook(self._selected_alias, alias):
            QMessageBox.warning(self, "无法重命名", "别名无效或已被使用。")

    def _prompt_delete(self) -> None:
        if not self._selected_alias:
            return
        count = len(self._references(self._selected_alias))
        suffix = f"\n该 Hook 有 {count} 处引用，删除后相关读写操作会自动停用。" if count else ""
        if QMessageBox.question(
            self,
            "删除 Hook",
            f"确定删除 Hook “{self._selected_alias}”吗？{suffix}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            self.delete_hook(self._selected_alias)

    def _select_alias(self, alias: str) -> None:
        self._selected_alias = alias
        self._refresh_detail()

    def _contract_changed(self) -> None:
        code = str(self.contract.currentData() or "write")
        self.signature.setText(HOOK_CONTRACT_DESCRIPTIONS.get(code, ""))
        self._refresh_argument_options(code, None)
        if code == "read":
            forward_index = self.return_policy.findData("forward")
            self.return_policy.setCurrentIndex(max(0, forward_index))
        self._save_definition()

    def _generation_mode_changed(self) -> None:
        self._refresh_generation_fields()
        self._save_definition()

    def _refresh_generation_fields(self) -> None:
        generated = self.generate_enabled.isChecked()
        body_mode = self.generate_mode.currentData() == "body"
        available = self.generate_enabled.isEnabled() and generated
        self.generate_mode.setEnabled(available)
        for widget in (self.call_function, self.arguments, self.return_policy):
            widget.setEnabled(available and not body_mode)
        self.body.setEnabled(available and body_mode)
        self.detail_form.setRowVisible(self.call_function, not body_mode)
        self.detail_form.setRowVisible(self.arguments, not body_mode)
        self.detail_form.setRowVisible(
            self.return_policy, not body_mode and self.contract.currentData() != "read"
        )
        self.detail_form.setRowVisible(self.body, body_mode)

    def _refresh_argument_options(self, contract: str, selected: Any) -> None:
        choices = {
            "read": (("不传参数", ""),),
            "write": (("传递 value", "value"), ("不传参数", "")),
            "transaction": (
                ("传递 subindex, value", "subindex,value"),
                ("仅传递 value", "value"),
                ("仅传递 subindex", "subindex"),
                ("不传参数", ""),
            ),
            "chunk_write": (
                ("传递 subindex, payload", "subindex,payload"),
                ("仅传递 payload", "payload"),
                ("仅传递 subindex", "subindex"),
                ("不传参数", ""),
            ),
        }.get(contract, (("无", ""),))
        if isinstance(selected, list):
            selected_key = ",".join(str(item) for item in selected)
        else:
            selected_key = str(selected or "")
        self.arguments.blockSignals(True)
        try:
            self.arguments.clear()
            for label, value in choices:
                self.arguments.addItem(label, value)
            index = self.arguments.findData(selected_key)
            self.arguments.setCurrentIndex(index if index >= 0 else 0)
        finally:
            self.arguments.blockSignals(False)

    def _save_definition(self) -> None:
        if self._refreshing or not self._selected_alias:
            return
        definition = CommentedMap(
            {
                "function": self.function.text().strip(),
                "contract": str(self.contract.currentData() or "write"),
                "description": self.description.toPlainText().strip(),
            }
        )
        if self.generate_enabled.isChecked():
            if self.generate_mode.currentData() == "body":
                definition["generate"] = CommentedMap(
                    {"enabled": True, "body": self.body.toPlainText().strip()}
                )
            else:
                argument_key = str(self.arguments.currentData() or "")
                definition["generate"] = CommentedMap(
                    {
                        "enabled": True,
                        "call_function": self.call_function.text().strip(),
                        "arguments": [item for item in argument_key.split(",") if item],
                        "return_policy": str(self.return_policy.currentData() or "forward"),
                    }
                )
        self.controller.set_value(
            self._hooks(), self._selected_alias, definition, "编辑 Hook 定义"
        )

    def _refresh_detail(self) -> None:
        self._refreshing = True
        try:
            definition = self._hooks().get(self._selected_alias)
            available = definition is not None
            self.alias_label.setText(self._selected_alias or "-")
            self.function.setEnabled(available)
            self.contract.setEnabled(available)
            self.description.setEnabled(available)
            self.generate_enabled.setEnabled(available)
            self.generate_mode.setEnabled(available)
            self.rename_button.setEnabled(available)
            self.delete_button.setEnabled(available)
            function, contract, description, generate = self._parts(definition)
            self.function.setText(function)
            index = self.contract.findData(contract)
            self.contract.setCurrentIndex(max(0, index))
            self.signature.setText(HOOK_CONTRACT_DESCRIPTIONS.get(contract, ""))
            self.description.setPlainText(description)
            generated = bool(generate.get("enabled", True)) if generate else False
            self.generate_enabled.setChecked(generated)
            mode_index = self.generate_mode.findData("body" if "body" in generate else "wrapper")
            self.generate_mode.setCurrentIndex(max(0, mode_index))
            self.call_function.setText(str(generate.get("call_function", "")))
            self.call_function.setStyleSheet(
                "border: 1px solid #B13A32;"
                if generated and not self.call_function.text().strip()
                else ""
            )
            self._refresh_argument_options(contract, generate.get("arguments"))
            return_policy = str(generate.get("return_policy", "forward"))
            return_index = self.return_policy.findData(return_policy)
            self.return_policy.setCurrentIndex(max(0, return_index))
            self.body.setPlainText(str(generate.get("body", "")))
            generation_available = available and bool(contract)
            self.generate_enabled.setEnabled(generation_available)
            self._refresh_generation_fields()
        finally:
            self._refreshing = False

    def refresh(self) -> None:
        hooks = self._hooks()
        selected = self._selected_alias if self._selected_alias in hooks else ""
        self._refreshing = True
        try:
            self.hook_list.clear()
            for alias, definition in hooks.items():
                item = QListWidgetItem(str(alias))
                generate = definition.get("generate") if isinstance(definition, dict) else None
                if isinstance(generate, dict) and bool(generate.get("enabled", True)):
                    item.setIcon(self.style().standardIcon(QStyle.SP_DialogApplyButton))
                    if "body" in generate:
                        item.setToolTip("生成自定义 C 函数体")
                    else:
                        item.setToolTip(
                            f"生成包装函数，调用 {generate.get('call_function', '')}"
                        )
                self.hook_list.addItem(item)
            if selected:
                matches = self.hook_list.findItems(selected, Qt.MatchExactly)
                if matches:
                    self.hook_list.setCurrentItem(matches[0])
            elif self.hook_list.count():
                self.hook_list.setCurrentRow(0)
        finally:
            self._refreshing = False
        current = self.hook_list.currentItem()
        self._selected_alias = current.text() if current else ""
        self._refresh_detail()
