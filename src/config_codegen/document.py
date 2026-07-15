from __future__ import annotations

from io import StringIO
from pathlib import Path
from copy import deepcopy
import os
import tempfile
from typing import Any, Iterator

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from .errors import ConfigError


def format_number(value: Any, width: int = 0) -> str:
    if isinstance(value, int):
        return f"0x{value:0{width}X}" if width else str(value)
    return str(value)


def format_subindex(value: Any) -> str:
    if isinstance(value, dict):
        return f"{format_number(value.get('from'))}-{format_number(value.get('to'))}"
    return format_number(value)


class ProtocolDocument:
    """Round-trip YAML document used by the GUI editing layer."""

    def __init__(self, path: Path, data: CommentedMap, yaml: YAML) -> None:
        self.path = path
        self.data = data
        self._yaml = yaml

    @classmethod
    def load(cls, path: str | Path) -> "ProtocolDocument":
        source = Path(path).resolve()
        yaml = YAML(typ="rt")
        yaml.preserve_quotes = True
        yaml.indent(mapping=2, sequence=4, offset=2)
        try:
            with source.open("r", encoding="utf-8") as stream:
                data = yaml.load(stream)
        except OSError as exc:
            raise ConfigError(f"cannot load {source}: {exc}") from exc
        if not isinstance(data, CommentedMap):
            raise ConfigError("configuration root must be a mapping")
        return cls(source, data, yaml)

    @property
    def objects(self) -> CommentedSeq:
        objects = self.data.get("objects")
        if not isinstance(objects, CommentedSeq):
            raise ConfigError("objects: expected a list")
        return objects

    def entries(self, object_node: CommentedMap) -> CommentedSeq:
        entries = object_node.get("entries")
        if not isinstance(entries, CommentedSeq):
            raise ConfigError("object entries: expected a list")
        return entries

    def iter_entries(self) -> Iterator[tuple[CommentedMap, CommentedMap]]:
        for object_node in self.objects:
            for entry in self.entries(object_node):
                yield object_node, entry

    def dumps(self) -> str:
        buffer = StringIO()
        self._yaml.dump(self.data, buffer)
        return buffer.getvalue()

    def dump_node(self, node: Any) -> str:
        buffer = StringIO()
        self._yaml.dump(node, buffer)
        return buffer.getvalue()

    def clone_with_objects(self, objects: CommentedSeq) -> "ProtocolDocument":
        data = deepcopy(self.data)
        data["objects"] = deepcopy(objects)
        return ProtocolDocument(self.path, data, self._yaml)

    def save(self, path: str | Path | None = None) -> Path:
        destination = Path(path).resolve() if path else self.path
        destination.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
        )
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(self.dumps())
            os.replace(temporary_name, destination)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        self.path = destination
        return destination
