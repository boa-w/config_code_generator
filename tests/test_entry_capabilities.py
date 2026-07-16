import pytest

from config_codegen.gui.entry_capabilities import (
    TEMPLATE_OPTIONS,
    capability_for,
    create_entry_from_template,
)


@pytest.mark.parametrize("template,_label", TEMPLATE_OPTIONS)
def test_entry_templates_create_complete_disabled_inventory(template: str, _label: str) -> None:
    entry = create_entry_from_template(
        template,
        index=0x2000,
        subindex=7,
        name="demo_entry",
        description="Demo entry",
        write_command="write_u16",
    )

    assert entry["enabled"] is False
    assert "status" not in entry
    assert entry["protocol_ref"] == "0x2000:07"
    assert entry["kind"]
    assert entry["access"]


def test_capability_matrix_limits_scalar_and_buffer_fields() -> None:
    scalar = capability_for("scalar")
    chunk = capability_for("chunked_buffer")

    assert scalar.read_source and scalar.validation and scalar.storage
    assert not scalar.read_hook and not scalar.buffer
    assert chunk.buffer and chunk.write_hook and chunk.complex_structure
    assert not chunk.validation and not chunk.storage
