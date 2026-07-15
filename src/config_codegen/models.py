from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from .errors import ConfigError


_C_REFERENCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*$")
_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def as_int(value: Any, path: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{path}: boolean is not an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ConfigError(f"{path}: invalid integer {value!r}") from exc
    raise ConfigError(f"{path}: expected integer, got {type(value).__name__}")


def require_identifier(value: str, path: str) -> str:
    if not isinstance(value, str) or not _C_IDENTIFIER.fullmatch(value):
        raise ConfigError(f"{path}: invalid C identifier {value!r}")
    return value


def require_reference(value: str, path: str) -> str:
    if not isinstance(value, str) or not _C_REFERENCE.fullmatch(value):
        raise ConfigError(f"{path}: invalid C reference {value!r}")
    return value


@dataclass(frozen=True)
class Command:
    name: str
    request: int
    payload_width: int
    success_response: int | None


@dataclass(frozen=True)
class ExpandedEntry:
    index: int
    subindex: int
    object_name: str
    name: str
    description: str
    kind: str
    access: str
    enabled: bool
    raw: dict[str, Any]
    field: dict[str, Any] | None = None


@dataclass(frozen=True)
class GeneratorConfig:
    path: Path
    raw: dict[str, Any]
    fragment_path: Path
    command_reference: str
    index_reference: str
    subindex_reference: str
    data_reference: str
    response_can_id: int
    transmit_function: str
    read_command: int
    read_responses: dict[int, int]
    commands: dict[str, Command]
    error_command: int
    error_codes: dict[str, int]
    hooks: dict[str, str]
    entries: tuple[ExpandedEntry, ...]


def _expand_entries(raw: dict[str, Any]) -> tuple[ExpandedEntry, ...]:
    expanded: list[ExpandedEntry] = []
    seen: set[tuple[int, int]] = set()
    objects = raw.get("objects")
    if not isinstance(objects, list) or not objects:
        raise ConfigError("objects: expected a non-empty list")

    for object_pos, obj in enumerate(objects):
        base = f"objects[{object_pos}]"
        index = as_int(obj.get("index"), f"{base}.index")
        if not 0 <= index <= 0xFFFF:
            raise ConfigError(f"{base}.index: out of u16 range")
        object_name = require_identifier(obj.get("name"), f"{base}.name")
        object_enabled = bool(obj.get("enabled", True))
        entries = obj.get("entries")
        if not isinstance(entries, list):
            raise ConfigError(f"{base}.entries: expected list")

        for entry_pos, entry in enumerate(entries):
            entry_path = f"{base}.entries[{entry_pos}]"
            name = require_identifier(entry.get("name"), f"{entry_path}.name")
            enabled = object_enabled and bool(entry.get("enabled", True))
            kind = entry.get("kind", "unimplemented")
            access = entry.get("access", "none")
            if enabled and kind not in {"scalar", "bitfield", "hook", "action", "transaction_fields", "chunked_buffer"}:
                raise ConfigError(f"{entry_path}.kind: unsupported kind {kind!r}")
            if enabled and access not in {"read_only", "write_only", "read_write"}:
                raise ConfigError(f"{entry_path}.access: invalid access {access!r}")

            subindex_value = entry.get("subindex")
            if isinstance(subindex_value, dict):
                first = as_int(subindex_value.get("from"), f"{entry_path}.subindex.from")
                last = as_int(subindex_value.get("to"), f"{entry_path}.subindex.to")
            else:
                first = last = as_int(subindex_value, f"{entry_path}.subindex")
            if not 0 <= first <= last <= 0xFF:
                raise ConfigError(f"{entry_path}.subindex: invalid u8 range {first}..{last}")

            fields = {as_int(field.get("subindex"), f"{entry_path}.fields.subindex"): field for field in entry.get("fields", [])}
            for subindex in range(first, last + 1):
                key = (index, subindex)
                if key in seen:
                    raise ConfigError(f"{entry_path}: duplicate object 0x{index:04X}:{subindex}")
                seen.add(key)
                field = fields.get(subindex)
                if kind == "transaction_fields" and field is None:
                    raise ConfigError(f"{entry_path}: missing field definition for subindex {subindex}")
                expanded.append(
                    ExpandedEntry(
                        index=index,
                        subindex=subindex,
                        object_name=object_name,
                        name=name,
                        description=str(entry.get("description", "")),
                        kind=kind,
                        access=access,
                        enabled=enabled,
                        raw=entry,
                        field=field,
                    )
                )
    return tuple(expanded)


def load_config(path: str | Path) -> GeneratorConfig:
    config_path = Path(path).resolve()
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot load {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be a mapping")
    if str(raw.get("schema_version")) != "1.0":
        raise ConfigError("schema_version: expected '1.0'")

    generator = raw.get("generator", {})
    output = generator.get("output", {})
    fragment_path = Path(output.get("fragment", "generated/protocol_switch.inc"))

    protocol = raw.get("protocol", {})
    references = protocol.get("code_references", {})
    response = protocol.get("response", {})
    command_nodes = protocol.get("commands", {})
    read_node = command_nodes.get("read", {})
    read_command = as_int(read_node.get("request"), "protocol.commands.read.request")
    read_responses = {
        as_int(width, "read response width"): as_int(value, f"read response width {width}")
        for width, value in read_node.get("response_by_width", {}).items()
    }

    commands: dict[str, Command] = {}
    for name, node in command_nodes.items():
        require_identifier(name, f"protocol.commands.{name}")
        if name == "read":
            continue
        width = as_int(node.get("payload_width"), f"protocol.commands.{name}.payload_width")
        if width not in {1, 2, 4}:
            raise ConfigError(f"protocol.commands.{name}.payload_width: expected 1, 2 or 4")
        commands[name] = Command(
            name=name,
            request=as_int(node.get("request"), f"protocol.commands.{name}.request"),
            payload_width=width,
            success_response=as_int(node.get("success_response"), f"protocol.commands.{name}.success_response"),
        )

    errors = protocol.get("errors", {})
    error_codes = {name: as_int(value, f"protocol.errors.codes.{name}") for name, value in errors.get("codes", {}).items()}
    for required in ("value_out_of_range", "invalid_key"):
        if required not in error_codes:
            raise ConfigError(f"protocol.errors.codes: missing {required}")

    hook_functions: dict[str, str] = {}
    for name, function in raw.get("hooks", {}).items():
        require_identifier(name, f"hooks.{name}")
        hook_functions[name] = require_identifier(function, f"hooks.{name}")

    config = GeneratorConfig(
        path=config_path,
        raw=raw,
        fragment_path=fragment_path,
        command_reference=require_reference(references.get("command"), "protocol.code_references.command"),
        index_reference=require_reference(references.get("index"), "protocol.code_references.index"),
        subindex_reference=require_reference(references.get("subindex"), "protocol.code_references.subindex"),
        data_reference=require_reference(references.get("data"), "protocol.code_references.data"),
        response_can_id=as_int(response.get("can_id"), "protocol.response.can_id"),
        transmit_function=require_identifier(response.get("transmit_function"), "protocol.response.transmit_function"),
        read_command=read_command,
        read_responses=read_responses,
        commands=commands,
        error_command=as_int(errors.get("response_command"), "protocol.errors.response_command"),
        error_codes=error_codes,
        hooks=hook_functions,
        entries=_expand_entries(raw),
    )
    _validate_references(config)
    return config


def _validate_references(config: GeneratorConfig) -> None:
    for entry in config.entries:
        if not entry.enabled:
            continue
        path = f"0x{entry.index:04X}:{entry.subindex} ({entry.name})"
        read = entry.raw.get("read")
        write = entry.raw.get("write")
        if entry.access != "write_only" and not isinstance(read, dict) and entry.kind != "bitfield":
            raise ConfigError(f"{path}: readable entry requires read configuration")
        if entry.access != "read_only" and not isinstance(write, dict):
            raise ConfigError(f"{path}: writable entry requires write configuration")
        if isinstance(read, dict) and "source" in read:
            require_reference(read["source"], f"{path}.read.source")
        if entry.field and "source" in entry.field:
            require_reference(entry.field["source"], f"{path}.field.source")
        if isinstance(write, dict):
            for command_name in write.get("commands", []):
                if command_name not in config.commands:
                    raise ConfigError(f"{path}: unknown write command {command_name!r}")
            if "target" in write:
                require_reference(write["target"], f"{path}.write.target")
            hook = write.get("hook")
            if hook is not None and hook not in config.hooks:
                raise ConfigError(f"{path}: unknown hook {hook!r}")
        if isinstance(read, dict) and read.get("hook") not in (None, *config.hooks.keys()):
            raise ConfigError(f"{path}: unknown hook {read.get('hook')!r}")
