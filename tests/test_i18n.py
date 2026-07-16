from config_codegen.gui.i18n import (
    ACCESS_OPTIONS,
    KIND_DESCRIPTIONS,
    KIND_OPTIONS,
    WIRE_TYPE_LABELS,
    option_label,
)


def test_enum_labels_and_kind_descriptions_are_complete() -> None:
    assert option_label(ACCESS_OPTIONS, "read_write") == "读写"
    assert option_label(KIND_OPTIONS, "chunked_buffer") == "分包缓冲区"
    assert WIRE_TYPE_LABELS == {
        "u8": "uint8_t",
        "u16": "uint16_t",
        "u32": "uint32_t",
    }
    assert all(code in KIND_DESCRIPTIONS for code, _label in KIND_OPTIONS)
    assert all(KIND_DESCRIPTIONS[code] for code, _label in KIND_OPTIONS)
