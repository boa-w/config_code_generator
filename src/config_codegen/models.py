from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from .errors import ConfigError


_C_REFERENCE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*|\[[0-9]+\])*$")
_C_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BUSINESS_STRING_FIELDS = {
    "requirement_ref",
    "category",
    "unit",
    "value_semantics",
    "notes",
    "owner",
    "verification_ref",
}
_IMPLEMENTATION_STRING_FIELDS = {
    "source_file",
    "source_symbol",
    "module",
    "notes",
}
HOOK_CONTRACTS = {"generic", "read", "write", "transaction", "chunk_write"}


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


def _validate_description_mapping(
    entry: dict[str, Any], key: str, allowed_fields: set[str], path: str
) -> None:
    node = entry.get(key)
    if node is None:
        return
    if not isinstance(node, dict):
        raise ConfigError(f"{path}.{key}: expected mapping")
    unknown = set(node) - allowed_fields
    if unknown:
        raise ConfigError(f"{path}.{key}: unsupported fields {', '.join(sorted(unknown))}")
    for field, value in node.items():
        if field == "default_value":
            if isinstance(value, (dict, list)):
                raise ConfigError(f"{path}.{key}.{field}: expected scalar value")
        elif not isinstance(value, str):
            raise ConfigError(f"{path}.{key}.{field}: expected string")


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
class HookImplementation:
    alias: str
    function: str
    contract: str
    description: str
    call_function: str
    arguments: tuple[str, ...]
    return_policy: str


@dataclass(frozen=True)
class GeneratorConfig:
    path: Path
    raw: dict[str, Any]
    fragment_path: Path
    hook_fragment_path: Path | None
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
    hook_contracts: dict[str, str]
    hook_descriptions: dict[str, str]
    hook_implementations: dict[str, HookImplementation]
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
            _validate_description_mapping(
                entry,
                "business",
                _BUSINESS_STRING_FIELDS | {"default_value"},
                entry_path,
            )
            _validate_description_mapping(
                entry,
                "implementation",
                _IMPLEMENTATION_STRING_FIELDS,
                entry_path,
            )
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

    project = raw.get("project", {})
    if not isinstance(project, dict):
        raise ConfigError("project: expected mapping")
    for field in ("name", "description", "source_file", "source_handler", "generated_notice"):
        if field in project and not isinstance(project[field], str):
            raise ConfigError(f"project.{field}: expected string")
    if project.get("source_handler"):
        require_identifier(project["source_handler"], "project.source_handler")

    generator = raw.get("generator", {})
    output = generator.get("output", {})
    fragment_path = Path(output.get("fragment", "generated/protocol_switch.inc"))
    hook_fragment_value = output.get("hook_implementations")
    hook_fragment_path = Path(hook_fragment_value) if hook_fragment_value else None

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
    hook_contracts: dict[str, str] = {}
    hook_descriptions: dict[str, str] = {}
    hook_implementations: dict[str, HookImplementation] = {}
    for name, definition in raw.get("hooks", {}).items():
        require_identifier(name, f"hooks.{name}")
        if isinstance(definition, str):
            function = definition
            contract = "generic"
            description = ""
        elif isinstance(definition, dict):
            unknown = set(definition) - {"function", "contract", "description", "generate"}
            if unknown:
                raise ConfigError(f"hooks.{name}: unsupported fields {', '.join(sorted(unknown))}")
            function = definition.get("function")
            contract = definition.get("contract", "generic")
            description = definition.get("description", "")
            if contract not in HOOK_CONTRACTS:
                raise ConfigError(f"hooks.{name}.contract: unsupported contract {contract!r}")
            if not isinstance(description, str):
                raise ConfigError(f"hooks.{name}.description: expected string")
        else:
            raise ConfigError(f"hooks.{name}: expected function name or mapping")
        hook_functions[name] = require_identifier(function, f"hooks.{name}.function")
        hook_contracts[name] = contract
        hook_descriptions[name] = description
        generate_node = definition.get("generate") if isinstance(definition, dict) else None
        if generate_node is not None:
            if not isinstance(generate_node, dict):
                raise ConfigError(f"hooks.{name}.generate: expected mapping")
            unknown = set(generate_node) - {
                "enabled",
                "call_function",
                "arguments",
                "return_policy",
            }
            if unknown:
                raise ConfigError(
                    f"hooks.{name}.generate: unsupported fields {', '.join(sorted(unknown))}"
                )
            if bool(generate_node.get("enabled", True)):
                if contract == "generic":
                    raise ConfigError(
                        f"hooks.{name}.generate: generated Hook requires an explicit contract"
                    )
                call_function = require_identifier(
                    generate_node.get("call_function"),
                    f"hooks.{name}.generate.call_function",
                )
                if call_function == function:
                    raise ConfigError(
                        f"hooks.{name}.generate.call_function: must not call the wrapper itself"
                    )
                allowed_arguments = {
                    "read": (),
                    "write": ("value",),
                    "transaction": ("subindex", "value"),
                    "chunk_write": ("subindex", "payload"),
                }[contract]
                raw_arguments = generate_node.get("arguments", list(allowed_arguments))
                if not isinstance(raw_arguments, list) or not all(
                    isinstance(argument, str) for argument in raw_arguments
                ):
                    raise ConfigError(f"hooks.{name}.generate.arguments: expected string list")
                arguments = tuple(raw_arguments)
                if len(set(arguments)) != len(arguments) or any(
                    argument not in allowed_arguments for argument in arguments
                ):
                    raise ConfigError(
                        f"hooks.{name}.generate.arguments: incompatible with {contract!r} contract"
                    )
                return_policy = str(generate_node.get("return_policy", "forward"))
                if return_policy not in {"forward", "always_success"}:
                    raise ConfigError(
                        f"hooks.{name}.generate.return_policy: expected forward or always_success"
                    )
                if contract == "read" and return_policy != "forward":
                    raise ConfigError(
                        f"hooks.{name}.generate.return_policy: read Hook must forward its result"
                    )
                hook_implementations[name] = HookImplementation(
                    alias=name,
                    function=hook_functions[name],
                    contract=contract,
                    description=description,
                    call_function=call_function,
                    arguments=arguments,
                    return_policy=return_policy,
                )

    if hook_implementations and hook_fragment_path is None:
        raise ConfigError(
            "generator.output.hook_implementations: required when generated Hooks are enabled"
        )
    generated_functions: dict[str, str] = {}
    for alias, implementation in hook_implementations.items():
        previous = generated_functions.get(implementation.function)
        if previous is not None:
            raise ConfigError(
                f"hooks.{alias}.function: generated wrapper duplicates Hook {previous!r}"
            )
        generated_functions[implementation.function] = alias

    config = GeneratorConfig(
        path=config_path,
        raw=raw,
        fragment_path=fragment_path,
        hook_fragment_path=hook_fragment_path,
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
        hook_contracts=hook_contracts,
        hook_descriptions=hook_descriptions,
        hook_implementations=hook_implementations,
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
        if isinstance(read, dict):
            wire_type = read.get("wire_type")
            if wire_type not in {"u8", "u16", "u32"}:
                raise ConfigError(f"{path}.read.wire_type: expected u8, u16 or u32")
            seen_bits: set[int] = set()
            for bit_pos, bit in enumerate(read.get("bits", [])):
                if not isinstance(bit, dict):
                    raise ConfigError(f"{path}.read.bits[{bit_pos}]: expected mapping")
                position = as_int(bit.get("bit"), f"{path}.read.bits[{bit_pos}].bit")
                if not 0 <= position <= 31 or position in seen_bits:
                    raise ConfigError(f"{path}.read.bits[{bit_pos}].bit: invalid or duplicate bit")
                seen_bits.add(position)
                require_reference(bit.get("source"), f"{path}.read.bits[{bit_pos}].source")
                if bit.get("active", "high") not in {"high", "low"}:
                    raise ConfigError(f"{path}.read.bits[{bit_pos}].active: expected high or low")
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
            if hook is not None:
                expected_contract = (
                    "transaction" if entry.kind == "transaction_fields"
                    else "chunk_write" if entry.kind == "chunked_buffer"
                    else "write"
                )
                _validate_hook_contract(config, hook, expected_contract, f"{path}.write.hook")
        if isinstance(read, dict) and read.get("hook") not in (None, *config.hooks.keys()):
            raise ConfigError(f"{path}: unknown hook {read.get('hook')!r}")
        if isinstance(read, dict) and read.get("hook") is not None:
            _validate_hook_contract(config, read["hook"], "read", f"{path}.read.hook")
        if entry.kind == "chunked_buffer":
            buffer = entry.raw.get("buffer")
            if not isinstance(buffer, dict):
                raise ConfigError(f"{path}.buffer: expected mapping")
            require_reference(buffer.get("source"), f"{path}.buffer.source")
            for field in ("length", "chunk_size", "first_subindex"):
                if as_int(buffer.get(field), f"{path}.buffer.{field}") < 0:
                    raise ConfigError(f"{path}.buffer.{field}: must not be negative")
        implementation = entry.raw.get("implementation", {})
        if implementation.get("source_symbol"):
            require_reference(implementation["source_symbol"], f"{path}.implementation.source_symbol")


def _validate_hook_contract(
    config: GeneratorConfig, hook: str, expected: str, path: str
) -> None:
    contract = config.hook_contracts.get(hook, "generic")
    if contract not in {"generic", expected}:
        raise ConfigError(f"{path}: Hook contract {contract!r} is incompatible with {expected!r}")
