from pathlib import Path
import shutil

from config_codegen.document import ProtocolDocument
from config_codegen.models import load_config
from config_codegen.preview import validate_and_preview


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "config" / "protocol.example.yaml"


def test_round_trip_save_preserves_comments_and_valid_config(tmp_path: Path) -> None:
    path = tmp_path / "protocol.yaml"
    shutil.copyfile(SAMPLE, path)
    document = ProtocolDocument.load(path)
    first_entry = document.objects[0]["entries"][0]
    first_entry["enabled"] = False

    document.save()

    saved = path.read_text(encoding="utf-8")
    assert "# Public demonstration configuration." in saved
    assert "enabled: false" in saved
    assert sum(entry.enabled for entry in load_config(path).entries) == 12


def test_preview_uses_unsaved_document_state(tmp_path: Path) -> None:
    path = tmp_path / "config" / "protocol.yaml"
    path.parent.mkdir()
    shutil.copyfile(SAMPLE, path)
    document = ProtocolDocument.load(path)
    document.objects[0]["entries"][0]["enabled"] = False

    result = validate_and_preview(document)

    assert result.valid
    assert "[DEMO-SET-01]" not in result.fragment
