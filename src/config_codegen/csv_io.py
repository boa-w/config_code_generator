from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarint import HexInt

from .document import ProtocolDocument, format_number
from .errors import ConfigError


COLUMNS = (
    "object_index",
    "object_name",
    "object_description",
    "object_enabled",
    "subindex_from",
    "subindex_to",
    "name",
    "description",
    "protocol_ref",
    "status",
    "enabled",
    "kind",
    "access",
    "read_json",
    "write_json",
    "fields_json",
    "buffer_json",
    "business_json",
    "implementation_json",
)

REQUIRED_COLUMNS = COLUMNS[:-2]


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _json_cell(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(_plain(value), ensure_ascii=False, separators=(",", ":"))


def _parse_int(value: str, field: str, row: int) -> int:
    try:
        return int(value.strip(), 0)
    except ValueError as exc:
        raise ConfigError(f"CSV row {row}: {field} has invalid integer {value!r}") from exc


def _parse_bool(value: str, field: str, row: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ConfigError(f"CSV row {row}: {field} must be true or false")


def _parse_json(value: str, field: str, row: int, expected: type) -> Any:
    if not value.strip():
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ConfigError(f"CSV row {row}: {field} contains invalid JSON: {exc.msg}") from exc
    if not isinstance(parsed, expected):
        raise ConfigError(f"CSV row {row}: {field} must contain a JSON {expected.__name__}")
    return parsed


def export_csv(document: ProtocolDocument, path: str | Path) -> Path:
    destination = Path(path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        for object_node in document.objects:
            for entry in document.entries(object_node):
                subindex = entry.get("subindex")
                if isinstance(subindex, dict):
                    subindex_from = format_number(subindex.get("from"))
                    subindex_to = format_number(subindex.get("to"))
                else:
                    subindex_from = format_number(subindex)
                    subindex_to = ""
                writer.writerow(
                    {
                        "object_index": format_number(object_node.get("index"), 4),
                        "object_name": object_node.get("name", ""),
                        "object_description": object_node.get("description", ""),
                        "object_enabled": str(bool(object_node.get("enabled", True))).lower(),
                        "subindex_from": subindex_from,
                        "subindex_to": subindex_to,
                        "name": entry.get("name", ""),
                        "description": entry.get("description", ""),
                        "protocol_ref": entry.get("protocol_ref", ""),
                        "status": entry.get("status", ""),
                        "enabled": str(bool(entry.get("enabled", True))).lower(),
                        "kind": entry.get("kind", ""),
                        "access": entry.get("access", ""),
                        "read_json": _json_cell(entry.get("read")),
                        "write_json": _json_cell(entry.get("write")),
                        "fields_json": _json_cell(entry.get("fields")),
                        "buffer_json": _json_cell(entry.get("buffer")),
                        "business_json": _json_cell(entry.get("business")),
                        "implementation_json": _json_cell(entry.get("implementation")),
                    }
                )
    return destination


def import_csv(path: str | Path) -> CommentedSeq:
    source = Path(path).resolve()
    try:
        stream = source.open("r", encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ConfigError(f"cannot open CSV {source}: {exc}") from exc
    with stream:
        reader = csv.DictReader(stream)
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ConfigError(f"CSV is missing columns: {', '.join(missing)}")
        objects = CommentedSeq()
        by_index: dict[int, CommentedMap] = {}
        seen_entries: set[tuple[int, int, int]] = set()
        for row_number, row in enumerate(reader, start=2):
            if not any((value or "").strip() for value in row.values()):
                continue
            index = _parse_int(row["object_index"], "object_index", row_number)
            first = _parse_int(row["subindex_from"], "subindex_from", row_number)
            last = _parse_int(row["subindex_to"], "subindex_to", row_number) if row["subindex_to"].strip() else first
            if not 0 <= index <= 0xFFFF or not 0 <= first <= last <= 0xFF:
                raise ConfigError(f"CSV row {row_number}: index or subindex is out of range")
            identity = (index, first, last)
            if identity in seen_entries:
                raise ConfigError(f"CSV row {row_number}: duplicate entry 0x{index:04X}:{first}-{last}")
            seen_entries.add(identity)

            object_node = by_index.get(index)
            if object_node is None:
                object_enabled = _parse_bool(row["object_enabled"], "object_enabled", row_number)
                object_node = CommentedMap(
                    {
                        "index": HexInt(index),
                        "name": row["object_name"].strip(),
                        "description": row["object_description"].strip(),
                        "enabled": object_enabled,
                        "entries": CommentedSeq(),
                    }
                )
                objects.append(object_node)
                by_index[index] = object_node
            else:
                repeated = (
                    row["object_name"].strip(),
                    row["object_description"].strip(),
                    _parse_bool(row["object_enabled"], "object_enabled", row_number),
                )
                expected = (
                    object_node.get("name", ""),
                    object_node.get("description", ""),
                    bool(object_node.get("enabled", True)),
                )
                if repeated != expected:
                    raise ConfigError(
                        f"CSV row {row_number}: repeated object 0x{index:04X} metadata is inconsistent"
                    )

            entry = CommentedMap()
            entry["subindex"] = first if first == last else CommentedMap({"from": first, "to": last})
            for key in ("name", "description", "protocol_ref", "status"):
                value = row[key].strip()
                if value:
                    entry[key] = value
            entry["enabled"] = _parse_bool(row["enabled"], "enabled", row_number)
            for key in ("kind", "access"):
                value = row[key].strip()
                if value:
                    entry[key] = value
            for column, key, expected in (
                ("read_json", "read", dict),
                ("write_json", "write", dict),
                ("fields_json", "fields", list),
                ("buffer_json", "buffer", dict),
                ("business_json", "business", dict),
                ("implementation_json", "implementation", dict),
            ):
                value = _parse_json(row.get(column, ""), column, row_number, expected)
                if value is not None:
                    entry[key] = value
            object_node["entries"].append(entry)

    if not objects:
        raise ConfigError("CSV contains no protocol entries")
    return objects
