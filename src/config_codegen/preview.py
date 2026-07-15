from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
import tempfile

from .document import ProtocolDocument
from .errors import ConfigError
from .generator import generate
from .models import load_config


@dataclass(frozen=True)
class PreviewResult:
    valid: bool
    issues: tuple[str, ...]
    fragment: str
    diff: str


def validate_and_preview(document: ProtocolDocument) -> PreviewResult:
    try:
        with tempfile.TemporaryDirectory(prefix="cfggen-preview-") as temporary:
            root = Path(temporary)
            config_path = root / document.path.name
            config_path.write_text(document.dumps(), encoding="utf-8", newline="\n")
            config = load_config(config_path)
            fragment_path = generate(config_path, root)
            fragment = fragment_path.read_text(encoding="utf-8")
            current_path = document.path.parent.parent / config.fragment_path
            current = current_path.read_text(encoding="utf-8") if current_path.exists() else ""
            diff = "".join(
                unified_diff(
                    current.splitlines(keepends=True),
                    fragment.splitlines(keepends=True),
                    fromfile=str(current_path),
                    tofile="preview",
                )
            )
            return PreviewResult(True, (), fragment, diff)
    except (ConfigError, OSError, ValueError) as exc:
        return PreviewResult(False, (str(exc),), "", "")
