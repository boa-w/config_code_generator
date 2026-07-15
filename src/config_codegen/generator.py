from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from .errors import ConfigError
from .models import Command, ExpandedEntry, GeneratorConfig, as_int, load_config, require_identifier


_WIRE_WIDTHS = {"u8": 1, "u16": 2, "u32": 4}


@dataclass(frozen=True)
class Case:
    value: int
    comment: str
    lines: tuple[str, ...]
    scoped: bool = False


@dataclass(frozen=True)
class IndexCase:
    value: int
    entries: tuple[Case, ...]


@dataclass(frozen=True)
class CommandCase:
    value: int
    name: str
    indices: tuple[IndexCase, ...]


def _wire_width(node: dict[str, Any], path: str) -> int:
    wire_type = node.get("wire_type")
    if wire_type not in _WIRE_WIDTHS:
        raise ConfigError(f"{path}: unsupported wire_type {wire_type!r}")
    return _WIRE_WIDTHS[wire_type]


def _hook(config: GeneratorConfig, name: str | None, path: str) -> str:
    if name is None or name not in config.hooks:
        raise ConfigError(f"{path}: unknown hook {name!r}")
    return config.hooks[name]


def _comment(entry: ExpandedEntry) -> str:
    protocol_ref = entry.raw.get("protocol_ref", f"0x{entry.index:04X}:{entry.subindex}")
    description = entry.description or entry.name
    return f"[{protocol_ref}] {description}"


def _decode_expression(config: GeneratorConfig, width: int) -> str:
    data = config.data_reference
    if width == 1:
        return f"{data}[4]"
    if width == 2:
        return f"({data}[5] * 256u + {data}[4])"
    if width == 4:
        return f"(((uint32_t){data}[7] << 24u) | ((uint32_t){data}[6] << 16u) | ((uint32_t){data}[5] << 8u) | {data}[4])"
    raise ConfigError(f"unsupported payload width {width}")


def _send(config: GeneratorConfig, command: int, payload: list[str]) -> str:
    if len(payload) != 4:
        raise ConfigError("response payload must contain four bytes")
    return (
        f"{config.transmit_function}(0x{config.response_can_id:03X}, 0x{command:02X}, "
        f"{config.index_reference} & 0xFF, {config.index_reference} >> 8, {config.subindex_reference}, "
        f"{', '.join(payload)}, 0x00);"
    )


def _ack(config: GeneratorConfig, command: Command) -> str:
    return _send(config, command.success_response or 0x60, ["0x00"] * 4)


def _error(config: GeneratorConfig, code_name: str) -> str:
    code = config.error_codes[code_name]
    return _send(config, config.error_command, [f"0x{code:02X}", "0x00", "0x00", "0x00"])


def _read_expression(entry: ExpandedEntry) -> str:
    read = entry.raw.get("read", {})
    source = entry.field.get("source") if entry.field else read.get("source")
    if source is None:
        raise ConfigError(f"0x{entry.index:04X}:{entry.subindex}: read source is required")
    transform = read.get("transform")
    if transform:
        if transform.get("kind") != "divide_integer":
            raise ConfigError(f"{entry.name}: unsupported transform {transform.get('kind')!r}")
        divisor = as_int(transform.get("divisor"), f"{entry.name}.read.transform.divisor")
        if divisor == 0:
            raise ConfigError(f"{entry.name}: transform divisor must not be zero")
        source = f"(({source}) / {divisor}u)"
    if read.get("year_transform") == "subtract_2000" and entry.field and entry.field.get("name") == "year":
        source = f"(({source}) >= 2000u ? ({source}) - 2000u : ({source}))"
    return source


def _value_payload(expression: str, width: int) -> list[str]:
    if width == 1:
        return [f"{expression} & 0xFF", "0x00", "0x00", "0x00"]
    if width == 2:
        return [f"{expression} & 0xFF", f"{expression} >> 8", "0x00", "0x00"]
    return [
        f"{expression} & 0xFF",
        f"({expression} >> 8) & 0xFF",
        f"({expression} >> 16) & 0xFF",
        f"({expression} >> 24) & 0xFF",
    ]


def _read_case(config: GeneratorConfig, entry: ExpandedEntry) -> Case:
    read = entry.raw.get("read", {})
    width = _wire_width(read, f"{entry.name}.read")
    response = config.read_responses.get(width)
    if response is None:
        raise ConfigError(f"{entry.name}.read: no response command for width {width}")

    if entry.kind in {"scalar", "transaction_fields"}:
        expression = _read_expression(entry)
        return Case(entry.subindex, _comment(entry), (_send(config, response, _value_payload(expression, width)),))

    if entry.kind == "bitfield":
        terms: list[str] = []
        for bit in read.get("bits", []):
            position = as_int(bit.get("bit"), f"{entry.name}.read.bits.bit")
            source = bit.get("source")
            active = source if bit.get("active", "high") == "high" else f"!({source})"
            terms.append(f"(({active}) ? (1u << {position}) : 0u)")
        expression = " | ".join(terms) or "0u"
        lines = (f"uint32_t generatedValue = {expression};", _send(config, response, _value_payload("generatedValue", width)))
        return Case(entry.subindex, _comment(entry), lines, scoped=True)

    if entry.kind == "hook":
        function = _hook(config, read.get("hook"), f"{entry.name}.read.hook")
        lines = (f"uint32_t generatedValue = {function}();", _send(config, response, _value_payload("generatedValue", width)))
        return Case(entry.subindex, _comment(entry), lines, scoped=True)

    if entry.kind == "chunked_buffer":
        buffer = entry.raw.get("buffer", {})
        source = buffer.get("source")
        capacity = as_int(buffer.get("length", buffer.get("capacity")), f"{entry.name}.buffer.capacity")
        chunk_size = as_int(buffer.get("chunk_size"), f"{entry.name}.buffer.chunk_size")
        first = as_int(buffer.get("first_subindex"), f"{entry.name}.buffer.first_subindex")
        padding = as_int(buffer.get("padding", 0), f"{entry.name}.buffer.padding")
        if chunk_size != 4 or width != 4:
            raise ConfigError(f"{entry.name}: first version supports only four-byte chunks")
        offset = (entry.subindex - first) * chunk_size
        payload = [f"({offset + pos}u < {capacity}u ? {source}[{offset + pos}] : 0x{padding:02X})" for pos in range(4)]
        return Case(entry.subindex, _comment(entry), (_send(config, response, payload),))

    raise ConfigError(f"{entry.name}: kind {entry.kind!r} cannot be read")


def _validation_lines(config: GeneratorConfig, entry: ExpandedEntry, target: str, write: dict[str, Any]) -> list[str]:
    validation = write.get("validation", {})
    allowed = validation.get("allowed_values")
    if allowed:
        comparisons = " && ".join(f"{target} != {as_int(item, entry.name)}u" for item in allowed)
        return [f"if ({comparisons})", "{", f"    {_error(config, 'value_out_of_range')}", "    break;", "}"]

    minimum = validation.get("minimum")
    maximum = validation.get("maximum")
    if validation.get("type_ref"):
        type_node = config.raw.get("types", {}).get(validation["type_ref"], {})
        minimum = type_node.get("minimum", minimum)
        maximum = type_node.get("maximum", maximum)
    policy = validation.get("policy", "reject")
    lines: list[str] = []
    for operator, bound, replacement in (("<", minimum, minimum), (">", maximum, maximum)):
        if bound is None:
            continue
        value = as_int(bound, f"{entry.name}.validation")
        if operator == "<" and value <= 0:
            continue
        lines.extend([f"if ({target} {operator} {value}u)", "{"])
        if policy == "clamp":
            lines.append(f"    {target} = {as_int(replacement, entry.name)}u;")
        else:
            lines.extend([f"    {_error(config, 'value_out_of_range')}", "    break;"])
        lines.append("}")
    return lines


def _scalar_write_lines(config: GeneratorConfig, entry: ExpandedEntry, command: Command) -> tuple[str, ...]:
    write = entry.raw["write"]
    target = write.get("target")
    if not target:
        raise ConfigError(f"{entry.name}.write.target is required")
    lines = [f"{target} = {_decode_expression(config, command.payload_width)};"]
    lines.extend(_validation_lines(config, entry, target, write))
    storage = write.get("storage")
    if storage:
        kind = storage.get("kind")
        if kind == "eeprom_u8":
            function = require_identifier(storage.get("function"), f"{entry.name}.storage.function")
            address = as_int(storage.get("address"), f"{entry.name}.storage.address")
            lines.append(f"{function}({address}, {target});")
        elif kind == "eeprom_bytes":
            function = require_identifier(storage.get("function"), f"{entry.name}.storage.function")
            addresses = storage.get("addresses", [])
            if len(addresses) != command.payload_width:
                raise ConfigError(f"{entry.name}.storage.addresses: count must match command width")
            byte_order = storage.get("byte_order", "little_endian")
            for pos, raw_address in enumerate(addresses):
                shift_pos = command.payload_width - 1 - pos if byte_order == "big_endian" else pos
                address = as_int(raw_address, f"{entry.name}.storage.addresses")
                lines.append(f"{function}({address}, ({target} >> {shift_pos * 8}) & 0xFF);")
        elif kind == "hook":
            function = require_identifier(storage.get("function"), f"{entry.name}.storage.function")
            lines.append(f"{function}({target});")
        else:
            raise ConfigError(f"{entry.name}.storage.kind: unsupported kind {kind!r}")
    after_write = write.get("after_write")
    if after_write:
        function = require_identifier(after_write.get("function"), f"{entry.name}.after_write.function")
        lines.append(f"{function}({target});")
    lines.append(_ack(config, command))
    return tuple(lines)


def _hook_write_lines(config: GeneratorConfig, entry: ExpandedEntry, command: Command) -> tuple[str, ...]:
    write = entry.raw["write"]
    function = _hook(config, write.get("hook"), f"{entry.name}.write.hook")
    value = _decode_expression(config, command.payload_width)
    authorization = write.get("authorization")
    prefix: list[str] = []
    suffix: list[str] = []
    if authorization:
        if authorization.get("kind") != "magic_value":
            raise ConfigError(f"{entry.name}.authorization.kind: expected 'magic_value'")
        expected = as_int(authorization.get("value"), f"{entry.name}.authorization.value")
        prefix = [f"if ({value} == 0x{expected:08X}u)", "{"]
        suffix = ["}", "else", "{", f"    {_error(config, 'invalid_key')}", "}"]

    if entry.kind == "transaction_fields":
        call = f"{function}({config.subindex_reference}, {value})"
    elif entry.kind == "chunked_buffer":
        call = f"{function}({config.subindex_reference}, &{config.data_reference}[4])"
    else:
        call = f"{function}({value})"

    inner: list[str]
    if write.get("acknowledge_before_hook", False):
        inner = [_ack(config, command), f"(void){call};"]
    else:
        inner = [f"if ({call})", "{", f"    {_ack(config, command)}", "}", "else", "{", f"    {_error(config, 'value_out_of_range')}", "}"]
    if prefix:
        inner = [f"    {line}" if line else line for line in inner]
    return tuple(prefix + inner + suffix)


def _write_case(config: GeneratorConfig, entry: ExpandedEntry, command: Command) -> Case:
    if entry.kind == "scalar":
        lines = _scalar_write_lines(config, entry, command)
    else:
        lines = _hook_write_lines(config, entry, command)
    return Case(entry.subindex, _comment(entry), lines)


def _group_indices(cases: list[tuple[int, Case]]) -> tuple[IndexCase, ...]:
    grouped: dict[int, list[Case]] = {}
    for index, case in cases:
        grouped.setdefault(index, []).append(case)
    return tuple(IndexCase(index, tuple(entries)) for index, entries in grouped.items())


def _build_cases(config: GeneratorConfig) -> tuple[CommandCase, ...]:
    command_cases: list[CommandCase] = []
    read_cases = [
        (entry.index, _read_case(config, entry))
        for entry in config.entries
        if entry.enabled
        and entry.access != "write_only"
        and entry.raw.get("read", {}).get("enabled", True)
    ]
    if read_cases:
        command_cases.append(CommandCase(config.read_command, "read", _group_indices(read_cases)))

    for command in config.commands.values():
        cases: list[tuple[int, Case]] = []
        for entry in config.entries:
            if not entry.enabled or entry.access == "read_only":
                continue
            write = entry.raw.get("write", {})
            if not write.get("enabled", True) or command.name not in write.get("commands", []):
                continue
            cases.append((entry.index, _write_case(config, entry, command)))
        if cases:
            command_cases.append(CommandCase(command.request, command.name, _group_indices(cases)))
    return tuple(command_cases)


def generate(config_path: str | Path, output_root: str | Path | None = None) -> Path:
    config = load_config(config_path)
    root = Path(output_root).resolve() if output_root else config.path.parent.parent
    fragment_path = root / config.fragment_path
    fragment_path.parent.mkdir(parents=True, exist_ok=True)
    environment = Environment(
        loader=PackageLoader("config_codegen", "templates"),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    content = environment.get_template("switch_fragment.c.j2").render(
        config=config,
        commands=_build_cases(config),
    )
    fragment_path.write_text(content, encoding="utf-8", newline="\n")
    return fragment_path
