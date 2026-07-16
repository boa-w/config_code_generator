from __future__ import annotations

import re
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFocusEvent, QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QButtonGroup,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.scalarint import HexInt

from config_codegen.gui.controller import DocumentController
from config_codegen.gui.entry_capabilities import capability_for
from config_codegen.gui.i18n import (
    ACCESS_OPTIONS,
    KIND_DESCRIPTIONS,
    KIND_OPTIONS,
    HOOK_CONTRACT_DESCRIPTIONS,
    STATUS_OPTIONS,
)


WIRE_OPTIONS = (("u8", "8 位"), ("u16", "16 位"), ("u32", "32 位"))
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
POLICY_OPTIONS = (("", "不配置"), ("reject", "拒绝"), ("clamp", "限制到边界"))
STORAGE_OPTIONS = (
    ("", "不持久化"),
    ("eeprom_u8", "EEPROM 单字节"),
    ("eeprom_bytes", "EEPROM 多字节"),
    ("hook", "存储函数"),
)


class CommitPlainTextEdit(QPlainTextEdit):
    editingFinished = Signal()

    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.editingFinished.emit()


class CollapsibleSection(QWidget):
    def __init__(self, title: str, content: QWidget, expanded: bool = False) -> None:
        super().__init__()
        self.toggle = QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(expanded)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.toggled.connect(self._toggle)
        self.content = content
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(content)
        self._toggle(expanded)

    def _toggle(self, expanded: bool) -> None:
        self.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.content.setVisible(expanded)


class CommandSelector(QToolButton):
    commandsChanged = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setPopupMode(QToolButton.InstantPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self._menu = QMenu(self)
        self.setMenu(self._menu)
        self._refreshing = False
        self.set_commands((), ())

    def set_commands(self, available: Any, selected: Any) -> None:
        selected_set = {str(item) for item in selected}
        self._refreshing = True
        try:
            self._menu.clear()
            for command in available:
                action = self._menu.addAction(str(command))
                action.setCheckable(True)
                action.setChecked(str(command) in selected_set)
                action.toggled.connect(self._changed)
        finally:
            self._refreshing = False
        self._update_text()

    def selected_commands(self) -> list[str]:
        return [action.text() for action in self._menu.actions() if action.isChecked()]

    def _changed(self) -> None:
        self._update_text()
        if not self._refreshing:
            self.commandsChanged.emit(self.selected_commands())

    def _update_text(self) -> None:
        selected = self.selected_commands()
        self.setText(", ".join(selected) if selected else "选择写命令...")


class EntryEditor(QWidget):
    def __init__(self, controller: DocumentController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.entry: CommentedMap | None = None
        self._refreshing = False
        self.setMinimumWidth(390)
        self._create_widgets()
        self.error_banner = QLabel()
        self.error_banner.setObjectName("entryErrorBanner")
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(8, 6, 8, 8)
        content_layout.setSpacing(8)
        content_layout.addWidget(self.error_banner)
        content_layout.addLayout(self._overview_form())
        content_layout.addWidget(self.kind_description)
        content_layout.addWidget(self.read_group)
        content_layout.addWidget(self.write_group)
        content_layout.addWidget(self.validation_group)
        content_layout.addWidget(self.storage_group)
        content_layout.addWidget(self.buffer_group)
        content_layout.addWidget(self.complex_structure_button)
        content_layout.addWidget(self.business_section)
        content_layout.addWidget(self.advanced_button)
        content_layout.addStretch(1)
        scroll = self._scroll_widget(content)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(scroll)

        self._connect_signals()
        self.controller.changed.connect(self.refresh)
        self.set_entry(None)

    def _create_widgets(self) -> None:
        self.enabled = QCheckBox("生成此条目")
        self.protocol_ref = QLineEdit()
        self.name = QLineEdit()
        self.description = QLineEdit()
        self.status = self._combo(STATUS_OPTIONS)
        self.access = self._combo(ACCESS_OPTIONS)
        self.kind = self._combo(KIND_OPTIONS)
        self.kind_description = QLabel()
        self.kind_description.setObjectName("kindDescription")
        self.kind_description.setWordWrap(True)

        self.read_enabled = QCheckBox("生成读取代码")
        self.read_wire_type = self._combo(WIRE_OPTIONS)
        self.read_source = QLineEdit()
        self.read_hook = QComboBox()
        self.read_hook.setEditable(True)
        self.read_hook_add = QToolButton()
        self.read_hook_add.setText("+")
        self.read_hook_add.setToolTip("新增并绑定读取 Hook")
        self.transform_kind = self._combo((("", "无"), ("divide_integer", "整数除法")))
        self.transform_divisor = QLineEdit()
        self.year_transform = QCheckBox("年份减去 2000")

        self.write_enabled = QCheckBox("生成写入代码")
        self.write_commands = CommandSelector()
        self.write_target = QLineEdit()
        self.write_hook = QComboBox()
        self.write_hook.setEditable(True)
        self.write_hook_add = QToolButton()
        self.write_hook_add.setText("+")
        self.write_hook_add.setToolTip("新增并绑定写入 Hook")
        self.authorization_value = QLineEdit()
        self.authorization_radix = 16
        self.authorization_decimal = QToolButton()
        self.authorization_decimal.setObjectName("radixButton")
        self.authorization_decimal.setText("10")
        self.authorization_decimal.setCheckable(True)
        self.authorization_decimal.setToolTip("十进制显示")
        self.authorization_hex = QToolButton()
        self.authorization_hex.setObjectName("radixButton")
        self.authorization_hex.setText("16")
        self.authorization_hex.setCheckable(True)
        self.authorization_hex.setChecked(True)
        self.authorization_hex.setToolTip("十六进制显示")
        self.authorization_radix_group = QButtonGroup(self)
        self.authorization_radix_group.setExclusive(True)
        self.authorization_radix_group.addButton(self.authorization_decimal, 10)
        self.authorization_radix_group.addButton(self.authorization_hex, 16)
        self.authorization_field = self._radix_field()
        self.acknowledge_before_hook = QCheckBox("先应答，再调用 Hook")

        self.validation_policy = self._combo(POLICY_OPTIONS)
        self.validation_minimum = QLineEdit()
        self.validation_maximum = QLineEdit()
        self.allowed_values = QLineEdit()
        self.allowed_values.setPlaceholderText("0, 1, 2")

        self.storage_kind = self._combo(STORAGE_OPTIONS)
        self.storage_function = QLineEdit()
        self.storage_address = QLineEdit()
        self.storage_addresses = QLineEdit()
        self.storage_addresses.setPlaceholderText("0, 1")
        self.byte_order = self._combo((("little_endian", "小端"), ("big_endian", "大端")))
        self.after_write = QLineEdit()

        self.buffer_source = QLineEdit()
        self.buffer_length = QLineEdit()
        self.buffer_chunk_size = QLineEdit()
        self.buffer_first_subindex = QLineEdit()
        self.buffer_padding = QLineEdit()

        self._create_business_widgets()
        self._create_groups()
        self.raw_yaml = QPlainTextEdit()
        self.raw_yaml.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.apply_yaml_button = QPushButton("应用条目 YAML")
        self.advanced_button = QPushButton("高级 YAML...")
        self.complex_structure_button = QPushButton("编辑位域 / 事务字段结构...")
        self.advanced_dialog = self._advanced_dialog()

    def _overview_form(self) -> QFormLayout:
        form = QFormLayout()
        form.addRow("启用", self.enabled)
        form.addRow("协议编号", self.protocol_ref)
        form.addRow("内部名称", self.name)
        form.addRow("显示名称", self.description)
        form.addRow("状态", self.status)
        form.addRow("访问权限", self.access)
        form.addRow("实现类型", self.kind)
        return form

    def _create_business_widgets(self) -> None:
        self.requirement_ref = QLineEdit()
        self.category = QLineEdit()
        self.unit = QLineEdit()
        self.default_value = QLineEdit()
        self.owner = QLineEdit()
        self.verification_ref = QLineEdit()
        self.value_semantics = CommitPlainTextEdit()
        self.value_semantics.setMaximumHeight(90)
        self.business_notes = CommitPlainTextEdit()
        self.business_notes.setMaximumHeight(90)
        self.source_file = QLineEdit()
        self.source_symbol = QLineEdit()
        self.module = QLineEdit()
        self.implementation_notes = CommitPlainTextEdit()
        self.implementation_notes.setMaximumHeight(90)
        business_content = QWidget()
        form = QFormLayout()
        form.addRow("需求编号", self.requirement_ref)
        form.addRow("业务分类", self.category)
        form.addRow("单位", self.unit)
        form.addRow("默认值", self.default_value)
        form.addRow("责任人", self.owner)
        form.addRow("验证依据", self.verification_ref)
        form.addRow("取值语义", self.value_semantics)
        form.addRow("业务备注", self.business_notes)
        form.addRow(self._section_label("代码追踪"))
        form.addRow("源码文件", self.source_file)
        form.addRow("源码符号", self.source_symbol)
        form.addRow("所属模块", self.module)
        form.addRow("实现备注", self.implementation_notes)
        business_content.setLayout(form)
        self.business_section = CollapsibleSection(
            "业务追踪与代码来源", business_content, expanded=False
        )

    def _create_groups(self) -> None:
        read_form = QFormLayout()
        read_form.addRow("启用", self.read_enabled)
        read_form.addRow("线宽类型", self.read_wire_type)
        read_form.addRow("变量来源", self.read_source)
        self.read_hook_field = self._hook_field(self.read_hook, self.read_hook_add)
        read_form.addRow("读取 Hook", self.read_hook_field)
        read_form.addRow("转换", self.transform_kind)
        read_form.addRow("除数", self.transform_divisor)
        read_form.addRow("年份转换", self.year_transform)
        self.read_form = read_form
        self.read_group = QGroupBox("读取")
        self.read_group.setLayout(read_form)

        write_form = QFormLayout()
        write_form.addRow("启用", self.write_enabled)
        write_form.addRow("写命令", self.write_commands)
        write_form.addRow("目标变量", self.write_target)
        self.write_hook_field = self._hook_field(self.write_hook, self.write_hook_add)
        write_form.addRow("写入 Hook", self.write_hook_field)
        write_form.addRow("授权值", self.authorization_field)
        write_form.addRow("Hook 顺序", self.acknowledge_before_hook)
        self.write_form = write_form
        self.write_group = QGroupBox("写入")
        self.write_group.setLayout(write_form)

        validation_form = QFormLayout()
        validation_form.addRow("越界策略", self.validation_policy)
        validation_form.addRow("最小值", self.validation_minimum)
        validation_form.addRow("最大值", self.validation_maximum)
        validation_form.addRow("允许值", self.allowed_values)
        self.validation_group = QGroupBox("数值校验")
        self.validation_group.setLayout(validation_form)

        storage_form = QFormLayout()
        storage_form.addRow("存储类型", self.storage_kind)
        storage_form.addRow("存储函数", self.storage_function)
        storage_form.addRow("存储地址", self.storage_address)
        storage_form.addRow("地址列表", self.storage_addresses)
        storage_form.addRow("字节序", self.byte_order)
        storage_form.addRow("写后函数", self.after_write)
        self.storage_group = QGroupBox("持久化与写后处理")
        self.storage_group.setLayout(storage_form)

        buffer_form = QFormLayout()
        buffer_form.addRow("数组来源", self.buffer_source)
        buffer_form.addRow("总长度", self.buffer_length)
        buffer_form.addRow("分包大小", self.buffer_chunk_size)
        buffer_form.addRow("起始 SubIndex", self.buffer_first_subindex)
        buffer_form.addRow("填充值", self.buffer_padding)
        self.buffer_group = QGroupBox("分包缓冲区")
        self.buffer_group.setLayout(buffer_form)

    def _advanced_dialog(self) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("高级条目 YAML")
        dialog.setModal(True)
        dialog.resize(680, 620)
        note = QLabel("可编辑位域 bits、事务 fields 以及其他完整条目字段。应用后仍可撤销。")
        note.setWordWrap(True)
        layout = QVBoxLayout(dialog)
        layout.addWidget(note)
        layout.addWidget(self.raw_yaml, 1)
        layout.addWidget(self.apply_yaml_button, 0, Qt.AlignRight)
        return dialog

    @staticmethod
    def _combo(options: tuple[tuple[str, str], ...]) -> QComboBox:
        combo = QComboBox()
        for code, label in options:
            combo.addItem(label, code)
        return combo

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        font = label.font()
        font.setBold(True)
        label.setFont(font)
        return label

    @staticmethod
    def _hook_field(combo: QComboBox, button: QToolButton) -> QWidget:
        field = QWidget()
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(combo, 1)
        layout.addWidget(button)
        return field

    def _radix_field(self) -> QWidget:
        field = QWidget()
        layout = QHBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(self.authorization_value, 1)
        layout.addWidget(self.authorization_decimal)
        layout.addWidget(self.authorization_hex)
        return field

    @staticmethod
    def _scroll_widget(content: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _connect_signals(self) -> None:
        self.enabled.clicked.connect(lambda value: self._set("enabled", value, "切换协议条目"))
        for widget, key, label in (
            (self.protocol_ref, "protocol_ref", "编辑协议编号"),
            (self.name, "name", "编辑内部名称"),
            (self.description, "description", "编辑显示名称"),
        ):
            widget.editingFinished.connect(lambda w=widget, k=key, l=label: self._set(k, w.text(), l))
        self.status.currentIndexChanged.connect(lambda: self._set_combo("status", self.status, "编辑状态"))
        self.access.currentIndexChanged.connect(lambda: self._set_combo("access", self.access, "编辑访问权限"))
        self.kind.currentIndexChanged.connect(self._kind_changed)

        business_lines = {
            self.requirement_ref: ("business", "requirement_ref", False),
            self.category: ("business", "category", False),
            self.unit: ("business", "unit", False),
            self.default_value: ("business", "default_value", True),
            self.owner: ("business", "owner", False),
            self.verification_ref: ("business", "verification_ref", False),
            self.source_file: ("implementation", "source_file", False),
            self.source_symbol: ("implementation", "source_symbol", False),
            self.module: ("implementation", "module", False),
        }
        for widget, (section, key, numeric) in business_lines.items():
            widget.editingFinished.connect(
                lambda w=widget, s=section, k=key, n=numeric: self._set_nested_text(s, k, w.text(), n)
            )
        for widget, section, key in (
            (self.value_semantics, "business", "value_semantics"),
            (self.business_notes, "business", "notes"),
            (self.implementation_notes, "implementation", "notes"),
        ):
            widget.editingFinished.connect(lambda w=widget, s=section, k=key: self._commit_multiline(w, s, k))

        self.read_enabled.clicked.connect(lambda value: self._toggle_operation("read", value))
        self.read_wire_type.currentIndexChanged.connect(lambda: self._set_nested("read", "wire_type", self.read_wire_type.currentData()))
        self.read_source.editingFinished.connect(lambda: self._set_nested_text("read", "source", self.read_source.text()))
        assert self.read_hook.lineEdit() is not None
        self.read_hook.lineEdit().editingFinished.connect(
            lambda: self._set_nested_text("read", "hook", self.read_hook.currentText())
        )
        self.read_hook.activated.connect(
            lambda _index: self._set_nested_text("read", "hook", self.read_hook.currentText())
        )
        self.read_hook_add.clicked.connect(
            lambda: self._prompt_create_hook("read", "read", self.read_hook)
        )
        self.transform_kind.currentIndexChanged.connect(self._set_transform_kind)
        self.transform_divisor.editingFinished.connect(self._set_transform_divisor)
        self.year_transform.clicked.connect(
            lambda value: self._set_nested("read", "year_transform", "subtract_2000" if value else None)
        )

        self.write_enabled.clicked.connect(lambda value: self._toggle_operation("write", value))
        self.write_commands.commandsChanged.connect(self._set_commands)
        self.write_target.editingFinished.connect(lambda: self._set_nested_text("write", "target", self.write_target.text()))
        assert self.write_hook.lineEdit() is not None
        self.write_hook.lineEdit().editingFinished.connect(
            lambda: self._set_nested_text("write", "hook", self.write_hook.currentText())
        )
        self.write_hook.activated.connect(
            lambda _index: self._set_nested_text("write", "hook", self.write_hook.currentText())
        )
        self.write_hook_add.clicked.connect(self._prompt_create_write_hook)
        self.validation_policy.currentIndexChanged.connect(lambda: self._set_deep("write", "validation", "policy", self.validation_policy.currentData()))
        self.validation_minimum.editingFinished.connect(lambda: self._set_deep_number("write", "validation", "minimum", self.validation_minimum.text()))
        self.validation_maximum.editingFinished.connect(lambda: self._set_deep_number("write", "validation", "maximum", self.validation_maximum.text()))
        self.allowed_values.editingFinished.connect(self._set_allowed_values)
        self.storage_kind.currentIndexChanged.connect(lambda: self._set_deep("write", "storage", "kind", self.storage_kind.currentData()))
        self.storage_function.editingFinished.connect(lambda: self._set_deep_text("write", "storage", "function", self.storage_function.text()))
        self.storage_address.editingFinished.connect(lambda: self._set_deep_number("write", "storage", "address", self.storage_address.text()))
        self.storage_addresses.editingFinished.connect(self._set_storage_addresses)
        self.byte_order.currentIndexChanged.connect(lambda: self._set_deep("write", "storage", "byte_order", self.byte_order.currentData()))
        self.after_write.editingFinished.connect(lambda: self._set_deep_text("write", "after_write", "function", self.after_write.text()))
        self.authorization_value.editingFinished.connect(self._set_authorization)
        self.authorization_radix_group.idClicked.connect(self._set_authorization_radix)
        self.acknowledge_before_hook.clicked.connect(lambda value: self._set_nested("write", "acknowledge_before_hook", value))

        for widget, key in (
            (self.buffer_source, "source"),
            (self.buffer_length, "length"),
            (self.buffer_chunk_size, "chunk_size"),
            (self.buffer_first_subindex, "first_subindex"),
            (self.buffer_padding, "padding"),
        ):
            numeric = key != "source"
            widget.editingFinished.connect(lambda w=widget, k=key, n=numeric: self._set_nested_text("buffer", k, w.text(), n))
        self.apply_yaml_button.clicked.connect(self._apply_yaml)
        self.advanced_button.clicked.connect(self._open_advanced)
        self.complex_structure_button.clicked.connect(self._open_advanced)

    def set_entry(self, entry: CommentedMap | None) -> None:
        self.entry = entry
        self.refresh()

    def _open_advanced(self) -> None:
        if self.entry is None:
            return
        self.raw_yaml.setPlainText(self.controller.document.dump_node(self.entry))
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _set(self, key: str, value: object, label: str) -> None:
        if not self._refreshing and self.entry is not None:
            self.controller.set_value(self.entry, key, value, label)

    def _set_combo(self, key: str, combo: QComboBox, label: str) -> None:
        self._set(key, str(combo.currentData() or ""), label)

    def _kind_changed(self) -> None:
        code = str(self.kind.currentData() or "")
        self.kind_description.setText(KIND_DESCRIPTIONS.get(code, "未知实现类型。"))
        self._set("kind", code, "编辑实现类型")

    def _mapping(self, section: str, create: bool = False) -> dict[str, Any] | None:
        if self.entry is None:
            return None
        node = self.entry.get(section)
        if isinstance(node, dict):
            return node
        if create:
            node = CommentedMap()
            self.controller.set_value(self.entry, section, node, f"创建 {section} 配置")
            return node
        return None

    def _set_nested(self, section: str, key: str, value: object | None) -> None:
        if self._refreshing:
            return
        node = self._mapping(section, value is not None)
        if node is None:
            return
        if value is None or value == "":
            self.controller.delete_value(node, key, f"清除 {section}.{key}")
        else:
            self.controller.set_value(node, key, value, f"编辑 {section}.{key}")

    def _set_nested_text(self, section: str, key: str, text: str, numeric: bool = False) -> None:
        value = self._parse_number(text) if numeric and text.strip() else text.strip() or None
        self._set_nested(section, key, value)

    def _set_deep(self, section: str, child: str, key: str, value: object | None) -> None:
        parent = self._mapping(section, value not in (None, ""))
        if parent is None:
            return
        node = parent.get(child)
        if not isinstance(node, dict):
            if value in (None, ""):
                return
            node = CommentedMap()
            self.controller.set_value(parent, child, node, f"创建 {section}.{child}")
        if value in (None, ""):
            self.controller.delete_value(node, key, f"清除 {section}.{child}.{key}")
        else:
            self.controller.set_value(node, key, value, f"编辑 {section}.{child}.{key}")

    def _set_deep_text(self, section: str, child: str, key: str, text: str) -> None:
        self._set_deep(section, child, key, text.strip() or None)

    def _set_deep_number(self, section: str, child: str, key: str, text: str) -> None:
        self._set_deep(section, child, key, self._parse_number(text) if text.strip() else None)

    def _toggle_operation(self, operation: str, enabled: bool) -> None:
        node = self._mapping(operation, enabled)
        if node is not None:
            self.controller.set_value(node, "enabled", enabled, f"切换 {operation} 代码")

    def _set_transform_kind(self) -> None:
        kind = str(self.transform_kind.currentData() or "")
        self._set_deep("read", "transform", "kind", kind or None)

    def _set_transform_divisor(self) -> None:
        self._set_deep_number("read", "transform", "divisor", self.transform_divisor.text())

    def _set_commands(self, values: list[str]) -> None:
        self._set_nested("write", "commands", values if values else None)

    def _set_allowed_values(self) -> None:
        values = self._parse_number_list(self.allowed_values.text())
        self._set_deep("write", "validation", "allowed_values", values or None)

    def _set_storage_addresses(self) -> None:
        values = self._parse_number_list(self.storage_addresses.text())
        self._set_deep("write", "storage", "addresses", values or None)

    def _set_authorization(self) -> None:
        text = self.authorization_value.text().strip()
        value: object | None = None
        if text:
            try:
                if self.authorization_radix == 16:
                    normalized = text[2:] if text.lower().startswith("0x") else text
                    value = HexInt(int(normalized, 16))
                else:
                    value = int(text, 10)
            except ValueError:
                value = text
        self._set_deep("write", "authorization", "kind", "magic_value" if text else None)
        self._set_deep("write", "authorization", "value", value)

    def _set_authorization_radix(self, radix: int) -> None:
        self.authorization_radix = radix
        if self.entry is None:
            return
        write = self.entry.get("write", {})
        value = write.get("authorization", {}).get("value") if isinstance(write, dict) else None
        self.authorization_value.setText(self._format_authorization(value))

    def _prompt_create_write_hook(self) -> None:
        kind = str(self.entry.get("kind", "")) if self.entry is not None else ""
        contract = (
            "transaction" if kind == "transaction_fields"
            else "chunk_write" if kind == "chunked_buffer"
            else "write"
        )
        self._prompt_create_hook(contract, "write", self.write_hook)

    def _prompt_create_hook(self, contract: str, operation: str, combo: QComboBox) -> None:
        if self.entry is None:
            return
        alias, accepted = QInputDialog.getText(self, "新增 Hook", "配置别名")
        alias = alias.strip()
        hooks = self.controller.document.data.get("hooks")
        if not accepted:
            return
        if not isinstance(hooks, dict):
            hooks = CommentedMap()
            self.controller.set_value(self.controller.document.data, "hooks", hooks, "创建 Hook 注册表")
        if not _IDENTIFIER.fullmatch(alias) or alias in hooks:
            QMessageBox.warning(self, "无法新增", "别名必须是未使用的 C 标识符。")
            return
        function, accepted = QInputDialog.getText(
            self, "新增 Hook", "C 函数名称", text=alias
        )
        function = function.strip()
        if not accepted:
            return
        if not _IDENTIFIER.fullmatch(function):
            QMessageBox.warning(self, "无法新增", "C 函数名称必须是有效标识符。")
            return
        definition = CommentedMap(
            {"function": function, "contract": contract, "description": ""}
        )
        self.controller.undo_stack.beginMacro("新增并绑定 Hook")
        try:
            self.controller.set_value(hooks, alias, definition, "新增 Hook")
            self._set_nested(operation, "hook", alias)
        finally:
            self.controller.undo_stack.endMacro()
        combo.setCurrentText(alias)

    def _commit_multiline(self, widget: QPlainTextEdit, section: str, key: str) -> None:
        if not self._refreshing:
            self._set_nested(section, key, widget.toPlainText().strip() or None)

    @staticmethod
    def _parse_number(text: str) -> object:
        value = text.strip()
        try:
            number = int(value, 0)
            return HexInt(number) if value.lower().startswith("0x") else number
        except ValueError:
            return value

    @classmethod
    def _parse_number_list(cls, text: str) -> list[object]:
        return [cls._parse_number(item) for item in text.split(",") if item.strip()]

    def _apply_yaml(self) -> None:
        if self.entry is None:
            return
        yaml = YAML(typ="rt")
        try:
            value = yaml.load(self.raw_yaml.toPlainText())
        except Exception as exc:
            QMessageBox.critical(self, "YAML 格式错误", str(exc))
            return
        if not isinstance(value, CommentedMap):
            QMessageBox.critical(self, "YAML 格式错误", "条目 YAML 必须是一个映射。")
            return
        self.controller.replace_mapping(self.entry, value, "编辑完整条目 YAML")
        self.advanced_dialog.accept()

    @staticmethod
    def _select_code(combo: QComboBox, code: object) -> None:
        value = str(code or "")
        index = combo.findData(value)
        if index < 0:
            combo.addItem(value or "未设置", value)
            index = combo.count() - 1
        combo.setCurrentIndex(index)

    @staticmethod
    def _text(value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, int):
            return f"0x{value:X}" if isinstance(value, HexInt) else str(value)
        return str(value)

    def _format_authorization(self, value: object) -> str:
        if not isinstance(value, int):
            return str(value or "")
        if self.authorization_radix == 16:
            return f"0x{value:X}"
        return str(value)

    def _populate_hook_combo(self, combo: QComboBox, selected: str, expected: str) -> None:
        hooks = self.controller.document.data.get("hooks", {})
        combo.clear()
        combo.addItem("", "")
        for alias, definition in hooks.items():
            if isinstance(definition, str):
                function, contract, description = definition, "generic", ""
            elif isinstance(definition, dict):
                function = str(definition.get("function", ""))
                contract = str(definition.get("contract", "generic"))
                description = str(definition.get("description", ""))
            else:
                continue
            if contract not in {"generic", expected} and alias != selected:
                continue
            combo.addItem(str(alias), str(alias))
            tooltip = f"{function}\n{HOOK_CONTRACT_DESCRIPTIONS.get(contract, contract)}"
            if description:
                tooltip += f"\n{description}"
            combo.setItemData(combo.count() - 1, tooltip, Qt.ToolTipRole)
        index = combo.findData(selected)
        if index >= 0:
            combo.setCurrentIndex(index)
        else:
            combo.setEditText(selected)

    def _update_visibility(self) -> None:
        if self.entry is None:
            return
        kind = str(self.entry.get("kind", ""))
        access = str(self.entry.get("access", ""))
        capability = capability_for(kind)
        readable = access != "write_only"
        writable = access != "read_only"
        self.read_group.setVisible(readable)
        self.write_group.setVisible(writable)
        self.validation_group.setVisible(writable and capability.validation)
        self.storage_group.setVisible(writable and capability.storage)
        self.buffer_group.setVisible(capability.buffer)
        self.complex_structure_button.setVisible(capability.complex_structure)

        self.read_form.setRowVisible(self.read_source, capability.read_source)
        self.read_form.setRowVisible(self.read_hook_field, capability.read_hook)
        self.read_form.setRowVisible(self.transform_kind, capability.read_transform)
        self.read_form.setRowVisible(
            self.transform_divisor,
            capability.read_transform and self.transform_kind.currentData() == "divide_integer",
        )
        self.read_form.setRowVisible(self.year_transform, kind == "transaction_fields")
        self.write_form.setRowVisible(self.write_target, capability.write_target)
        self.write_form.setRowVisible(self.write_hook_field, capability.write_hook)
        self.write_form.setRowVisible(self.authorization_field, capability.authorization)
        self.write_form.setRowVisible(
            self.acknowledge_before_hook, capability.write_hook
        )

        storage_kind = str(self.storage_kind.currentData() or "")
        storage_form = self.storage_group.layout()
        assert isinstance(storage_form, QFormLayout)
        storage_form.setRowVisible(self.storage_function, bool(storage_kind))
        storage_form.setRowVisible(self.storage_address, storage_kind == "eeprom_u8")
        storage_form.setRowVisible(self.storage_addresses, storage_kind == "eeprom_bytes")
        storage_form.setRowVisible(self.byte_order, storage_kind == "eeprom_bytes")

    def _update_inline_errors(self) -> None:
        widgets = (
            self.name,
            self.kind,
            self.access,
            self.read_enabled,
            self.read_source,
            self.read_hook,
            self.write_enabled,
            self.write_commands,
            self.write_target,
            self.write_hook,
            self.buffer_source,
        )
        for widget in widgets:
            widget.setStyleSheet("")
            widget.setToolTip("")
        if self.entry is None or not bool(self.entry.get("enabled", True)):
            self.error_banner.hide()
            return
        kind = str(self.entry.get("kind", ""))
        access = str(self.entry.get("access", ""))
        capability = capability_for(kind)
        errors: list[tuple[QWidget, str]] = []
        if not _IDENTIFIER.fullmatch(str(self.entry.get("name", ""))):
            errors.append((self.name, "内部名称不是有效的 C 标识符"))
        if not kind:
            errors.append((self.kind, "请选择实现类型"))
        if not access:
            errors.append((self.access, "请选择访问权限"))
        read = self.entry.get("read")
        if access != "write_only":
            if not isinstance(read, dict):
                errors.append((self.read_enabled, "缺少读取配置"))
            elif read.get("enabled", True):
                if capability.read_source and not read.get("source"):
                    errors.append((self.read_source, "读取变量不能为空"))
                if capability.read_hook and not read.get("hook"):
                    errors.append((self.read_hook, "请选择读取 Hook"))
        write = self.entry.get("write")
        if access != "read_only":
            if not isinstance(write, dict):
                errors.append((self.write_enabled, "缺少写入配置"))
            elif write.get("enabled", True):
                if not write.get("commands"):
                    errors.append((self.write_commands, "至少选择一个写命令"))
                if capability.write_target and not write.get("target"):
                    errors.append((self.write_target, "目标变量不能为空"))
                if capability.write_hook and not write.get("hook"):
                    errors.append((self.write_hook, "请选择写入 Hook"))
        if capability.buffer:
            buffer = self.entry.get("buffer")
            if not isinstance(buffer, dict) or not buffer.get("source"):
                errors.append((self.buffer_source, "缓冲区来源不能为空"))
        if errors:
            for widget, message in errors:
                widget.setStyleSheet("border: 1px solid #B13A32;")
                widget.setToolTip(message)
            self.error_banner.setText(
                f"{len(errors)} 个字段需要处理：" + "；".join(message for _, message in errors[:3])
            )
            self.error_banner.show()
        else:
            self.error_banner.hide()

    def refresh(self) -> None:
        self._refreshing = True
        try:
            available = self.entry is not None
            self.setEnabled(available)
            if not available:
                self.raw_yaml.clear()
                return
            assert self.entry is not None
            self.enabled.setChecked(bool(self.entry.get("enabled", True)))
            self.protocol_ref.setText(str(self.entry.get("protocol_ref", "")))
            self.name.setText(str(self.entry.get("name", "")))
            self.description.setText(str(self.entry.get("description", "")))
            self._select_code(self.status, self.entry.get("status", ""))
            self._select_code(self.access, self.entry.get("access", ""))
            self._select_code(self.kind, self.entry.get("kind", ""))
            self.kind_description.setText(KIND_DESCRIPTIONS.get(str(self.entry.get("kind", "")), "未知实现类型。"))

            business = self.entry.get("business", {})
            implementation = self.entry.get("implementation", {})
            for widget, value in (
                (self.requirement_ref, business.get("requirement_ref", "")),
                (self.category, business.get("category", "")),
                (self.unit, business.get("unit", "")),
                (self.default_value, business.get("default_value", "")),
                (self.owner, business.get("owner", "")),
                (self.verification_ref, business.get("verification_ref", "")),
                (self.source_file, implementation.get("source_file", "")),
                (self.source_symbol, implementation.get("source_symbol", "")),
                (self.module, implementation.get("module", "")),
            ):
                widget.setText(self._text(value))
            self.value_semantics.setPlainText(str(business.get("value_semantics", "")))
            self.business_notes.setPlainText(str(business.get("notes", "")))
            self.implementation_notes.setPlainText(str(implementation.get("notes", "")))

            read_node = self.entry.get("read")
            write_node = self.entry.get("write")
            read = read_node if isinstance(read_node, dict) else {}
            write = write_node if isinstance(write_node, dict) else {}
            self.read_enabled.setChecked(isinstance(read_node, dict) and bool(read.get("enabled", True)))
            self._select_code(self.read_wire_type, read.get("wire_type", "u16"))
            self.read_source.setText(str(read.get("source", "")))
            self._populate_hook_combo(self.read_hook, str(read.get("hook", "")), "read")
            transform = read.get("transform", {})
            self._select_code(self.transform_kind, transform.get("kind", ""))
            self.transform_divisor.setText(self._text(transform.get("divisor")))
            self.year_transform.setChecked(read.get("year_transform") == "subtract_2000")

            self.write_enabled.setChecked(isinstance(write_node, dict) and bool(write.get("enabled", True)))
            available_commands = [
                name
                for name in self.controller.document.data.get("protocol", {}).get("commands", {})
                if name != "read"
            ]
            self.write_commands.set_commands(available_commands, write.get("commands", []))
            self.write_target.setText(str(write.get("target", "")))
            expected_write_contract = (
                "transaction" if self.entry.get("kind") == "transaction_fields"
                else "chunk_write" if self.entry.get("kind") == "chunked_buffer"
                else "write"
            )
            self._populate_hook_combo(
                self.write_hook, str(write.get("hook", "")), expected_write_contract
            )
            validation = write.get("validation", {})
            self._select_code(self.validation_policy, validation.get("policy", ""))
            self.validation_minimum.setText(self._text(validation.get("minimum")))
            self.validation_maximum.setText(self._text(validation.get("maximum")))
            self.allowed_values.setText(", ".join(self._text(item) for item in validation.get("allowed_values", [])))
            storage = write.get("storage", {})
            self._select_code(self.storage_kind, storage.get("kind", ""))
            self.storage_function.setText(str(storage.get("function", "")))
            self.storage_address.setText(self._text(storage.get("address")))
            self.storage_addresses.setText(", ".join(self._text(item) for item in storage.get("addresses", [])))
            self._select_code(self.byte_order, storage.get("byte_order", "little_endian"))
            self.after_write.setText(str(write.get("after_write", {}).get("function", "")))
            self.authorization_value.setText(
                self._format_authorization(write.get("authorization", {}).get("value"))
            )
            self.acknowledge_before_hook.setChecked(bool(write.get("acknowledge_before_hook", False)))

            buffer = self.entry.get("buffer", {})
            self.buffer_source.setText(str(buffer.get("source", "")))
            self.buffer_length.setText(self._text(buffer.get("length")))
            self.buffer_chunk_size.setText(self._text(buffer.get("chunk_size")))
            self.buffer_first_subindex.setText(self._text(buffer.get("first_subindex")))
            self.buffer_padding.setText(self._text(buffer.get("padding")))
            self.raw_yaml.setPlainText(self.controller.document.dump_node(self.entry))
            self._update_visibility()
            self._update_inline_errors()
        finally:
            self._refreshing = False
