from __future__ import annotations

from dataclasses import dataclass
from difflib import unified_diff
from pathlib import Path
import tempfile

from .document import ProtocolDocument
from .errors import ConfigError
from .generator import generate_outputs
from .models import load_config


@dataclass(frozen=True)
class PreviewResult:
    valid: bool
    issues: tuple[str, ...]
    fragment: str
    diff: str
    hook_fragment: str = ""


def validate_and_preview(document: ProtocolDocument) -> PreviewResult:
    try:
        with tempfile.TemporaryDirectory(prefix="cfggen-preview-") as temporary:
            root = Path(temporary)
            config_path = root / document.path.name
            config_path.write_text(document.dumps(), encoding="utf-8", newline="\n")
            config = load_config(config_path)
            fragment_path, hook_path = generate_outputs(config_path, root)
            fragment = fragment_path.read_text(encoding="utf-8")
            current_path = document.path.parent.parent / config.fragment_path
            current = current_path.read_text(encoding="utf-8") if current_path.exists() else ""
            switch_diff = "".join(
                unified_diff(
                    current.splitlines(keepends=True),
                    fragment.splitlines(keepends=True),
                    fromfile=str(current_path),
                    tofile="preview",
                )
            )
            hook_fragment = hook_path.read_text(encoding="utf-8") if hook_path else ""
            hook_diff = ""
            if config.hook_fragment_path is not None and hook_path is not None:
                current_hook_path = document.path.parent.parent / config.hook_fragment_path
                current_hook = (
                    current_hook_path.read_text(encoding="utf-8")
                    if current_hook_path.exists()
                    else ""
                )
                hook_diff = "".join(
                    unified_diff(
                        current_hook.splitlines(keepends=True),
                        hook_fragment.splitlines(keepends=True),
                        fromfile=str(current_hook_path),
                        tofile="hook-preview",
                    )
                )
            return PreviewResult(
                True,
                (),
                fragment,
                switch_diff + ("\n" if switch_diff and hook_diff else "") + hook_diff,
                hook_fragment,
            )
    except (ConfigError, OSError, ValueError) as exc:
        return PreviewResult(False, (str(exc),), "", "")
