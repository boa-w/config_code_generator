from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


def apply_theme(application: QApplication) -> None:
    application.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#EEF1F2"))
    palette.setColor(QPalette.WindowText, QColor("#182126"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F3F6F7"))
    palette.setColor(QPalette.ToolTipBase, QColor("#202B31"))
    palette.setColor(QPalette.ToolTipText, QColor("#F7FAFB"))
    palette.setColor(QPalette.Text, QColor("#182126"))
    palette.setColor(QPalette.Button, QColor("#E4E9EB"))
    palette.setColor(QPalette.ButtonText, QColor("#182126"))
    palette.setColor(QPalette.Highlight, QColor("#28717A"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.PlaceholderText, QColor("#77848A"))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#7E898E"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#7E898E"))
    application.setPalette(palette)
    application.setStyleSheet(
        """
        QMainWindow, QWidget {
            background-color: #EEF1F2;
            color: #182126;
        }
        QToolBar {
            background-color: #F7F8F8;
            border: 0;
            border-bottom: 1px solid #C7D0D4;
            spacing: 4px;
            padding: 4px 6px;
        }
        QToolButton {
            background-color: transparent;
            color: #182126;
            border: 1px solid transparent;
            padding: 5px 8px;
        }
        QToolButton:hover {
            background-color: #E1EAEC;
            border-color: #A9BBC0;
        }
        QToolButton:pressed {
            background-color: #CBDADD;
        }
        QToolButton#radixButton {
            background-color: #E4E9EB;
            color: #334147;
            border: 1px solid #AAB8BD;
            padding: 4px 7px;
        }
        QToolButton#radixButton:checked {
            background-color: #28717A;
            color: #FFFFFF;
            border-color: #205E66;
        }
        QToolButton:disabled {
            color: #899398;
        }
        QTreeWidget {
            background-color: #26343B;
            alternate-background-color: #2D3C44;
            color: #F1F5F6;
            border: 0;
            outline: 0;
        }
        QTreeWidget::item {
            color: #F1F5F6;
            min-height: 27px;
            padding: 2px 5px;
        }
        QTreeWidget::item:hover {
            background-color: #3A4D55;
        }
        QTreeWidget::item:selected {
            background-color: #28717A;
            color: #FFFFFF;
        }
        QTreeWidget QHeaderView::section {
            background-color: #1F2B31;
            color: #DDE6E8;
            border: 0;
            border-bottom: 1px solid #42545C;
            padding: 5px;
        }
        QTableView, QListWidget, QPlainTextEdit {
            background-color: #FFFFFF;
            alternate-background-color: #F3F6F7;
            color: #182126;
            border: 1px solid #B9C5C9;
            gridline-color: #D5DCDF;
            selection-background-color: #28717A;
            selection-color: #FFFFFF;
        }
        QHeaderView::section {
            background-color: #DCE4E6;
            color: #182126;
            border: 0;
            border-right: 1px solid #BEC9CD;
            border-bottom: 1px solid #AEBCC1;
            padding: 5px;
        }
        QLineEdit, QComboBox {
            background-color: #FFFFFF;
            color: #182126;
            border: 1px solid #AAB8BD;
            padding: 5px 7px;
            selection-background-color: #28717A;
            selection-color: #FFFFFF;
        }
        QLineEdit:focus, QComboBox:focus {
            border: 2px solid #28717A;
            padding: 4px 6px;
        }
        QLineEdit:disabled, QComboBox:disabled {
            background-color: #E4E8E9;
            color: #737E83;
        }
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            color: #182126;
            selection-background-color: #28717A;
            selection-color: #FFFFFF;
        }
        QTabWidget::pane {
            border: 1px solid #B9C5C9;
            background-color: #FFFFFF;
        }
        QTabBar::tab {
            background-color: #DCE3E5;
            color: #263238;
            border: 1px solid #B9C5C9;
            border-bottom: 0;
            padding: 6px 12px;
        }
        QTabBar::tab:selected {
            background-color: #FFFFFF;
            color: #174D54;
        }
        QSplitter::handle {
            background-color: #C5CED1;
        }
        QStatusBar {
            background-color: #26343B;
            color: #F1F5F6;
        }
        QCheckBox {
            color: #182126;
            spacing: 6px;
        }
        QLabel#kindDescription {
            color: #526168;
            padding: 3px 0;
        }
        QLabel#aboutVersion {
            color: #1F6670;
            font-size: 16px;
            font-weight: 600;
        }
        QLabel#entryErrorBanner {
            background-color: #F5DDDA;
            color: #70241F;
            border-left: 3px solid #B13A32;
            padding: 6px 8px;
        }
        QPushButton {
            background-color: #D7E3E5;
            color: #183138;
            border: 1px solid #9EB2B7;
            padding: 6px 12px;
        }
        QPushButton:hover {
            background-color: #C6DADD;
            border-color: #28717A;
        }
        QPushButton:pressed {
            background-color: #B5CDD1;
        }
        QToolTip {
            background-color: #202B31;
            color: #F7FAFB;
            border: 1px solid #53666E;
            padding: 4px;
        }
        """
    )
