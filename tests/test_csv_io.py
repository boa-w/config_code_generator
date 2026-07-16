from pathlib import Path
import csv
import shutil

import pytest

from config_codegen.csv_io import COLUMNS, export_csv, import_csv
from config_codegen.document import ProtocolDocument
from config_codegen.errors import ConfigError
from config_codegen.preview import validate_and_preview


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "config" / "protocol.example.yaml"


def test_csv_round_trip_preserves_logical_entries_and_nested_config(tmp_path: Path) -> None:
    config_path = tmp_path / "config" / "protocol.yaml"
    config_path.parent.mkdir()
    shutil.copyfile(SAMPLE, config_path)
    document = ProtocolDocument.load(config_path)
    csv_path = export_csv(document, tmp_path / "protocol.csv")

    assert csv_path.read_bytes().startswith(b"\xef\xbb\xbf")
    objects = import_csv(csv_path)
    candidate = document.clone_with_objects(objects)

    assert len(objects) == 5
    assert sum(len(obj["entries"]) for obj in objects) == 9
    assert objects[0]["entries"][0]["read"]["source"] == "g_demoLanguage"
    assert objects[4]["entries"][0]["fields"][0]["source"] == "g_demoYear"
    assert objects[1]["entries"][2]["write"]["hook"] == "write_indicator"
    assert objects[0]["entries"][0]["business"]["requirement_ref"] == "DEMO-REQ-001"
    assert objects[0]["entries"][0]["implementation"]["source_symbol"] == "g_demoLanguage"
    assert validate_and_preview(candidate).valid


def test_csv_import_rejects_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "invalid.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(column for column in COLUMNS if column != "read_json"))
        writer.writeheader()

    with pytest.raises(ConfigError, match="missing columns"):
        import_csv(path)


def test_csv_import_rejects_inconsistent_object_metadata(tmp_path: Path) -> None:
    document = ProtocolDocument.load(SAMPLE)
    path = export_csv(document, tmp_path / "protocol.csv")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    rows[1]["object_description"] = "different"
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ConfigError, match="metadata is inconsistent"):
        import_csv(path)
