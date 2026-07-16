from pathlib import Path
import shutil

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QInputDialog, QMessageBox

from config_codegen.document import ProtocolDocument
from config_codegen.gui.main_window import MainWindow
from config_codegen.gui.theme import apply_theme
from config_codegen.version import BASE_VERSION


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "config" / "protocol.example.yaml"


def test_main_window_edits_adds_and_deletes_entry(qapp, qtbot, tmp_path: Path, monkeypatch) -> None:
    apply_theme(qapp)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Discard)
    assert qapp.palette().color(QPalette.Text) != qapp.palette().color(QPalette.Base)
    path = tmp_path / "config" / "protocol.yaml"
    path.parent.mkdir()
    shutil.copyfile(SAMPLE, path)
    window = MainWindow(ProtocolDocument.load(path))
    qtbot.addWidget(window)
    window.show()

    assert window.object_tree.topLevelItemCount() == 10
    assert window.entry_model.rowCount() == 3
    assert window._last_preview.valid
    assert "Demo_Hook_ReadIndicator" in window._last_preview.hook_fragment
    assert "Demo_Hook_ReadIndicator" in window.hook_preview.toPlainText()

    window.basic_config_action.trigger()
    assert window.content_stack.currentWidget() is window.basic_editor
    assert window.entry_editor.isHidden()
    assert not window.add_entry_action.isEnabled()
    window.object_tree.setCurrentItem(window.object_tree.topLevelItem(3))
    assert window.basic_editor.stack.currentWidget() is window.basic_editor.pages["hooks"]
    window.basic_config_action.trigger()
    window.basic_editor.transmit_function.setText("Custom_Send")
    window.basic_editor.transmit_function.editingFinished.emit()
    assert window.controller.document.data["protocol"]["response"]["transmit_function"] == "Custom_Send"
    window.controller.undo_stack.undo()
    registry = window.basic_editor.hook_registry
    assert registry.generate_enabled.isChecked()
    assert registry.call_function.text() == "Demo_ReadIndicatorState"
    assert registry.arguments.currentData() == ""
    registry.call_function.setText("Demo_ReadIndicatorStateV2")
    registry.call_function.editingFinished.emit()
    assert (
        window.controller.document.data["hooks"]["read_indicator"]["generate"]["call_function"]
        == "Demo_ReadIndicatorStateV2"
    )
    window.controller.undo_stack.undo()
    body_mode = registry.generate_mode.findData("body")
    registry.generate_mode.setCurrentIndex(body_mode)
    registry.body.setPlainText("return 0u;")
    registry.body.editingFinished.emit()
    assert window.controller.document.data["hooks"]["read_indicator"]["generate"] == {
        "enabled": True,
        "body": "return 0u;",
    }
    window.controller.undo_stack.undo()
    assert registry.create_hook("new_demo_hook")
    assert window.controller.document.data["hooks"]["new_demo_hook"]["function"] == "new_demo_hook"
    window.controller.undo_stack.undo()
    assert registry.rename_hook("read_indicator", "read_indicator_v2")
    indicator_entry = window.controller.document.objects[1]["entries"][2]
    assert indicator_entry["read"]["hook"] == "read_indicator_v2"
    window.controller.undo_stack.undo()
    assert indicator_entry["read"]["hook"] == "read_indicator"
    write_operation = indicator_entry["write"]
    assert registry.delete_hook("write_indicator")
    assert "hook" not in write_operation
    assert write_operation["enabled"] is False
    window.controller.undo_stack.undo()
    assert write_operation["hook"] == "write_indicator"
    assert "enabled" not in write_operation

    window.about_action.trigger()
    assert window.content_stack.currentWidget() is window.about_page
    assert window.output_tabs.isHidden()
    assert window.about_page.version_info.version.startswith(BASE_VERSION)
    assert window.about_page.check_button.isEnabled()
    assert not window.about_page.download_button.isEnabled()
    assert not window.about_page.install_button.isEnabled()
    assert window.about_page.update_status.text() == "尚未检查更新"
    window.about_page.copy_version_info()
    assert window.about_page.version_info.version in qapp.clipboard().text()

    window.object_tree.setCurrentItem(window.object_tree.topLevelItem(4))

    assert window.entry_model.data(window.entry_model.index(0, 5)) == "读写"
    assert window.entry_model.data(window.entry_model.index(0, 6)) == "标量"
    assert window.entry_editor.access.currentText() == "读写"
    assert window.entry_editor.access.currentData() == "read_write"
    assert window.entry_editor.kind.currentText() == "标量"
    assert window.entry_editor.kind.currentData() == "scalar"
    assert "单个变量" in window.entry_editor.kind_description.text()
    assert window.entry_editor.validation_group.isVisible()
    assert not window.entry_editor.buffer_group.isVisible()
    assert not window.entry_editor.business_section.content.isVisible()
    assert window.entry_editor.error_banner.isHidden()
    window.entry_editor.read_source.clear()
    window.entry_editor.read_source.editingFinished.emit()
    assert window.entry_editor.error_banner.isVisible()
    assert "读取变量不能为空" in window.entry_editor.error_banner.text()
    window.controller.undo_stack.undo()
    assert window.entry_editor.error_banner.isHidden()
    write_u8_action = next(
        action for action in window.entry_editor.write_commands.menu().actions()
        if action.text() == "write_u8"
    )
    write_u8_action.setChecked(True)
    assert "write_u8" in window.controller.document.objects[0]["entries"][0]["write"]["commands"]
    window.controller.undo_stack.undo()
    assert window.entry_editor.requirement_ref.text() == "DEMO-REQ-001"
    window.entry_editor.owner.setText("display-team")
    window.entry_editor.owner.editingFinished.emit()
    assert window.controller.document.objects[0]["entries"][0]["business"]["owner"] == "display-team"
    window.entry_editor.validation_maximum.setText("3")
    window.entry_editor.validation_maximum.editingFinished.emit()
    assert window.controller.document.objects[0]["entries"][0]["write"]["validation"]["maximum"] == 3
    window.controller.undo_stack.undo()
    window.controller.undo_stack.undo()

    original_description = window.controller.document.objects[0]["entries"][0]["description"]
    window.entry_editor.raw_yaml.setPlainText(
        "subindex: 1\nname: temporary_entry\ndescription: YAML 编辑测试\nenabled: false\n"
    )
    window.entry_editor.apply_yaml_button.click()
    assert window.controller.document.objects[0]["entries"][0]["description"] == "YAML 编辑测试"
    window.controller.undo_stack.undo()
    assert window.controller.document.objects[0]["entries"][0]["description"] == original_description

    window.entry_editor.set_entry(indicator_entry)
    assert not window.entry_editor.validation_group.isVisible()
    assert window.entry_editor.read_hook.findData("read_indicator") >= 0
    assert window.entry_editor.read_hook.findData("write_indicator") < 0
    assert window.entry_editor.write_hook.findData("write_indicator") >= 0
    hook_inputs = iter((("created_read_hook", True), ("Demo_CreatedReadHook", True)))
    monkeypatch.setattr(QInputDialog, "getText", lambda *args, **kwargs: next(hook_inputs))
    window.entry_editor._prompt_create_hook("read", "read", window.entry_editor.read_hook)
    assert indicator_entry["read"]["hook"] == "created_read_hook"
    assert window.controller.document.data["hooks"]["created_read_hook"]["contract"] == "read"
    window.controller.undo_stack.undo()
    assert indicator_entry["read"]["hook"] == "read_indicator"

    action_entry = window.controller.document.objects[3]["entries"][0]
    window.entry_editor.set_entry(action_entry)
    assert window.entry_editor.authorization_field.isVisible()
    assert window.entry_editor.authorization_value.text() == "0xA5A55A5A"
    window.entry_editor.authorization_decimal.click()
    assert window.entry_editor.authorization_value.text() == str(0xA5A55A5A)
    window.entry_editor.authorization_value.setText("123456")
    window.entry_editor.authorization_value.editingFinished.emit()
    assert action_entry["write"]["authorization"]["value"] == 123456
    window.controller.undo_stack.undo()
    window.entry_editor.authorization_hex.click()
    assert window.entry_editor.authorization_value.text() == "0xA5A55A5A"
    window.entry_editor.set_entry(window.controller.document.objects[0]["entries"][0])

    window.search_edit.setText("brightness")
    assert window.entry_proxy.rowCount() == 1
    window.search_edit.clear()
    assert window.entry_proxy.rowCount() == 3

    enabled_index = window.entry_model.index(0, 0)
    assert window.entry_model.setData(enabled_index, Qt.Unchecked, Qt.CheckStateRole)
    assert window.controller.document.objects[0]["entries"][0]["enabled"] is False

    window.controller.undo_stack.undo()
    assert window.controller.document.objects[0]["entries"][0]["enabled"] is True

    window.add_entry()
    assert window.entry_model.rowCount() == 4
    added = window.controller.document.objects[0]["entries"][-1]
    assert "status" not in added
    assert added["enabled"] is False
    assert added["kind"] == "scalar"
    assert added["access"] == "read_write"
    assert added["read"]["source"] == "TODO_value"

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    window.delete_entry()
    assert window.entry_model.rowCount() == 3

    window.controller.undo_stack.undo()
    assert window.entry_model.rowCount() == 4
    window.controller.mark_clean()
