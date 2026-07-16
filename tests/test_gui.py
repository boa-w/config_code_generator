from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QMessageBox

from config_codegen.document import ProtocolDocument
from config_codegen.gui.main_window import MainWindow
from config_codegen.gui.theme import apply_theme


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "config" / "protocol.example.yaml"


def test_main_window_edits_adds_and_deletes_entry(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    apply_theme(qapp)
    assert qapp.palette().color(QPalette.Text) != qapp.palette().color(QPalette.Base)
    path = tmp_path / "config" / "protocol.yaml"
    path.parent.mkdir()
    shutil.copyfile(SAMPLE, path)
    window = MainWindow(ProtocolDocument.load(path))
    qtbot.addWidget(window)
    window.show()

    assert window.object_tree.topLevelItemCount() == 6
    assert window.entry_model.rowCount() == 3
    assert window._last_preview.valid

    window.basic_config_action.trigger()
    assert window.content_stack.currentWidget() is window.basic_editor
    assert window.entry_editor.isHidden()
    assert not window.add_entry_action.isEnabled()
    window.basic_editor.transmit_function.setText("Custom_Send")
    window.basic_editor.transmit_function.editingFinished.emit()
    assert window.controller.document.data["protocol"]["response"]["transmit_function"] == "Custom_Send"
    window.controller.undo_stack.undo()

    window.object_tree.setCurrentItem(window.object_tree.topLevelItem(1))

    assert window.entry_model.data(window.entry_model.index(0, 4)) == "已实现"
    assert window.entry_model.data(window.entry_model.index(0, 5)) == "读写"
    assert window.entry_model.data(window.entry_model.index(0, 6)) == "标量"
    assert window.entry_editor.status.currentText() == "已实现"
    assert window.entry_editor.status.currentData() == "implemented"
    assert window.entry_editor.access.currentText() == "读写"
    assert window.entry_editor.access.currentData() == "read_write"
    assert window.entry_editor.kind.currentText() == "标量"
    assert window.entry_editor.kind.currentData() == "scalar"
    assert "单个变量" in window.entry_editor.kind_description.text()

    verified_index = window.entry_editor.status.findData("verified")
    window.entry_editor.status.setCurrentIndex(verified_index)
    assert window.controller.document.objects[0]["entries"][0]["status"] == "verified"
    assert window.entry_editor.status.currentText() == "已验证"
    window.controller.undo_stack.undo()

    enabled_index = window.entry_model.index(0, 0)
    assert window.entry_model.setData(enabled_index, Qt.Unchecked, Qt.CheckStateRole)
    assert window.controller.document.objects[0]["entries"][0]["enabled"] is False

    window.controller.undo_stack.undo()
    assert window.controller.document.objects[0]["entries"][0]["enabled"] is True

    window.add_entry()
    assert window.entry_model.rowCount() == 4
    added = window.controller.document.objects[0]["entries"][-1]
    assert added["status"] == "planned"
    assert added["enabled"] is False

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    window.delete_entry()
    assert window.entry_model.rowCount() == 3

    window.controller.undo_stack.undo()
    assert window.entry_model.rowCount() == 4
