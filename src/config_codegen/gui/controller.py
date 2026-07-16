from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack

from config_codegen.document import ProtocolDocument


class SetMappingValueCommand(QUndoCommand):
    def __init__(
        self,
        mapping: dict[str, Any],
        key: str,
        value: Any,
        text: str,
        changed: Callable[[], None],
    ) -> None:
        super().__init__(text)
        self._mapping = mapping
        self._key = key
        self._value = value
        self._existed = key in mapping
        self._old_value = mapping.get(key)
        self._changed = changed

    def redo(self) -> None:
        self._mapping[self._key] = self._value
        self._changed()

    def undo(self) -> None:
        if self._existed:
            self._mapping[self._key] = self._old_value
        else:
            self._mapping.pop(self._key, None)
        self._changed()


class DeleteMappingValueCommand(QUndoCommand):
    def __init__(self, mapping: dict[str, Any], key: str, text: str, changed: Callable[[], None]) -> None:
        super().__init__(text)
        self._mapping = mapping
        self._key = key
        self._value = mapping[key]
        self._changed = changed

    def redo(self) -> None:
        self._mapping.pop(self._key, None)
        self._changed()

    def undo(self) -> None:
        self._mapping[self._key] = self._value
        self._changed()


class ReplaceMappingCommand(QUndoCommand):
    def __init__(self, mapping: dict[str, Any], value: dict[str, Any], text: str, changed: Callable[[], None]) -> None:
        super().__init__(text)
        self._mapping = mapping
        self._before = deepcopy(mapping)
        self._after = deepcopy(value)
        self._changed = changed

    def _apply(self, value: dict[str, Any]) -> None:
        self._mapping.clear()
        self._mapping.update(deepcopy(value))
        self._changed()

    def redo(self) -> None:
        self._apply(self._after)

    def undo(self) -> None:
        self._apply(self._before)

class InsertSequenceItemCommand(QUndoCommand):
    def __init__(self, sequence: list[Any], index: int, item: Any, text: str, changed: Callable[[], None]) -> None:
        super().__init__(text)
        self._sequence = sequence
        self._index = index
        self._item = item
        self._changed = changed

    def redo(self) -> None:
        self._sequence.insert(self._index, self._item)
        self._changed()

    def undo(self) -> None:
        self._sequence.pop(self._index)
        self._changed()


class RemoveSequenceItemCommand(QUndoCommand):
    def __init__(self, sequence: list[Any], index: int, text: str, changed: Callable[[], None]) -> None:
        super().__init__(text)
        self._sequence = sequence
        self._index = index
        self._item = sequence[index]
        self._changed = changed

    def redo(self) -> None:
        self._sequence.pop(self._index)
        self._changed()

    def undo(self) -> None:
        self._sequence.insert(self._index, self._item)
        self._changed()

class DocumentController(QObject):
    changed = Signal()
    structure_changed = Signal()

    def __init__(self, document: ProtocolDocument, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.document = document
        self.undo_stack = QUndoStack(self)

    def set_value(self, mapping: dict[str, Any], key: str, value: Any, label: str) -> None:
        if mapping.get(key) == value and key in mapping:
            return
        self.undo_stack.push(SetMappingValueCommand(mapping, key, value, label, self.changed.emit))

    def delete_value(self, mapping: dict[str, Any], key: str, label: str) -> None:
        if key in mapping:
            self.undo_stack.push(DeleteMappingValueCommand(mapping, key, label, self.changed.emit))

    def replace_mapping(self, mapping: dict[str, Any], value: dict[str, Any], label: str) -> None:
        self.undo_stack.push(ReplaceMappingCommand(mapping, value, label, self.changed.emit))

    def insert_item(self, sequence: list[Any], index: int, item: Any, label: str) -> None:
        self.undo_stack.push(
            InsertSequenceItemCommand(sequence, index, item, label, self._emit_structure_changed)
        )

    def remove_item(self, sequence: list[Any], index: int, label: str) -> None:
        self.undo_stack.push(
            RemoveSequenceItemCommand(sequence, index, label, self._emit_structure_changed)
        )

    def replace_objects(self, objects: Any) -> None:
        self.undo_stack.push(
            SetMappingValueCommand(
                self.document.data,
                "objects",
                objects,
                "导入 CSV",
                self._emit_structure_changed,
            )
        )

    def _emit_structure_changed(self) -> None:
        self.structure_changed.emit()
        self.changed.emit()

    def mark_clean(self) -> None:
        self.undo_stack.setClean()
