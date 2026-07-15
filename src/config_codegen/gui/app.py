from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from config_codegen.document import ProtocolDocument
from config_codegen.errors import ConfigError
from config_codegen.gui.main_window import MainWindow
from config_codegen.gui.theme import apply_theme


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Graphical protocol configuration editor")
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=Path("config/protocol.example.yaml"),
        help="YAML configuration to open",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    application = QApplication(sys.argv[:1])
    application.setApplicationName("协议配置管理")
    application.setOrganizationName("ConfigCodeGenerator")
    apply_theme(application)
    try:
        document = ProtocolDocument.load(args.config)
    except ConfigError as exc:
        QMessageBox.critical(None, "配置打开失败", str(exc))
        return 2
    window = MainWindow(document)
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
