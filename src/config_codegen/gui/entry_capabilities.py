from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ruamel.yaml.comments import CommentedMap, CommentedSeq


@dataclass(frozen=True)
class EntryCapability:
    read_source: bool = False
    read_hook: bool = False
    read_transform: bool = False
    write_target: bool = False
    write_hook: bool = False
    validation: bool = False
    storage: bool = False
    authorization: bool = False
    buffer: bool = False
    complex_structure: bool = False


CAPABILITIES = {
    "scalar": EntryCapability(
        read_source=True,
        read_transform=True,
        write_target=True,
        validation=True,
        storage=True,
    ),
    "bitfield": EntryCapability(complex_structure=True),
    "hook": EntryCapability(read_hook=True, write_hook=True),
    "action": EntryCapability(write_hook=True, authorization=True),
    "transaction_fields": EntryCapability(
        write_hook=True,
        complex_structure=True,
    ),
    "chunked_buffer": EntryCapability(
        write_hook=True,
        buffer=True,
        complex_structure=True,
    ),
}


TEMPLATE_OPTIONS = (
    ("read_scalar", "只读标量"),
    ("read_write_scalar", "读写标量"),
    ("bitfield", "位域状态"),
    ("hook", "Hook 处理"),
    ("action", "操作命令"),
    ("transaction_fields", "事务字段"),
    ("chunked_buffer", "分包缓冲区"),
)


def capability_for(kind: object) -> EntryCapability:
    return CAPABILITIES.get(str(kind or ""), EntryCapability())


def create_entry_from_template(
    template: str,
    *,
    index: int,
    subindex: int,
    name: str,
    description: str,
    write_command: str,
) -> CommentedMap:
    common: dict[str, Any] = {
        "subindex": subindex,
        "name": name,
        "description": description,
        "protocol_ref": f"0x{index:04X}:{subindex:02X}",
        "status": "planned",
        "enabled": False,
    }
    if template == "read_scalar":
        common.update(
            kind="scalar",
            access="read_only",
            read=CommentedMap({"wire_type": "u16", "source": "TODO_value"}),
        )
    elif template == "read_write_scalar":
        common.update(
            kind="scalar",
            access="read_write",
            read=CommentedMap({"wire_type": "u16", "source": "TODO_value"}),
            write=CommentedMap(
                {"commands": CommentedSeq([write_command]), "target": "TODO_value"}
            ),
        )
    elif template == "bitfield":
        common.update(
            kind="bitfield",
            access="read_only",
            read=CommentedMap(
                {
                    "wire_type": "u32",
                    "bits": CommentedSeq(
                        [CommentedMap({"bit": 0, "source": "TODO_flag", "active": "high"})]
                    ),
                }
            ),
        )
    elif template == "hook":
        common.update(
            kind="hook",
            access="read_write",
            read=CommentedMap({"wire_type": "u32", "enabled": False}),
            write=CommentedMap(
                {"commands": CommentedSeq([write_command]), "enabled": False}
            ),
        )
    elif template == "action":
        common.update(
            kind="action",
            access="write_only",
            write=CommentedMap(
                {"commands": CommentedSeq([write_command]), "enabled": False}
            ),
        )
    elif template == "transaction_fields":
        common.update(
            kind="transaction_fields",
            access="read_write",
            fields=CommentedSeq(
                [CommentedMap({"subindex": subindex, "name": "field", "source": "TODO_value"})]
            ),
            read=CommentedMap({"wire_type": "u16"}),
            write=CommentedMap(
                {"commands": CommentedSeq([write_command]), "enabled": False}
            ),
        )
    elif template == "chunked_buffer":
        common.update(
            kind="chunked_buffer",
            access="read_only",
            read=CommentedMap({"wire_type": "u32"}),
            buffer=CommentedMap(
                {
                    "source": "TODO_buffer",
                    "length": 4,
                    "chunk_size": 4,
                    "first_subindex": subindex,
                    "padding": 0,
                }
            ),
        )
    else:
        raise ValueError(f"unknown entry template: {template}")
    return CommentedMap(common)
