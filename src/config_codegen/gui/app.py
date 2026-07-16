from __future__ import annotations

import argparse
from pathlib import Path
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from config_codegen.document import ProtocolDocument
from config_codegen.errors import ConfigError
from config_codegen.gui.main_window import MainWindow
from config_codegen.gui.theme import apply_theme
from config_codegen.version import get_version


def _default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config" / "protocol.example.yaml"
    working_copy = Path.cwd() / "config" / "protocol.example.yaml"
    if working_copy.exists():
        return working_copy
    return Path(__file__).resolve().parents[3] / "config" / "protocol.example.yaml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Graphical protocol configuration editor")
    parser.add_argument("--version", action="version", version=get_version())
    parser.add_argument(
        "config",
        nargs="?",
        type=Path,
        default=_default_config_path(),
        help="YAML configuration to open",
    )
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
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
        if args.smoke_test:
            print(str(exc), file=sys.stderr)
            return 2
        QMessageBox.critical(None, "配置打开失败", str(exc))
        return 2
    window = MainWindow(document)
    if args.smoke_test:
        application.processEvents()
        valid = window._last_preview.valid
        window.close()
        return 0 if valid else 3
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
