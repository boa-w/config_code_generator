from __future__ import annotations

from typing import Any

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from ruamel.yaml.comments import CommentedMap

from config_codegen.document import format_subindex
from config_codegen.gui.controller import DocumentController


class EntryTableModel(QAbstractTableModel):
    HEADERS = ("启用", "协议编号", "SubIndex", "名称", "状态", "访问", "类型")

    def __init__(self, controller: DocumentController, parent: Any = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self._object: CommentedMap | None = None
        self.controller.changed.connect(self.refresh)

    def set_object(self, object_node: CommentedMap | None) -> None:
        self.beginResetModel()
        self._object = object_node
        self.endResetModel()

    def entries(self) -> list[CommentedMap]:
        if self._object is None:
            return []
        return list(self.controller.document.entries(self._object))

    def entry_at(self, row: int) -> CommentedMap | None:
        entries = self.entries()
        return entries[row] if 0 <= row < len(entries) else None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.entries())

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        entry = self.entry_at(index.row())
        if entry is None:
            return None
        enabled = bool(entry.get("enabled", True))
        if role == Qt.CheckStateRole and index.column() == 0:
            return Qt.Checked if enabled else Qt.Unchecked
        if role == Qt.ForegroundRole and not enabled:
            return QColor("#888888")
        if role not in (Qt.DisplayRole, Qt.EditRole):
            return None
        values = (
            "",
            entry.get("protocol_ref", ""),
            format_subindex(entry.get("subindex", "")),
            entry.get("description", entry.get("name", "")),
            entry.get("status", ""),
            entry.get("access", "-"),
            entry.get("kind", "-"),
        )
        return values[index.column()]

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        flags = super().flags(index) | Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.column() == 0:
            return flags | Qt.ItemIsUserCheckable
        if index.column() in {1, 3, 4}:
            return flags | Qt.ItemIsEditable
        return flags

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        entry = self.entry_at(index.row())
        if entry is None:
            return False
        if index.column() == 0 and role == Qt.CheckStateRole:
            self.controller.set_value(entry, "enabled", value == Qt.Checked, "切换协议条目")
            return True
        keys = {1: "protocol_ref", 3: "description", 4: "status"}
        if role == Qt.EditRole and index.column() in keys:
            self.controller.set_value(entry, keys[index.column()], str(value), "编辑协议条目")
            return True
        return False

    def refresh(self) -> None:
        if self.rowCount():
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, self.columnCount() - 1),
            )
