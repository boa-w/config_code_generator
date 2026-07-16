from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, QTimer, Qt
from PySide6.QtGui import QAction, QBrush, QCloseEvent, QColor, QFontDatabase
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHeaderView,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QStackedWidget,
    QStyle,
    QTabWidget,
    QTableView,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
)
from ruamel.yaml.comments import CommentedMap

from config_codegen.csv_io import export_csv, import_csv
from config_codegen.document import ProtocolDocument, format_number
from config_codegen.errors import ConfigError
from config_codegen.generator import generate
from config_codegen.gui.controller import DocumentController
from config_codegen.gui.models.entry_table_model import EntryTableModel
from config_codegen.gui.widgets.about_page import AboutPage
from config_codegen.gui.widgets.basic_config_editor import BasicConfigEditor
from config_codegen.gui.widgets.entry_editor import EntryEditor
from config_codegen.preview import PreviewResult, validate_and_preview


class MainWindow(QMainWindow):
    def __init__(self, document: ProtocolDocument) -> None:
        super().__init__()
        self.settings = QSettings("ConfigCodeGenerator", "ProtocolEditor")
        self.controller = DocumentController(document, self)
        self.selected_object: CommentedMap | None = None
        self._tree_refreshing = False
        self._last_preview = PreviewResult(False, (), "", "")

        self.setWindowTitle("协议配置管理")
        self.setMinimumSize(1024, 640)
        self.resize(1360, 820)
        self._build_toolbar()
        self._build_workspace()

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(250)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.controller.changed.connect(self._document_changed)
        self.controller.structure_changed.connect(self._structure_changed)
        self.controller.undo_stack.cleanChanged.connect(self._update_title)

        self.refresh_tree()
        self.controller.mark_clean()
        self.refresh_preview()
        geometry = self.settings.value("mainWindowGeometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主工具栏", self)
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)

        open_action = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "打开", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_document)
        toolbar.addAction(open_action)

        save_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "保存", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_document)
        toolbar.addAction(save_action)

        self.basic_config_action = QAction(
            self.style().standardIcon(QStyle.SP_FileDialogDetailedView), "基础配置", self
        )
        self.basic_config_action.setShortcut("Ctrl+,")
        self.basic_config_action.setToolTip("基础配置 (Ctrl+,)")
        self.basic_config_action.triggered.connect(self.show_basic_config)
        toolbar.addAction(self.basic_config_action)
        toolbar.addSeparator()

        undo_action = self.controller.undo_stack.createUndoAction(self, "撤销")
        undo_action.setShortcut("Ctrl+Z")
        undo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        toolbar.addAction(undo_action)
        redo_action = self.controller.undo_stack.createRedoAction(self, "重做")
        redo_action.setShortcut("Ctrl+Shift+Z")
        redo_action.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        toolbar.addAction(redo_action)
        toolbar.addSeparator()

        self.add_entry_action = QAction(self.style().standardIcon(QStyle.SP_FileIcon), "新增条目", self)
        self.add_entry_action.setShortcut("Insert")
        self.add_entry_action.triggered.connect(self.add_entry)
        toolbar.addAction(self.add_entry_action)

        self.delete_entry_action = QAction(self.style().standardIcon(QStyle.SP_TrashIcon), "删除条目", self)
        self.delete_entry_action.setShortcut("Delete")
        self.delete_entry_action.triggered.connect(self.delete_entry)
        toolbar.addAction(self.delete_entry_action)
        toolbar.addSeparator()

        import_action = QAction(self.style().standardIcon(QStyle.SP_DialogOpenButton), "导入 CSV", self)
        import_action.triggered.connect(self.import_csv_file)
        toolbar.addAction(import_action)

        export_action = QAction(self.style().standardIcon(QStyle.SP_DialogSaveButton), "导出 CSV", self)
        export_action.triggered.connect(self.export_csv_file)
        toolbar.addAction(export_action)
        toolbar.addSeparator()

        validate_action = QAction(self.style().standardIcon(QStyle.SP_DialogApplyButton), "校验", self)
        validate_action.setShortcut("F6")
        validate_action.triggered.connect(self.refresh_preview)
        toolbar.addAction(validate_action)

        generate_action = QAction(self.style().standardIcon(QStyle.SP_ArrowDown), "生成", self)
        generate_action.setShortcut("F7")
        generate_action.triggered.connect(self.generate_fragment)
        toolbar.addAction(generate_action)
        toolbar.addSeparator()

        self.about_action = QAction(
            self.style().standardIcon(QStyle.SP_MessageBoxInformation), "关于", self
        )
        self.about_action.setShortcut("F1")
        self.about_action.triggered.connect(self.show_about)
        toolbar.addAction(self.about_action)

    def _build_workspace(self) -> None:
        self.object_tree = QTreeWidget()
        self.object_tree.setHeaderLabels(["配置导航", "条目"])
        self.object_tree.setRootIsDecorated(False)
        self.object_tree.setAlternatingRowColors(True)
        self.object_tree.setMinimumWidth(220)
        self.object_tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.object_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.object_tree.itemSelectionChanged.connect(self._object_selected)
        self.object_tree.itemChanged.connect(self._object_toggled)

        self.entry_model = EntryTableModel(self.controller, self)
        self.entry_table = QTableView()
        self.entry_table.setModel(self.entry_model)
        self.entry_table.setAlternatingRowColors(True)
        self.entry_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.entry_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.entry_table.verticalHeader().setVisible(False)
        self.entry_table.horizontalHeader().setStretchLastSection(False)
        self.entry_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.entry_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.entry_table.selectionModel().selectionChanged.connect(self._entry_selected)

        fixed_font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self.issue_list = QListWidget()
        self.code_preview = QPlainTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(fixed_font)
        self.diff_preview = QPlainTextEdit()
        self.diff_preview.setReadOnly(True)
        self.diff_preview.setFont(fixed_font)

        self.output_tabs = QTabWidget()
        self.output_tabs.addTab(self.issue_list, "校验问题")
        self.output_tabs.addTab(self.code_preview, "代码预览")
        self.output_tabs.addTab(self.diff_preview, "Diff")

        self.basic_editor = BasicConfigEditor(self.controller)
        self.about_page = AboutPage()
        self.entry_editor = EntryEditor(self.controller)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(self.entry_table)
        self.content_stack.addWidget(self.basic_editor)
        self.content_stack.addWidget(self.about_page)
        self.content_stack.setCurrentWidget(self.entry_table)

        middle = QSplitter(Qt.Vertical)
        middle.addWidget(self.content_stack)
        middle.addWidget(self.output_tabs)
        middle.setStretchFactor(0, 3)
        middle.setStretchFactor(1, 2)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.object_tree)
        main_splitter.addWidget(middle)
        main_splitter.addWidget(self.entry_editor)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        main_splitter.setSizes([230, 820, 310])
        self.setCentralWidget(main_splitter)

    def refresh_tree(self) -> None:
        self._tree_refreshing = True
        try:
            selected = self.selected_object
            self.object_tree.clear()
            selected_item: QTreeWidgetItem | None = None
            basic_item = QTreeWidgetItem(["基础配置  /  代码引用", ""])
            basic_item.setData(0, Qt.UserRole, "__basic_config__")
            basic_item.setIcon(0, self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
            basic_font = basic_item.font(0)
            basic_font.setBold(True)
            basic_item.setFont(0, basic_font)
            basic_item.setBackground(0, QBrush(QColor("#36515A")))
            basic_item.setForeground(0, QBrush(QColor("#FFFFFF")))
            basic_item.setToolTip(0, "项目级代码生成配置")
            self.object_tree.addTopLevelItem(basic_item)
            self.object_tree.setFirstColumnSpanned(0, QModelIndex(), True)
            for object_node in self.controller.document.objects:
                index = format_number(object_node.get("index"), 4)
                name = object_node.get("description", object_node.get("name", ""))
                count = len(self.controller.document.entries(object_node))
                item = QTreeWidgetItem([f"{index}  {name}", str(count)])
                item.setData(0, Qt.UserRole, object_node)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked if object_node.get("enabled", True) else Qt.Unchecked)
                self.object_tree.addTopLevelItem(item)
                if object_node is selected:
                    selected_item = item
            about_item = QTreeWidgetItem(["关于  /  版本信息", ""])
            about_item.setData(0, Qt.UserRole, "__about__")
            about_item.setIcon(0, self.style().standardIcon(QStyle.SP_MessageBoxInformation))
            about_font = about_item.font(0)
            about_font.setBold(True)
            about_item.setFont(0, about_font)
            about_item.setToolTip(0, "版本和构建信息")
            self.object_tree.addTopLevelItem(about_item)
            if selected_item is None and self.object_tree.topLevelItemCount() > 1:
                selected_item = self.object_tree.topLevelItem(1)
            if selected_item is not None:
                self.object_tree.setCurrentItem(selected_item)
        finally:
            self._tree_refreshing = False

    def _object_selected(self) -> None:
        items = self.object_tree.selectedItems()
        selected = items[0].data(0, Qt.UserRole) if items else None
        if selected == "__basic_config__":
            self.selected_object = None
            self.entry_model.set_object(None)
            self.entry_editor.set_entry(None)
            self.content_stack.setCurrentWidget(self.basic_editor)
            self.output_tabs.show()
            self.entry_editor.hide()
            self.add_entry_action.setEnabled(False)
            self.delete_entry_action.setEnabled(False)
            return
        if selected == "__about__":
            self.selected_object = None
            self.entry_model.set_object(None)
            self.entry_editor.set_entry(None)
            self.content_stack.setCurrentWidget(self.about_page)
            self.output_tabs.hide()
            self.entry_editor.hide()
            self.add_entry_action.setEnabled(False)
            self.delete_entry_action.setEnabled(False)
            return
        self.selected_object = selected
        self.content_stack.setCurrentWidget(self.entry_table)
        self.output_tabs.show()
        self.entry_editor.show()
        self.add_entry_action.setEnabled(self.selected_object is not None)
        self.delete_entry_action.setEnabled(self.selected_object is not None)
        self.entry_model.set_object(self.selected_object)
        self.entry_editor.set_entry(None)
        if self.entry_model.rowCount():
            self.entry_table.selectRow(0)

    def show_basic_config(self) -> None:
        if self.object_tree.topLevelItemCount():
            self.object_tree.setCurrentItem(self.object_tree.topLevelItem(0))

    def show_about(self) -> None:
        if self.object_tree.topLevelItemCount():
            self.object_tree.setCurrentItem(
                self.object_tree.topLevelItem(self.object_tree.topLevelItemCount() - 1)
            )

    def _object_toggled(self, item: QTreeWidgetItem, column: int) -> None:
        if self._tree_refreshing or column != 0:
            return
        object_node = item.data(0, Qt.UserRole)
        if isinstance(object_node, CommentedMap):
            self.controller.set_value(
                object_node,
                "enabled",
                item.checkState(0) == Qt.Checked,
                "切换对象",
            )

    def _entry_selected(self) -> None:
        rows = self.entry_table.selectionModel().selectedRows()
        entry = self.entry_model.entry_at(rows[0].row()) if rows else None
        self.entry_editor.set_entry(entry)

    def _selected_entry_row(self) -> int | None:
        rows = self.entry_table.selectionModel().selectedRows()
        return rows[0].row() if rows else None

    def _next_subindex(self) -> int:
        if self.selected_object is None:
            return 1
        occupied: set[int] = set()
        for entry in self.controller.document.entries(self.selected_object):
            subindex = entry.get("subindex")
            if isinstance(subindex, dict):
                occupied.update(range(int(subindex.get("from", 0)), int(subindex.get("to", -1)) + 1))
            elif isinstance(subindex, int):
                occupied.add(subindex)
        for candidate in range(1, 256):
            if candidate not in occupied:
                return candidate
        return 0

    def add_entry(self) -> None:
        if self.selected_object is None:
            QMessageBox.information(self, "无法新增", "请先选择一个 Index 对象。")
            return
        subindex = self._next_subindex()
        if subindex == 0:
            QMessageBox.warning(self, "无法新增", "当前 Index 已没有可用 SubIndex。")
            return
        index = int(self.selected_object.get("index", 0))
        entry = CommentedMap(
            {
                "subindex": subindex,
                "name": f"new_entry_{subindex:02x}",
                "description": "新协议条目",
                "protocol_ref": f"0x{index:04X}:{subindex:02X}",
                "status": "planned",
                "enabled": False,
            }
        )
        entries = self.controller.document.entries(self.selected_object)
        row = len(entries)
        self.controller.insert_item(entries, row, entry, "新增协议条目")
        self.entry_table.selectRow(row)
        self.entry_table.scrollTo(self.entry_model.index(row, 0))

    def delete_entry(self) -> None:
        if self.selected_object is None:
            return
        row = self._selected_entry_row()
        entry = self.entry_model.entry_at(row) if row is not None else None
        if row is None or entry is None:
            QMessageBox.information(self, "无法删除", "请先选择一个协议条目。")
            return
        description = entry.get("description", entry.get("name", ""))
        if QMessageBox.question(
            self,
            "删除协议条目",
            f"确定删除“{description}”吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        entries = self.controller.document.entries(self.selected_object)
        self.controller.remove_item(entries, row, "删除协议条目")
        if self.entry_model.rowCount():
            self.entry_table.selectRow(min(row, self.entry_model.rowCount() - 1))

    def export_csv_file(self) -> None:
        suggested = self.controller.document.path.with_suffix(".csv")
        filename, _ = QFileDialog.getSaveFileName(self, "导出协议 CSV", str(suggested), "CSV (*.csv)")
        if not filename:
            return
        try:
            path = export_csv(self.controller.document, filename)
            self.statusBar().showMessage(f"已导出 {path}", 5000)
        except (ConfigError, OSError) as exc:
            QMessageBox.critical(self, "导出失败", str(exc))

    def import_csv_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "导入协议 CSV", str(self.controller.document.path.parent), "CSV (*.csv)")
        if not filename:
            return
        try:
            objects = import_csv(filename)
            candidate = self.controller.document.clone_with_objects(objects)
            result = validate_and_preview(candidate)
            if not result.valid:
                raise ConfigError("\n".join(result.issues))
        except (ConfigError, OSError) as exc:
            QMessageBox.critical(self, "导入失败", str(exc))
            return
        if QMessageBox.question(
            self,
            "导入协议 CSV",
            "导入将替换当前对象和条目清单，其他协议配置保持不变。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        self.selected_object = None
        self.controller.replace_objects(objects)
        self.statusBar().showMessage(f"已导入 {filename}，可使用撤销恢复", 5000)

    def _document_changed(self) -> None:
        self._sync_tree_checks()
        self.preview_timer.start()
        self._update_title()

    def _structure_changed(self) -> None:
        self.refresh_tree()

    def _sync_tree_checks(self) -> None:
        self._tree_refreshing = True
        try:
            for position in range(self.object_tree.topLevelItemCount()):
                item = self.object_tree.topLevelItem(position)
                object_node = item.data(0, Qt.UserRole)
                if isinstance(object_node, CommentedMap):
                    item.setCheckState(0, Qt.Checked if object_node.get("enabled", True) else Qt.Unchecked)
        finally:
            self._tree_refreshing = False

    def _update_title(self) -> None:
        marker = " *" if not self.controller.undo_stack.isClean() else ""
        self.setWindowTitle(f"协议配置管理 - {self.controller.document.path.name}{marker}")

    def refresh_preview(self) -> None:
        self._last_preview = validate_and_preview(self.controller.document)
        self.issue_list.clear()
        if self._last_preview.valid:
            self.issue_list.addItem("配置有效")
            self.statusBar().showMessage("配置有效", 3000)
        else:
            self.issue_list.addItems(self._last_preview.issues)
            self.output_tabs.setCurrentWidget(self.issue_list)
            self.statusBar().showMessage("配置校验失败")
        self.code_preview.setPlainText(self._last_preview.fragment)
        self.diff_preview.setPlainText(self._last_preview.diff or "无差异")

    def _confirm_discard(self) -> bool:
        if self.controller.undo_stack.isClean():
            return True
        result = QMessageBox.warning(
            self,
            "未保存修改",
            "当前配置尚未保存。",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if result == QMessageBox.Save:
            return self.save_document()
        return result == QMessageBox.Discard

    def open_document(self) -> None:
        if not self._confirm_discard():
            return
        filename, _ = QFileDialog.getOpenFileName(self, "打开协议配置", str(self.controller.document.path.parent), "YAML (*.yaml *.yml)")
        if not filename:
            return
        try:
            self.controller.document = ProtocolDocument.load(filename)
            self.controller.undo_stack.clear()
            self.selected_object = None
            self.refresh_tree()
            self.basic_editor.refresh()
            self.controller.mark_clean()
            self.refresh_preview()
        except ConfigError as exc:
            QMessageBox.critical(self, "打开失败", str(exc))

    def save_document(self) -> bool:
        try:
            self.controller.document.save()
            self.controller.mark_clean()
            self.statusBar().showMessage(f"已保存 {self.controller.document.path}", 4000)
            return True
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))
            return False

    def generate_fragment(self) -> None:
        self.refresh_preview()
        if not self._last_preview.valid:
            QMessageBox.warning(self, "无法生成", "请先修复配置校验问题。")
            return
        if not self.save_document():
            return
        try:
            path = generate(self.controller.document.path)
            self.statusBar().showMessage(f"已生成 {path}", 5000)
            self.refresh_preview()
            self.output_tabs.setCurrentWidget(self.code_preview)
        except (ConfigError, OSError) as exc:
            QMessageBox.critical(self, "生成失败", str(exc))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_discard():
            event.ignore()
            return
        self.settings.setValue("mainWindowGeometry", self.saveGeometry())
        event.accept()
