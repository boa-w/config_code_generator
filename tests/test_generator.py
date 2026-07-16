from pathlib import Path

import pytest
import yaml

from config_codegen.errors import ConfigError
from config_codegen.generator import generate, generate_outputs
from config_codegen.models import load_config


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "config" / "protocol.example.yaml"


def test_sample_config_expands_ranges() -> None:
    config = load_config(SAMPLE)

    assert len(config.entries) == 14
    assert sum(entry.enabled for entry in config.entries) == 13
    assert {(entry.index, entry.subindex) for entry in config.entries} >= {
        (0x2200, 1),
        (0x2200, 4),
        (0x2400, 1),
        (0x2400, 3),
    }


def test_generates_nested_switches_and_hooks(tmp_path: Path) -> None:
    fragment_path, hook_path = generate_outputs(SAMPLE, tmp_path)
    source = fragment_path.read_text(encoding="utf-8")
    assert hook_path is not None
    hooks = hook_path.read_text(encoding="utf-8")

    assert "if (DemoRequest.Command == 0x40)" in source
    assert "    if (DemoRequest.Index == 0x2000)" in source
    assert "switch (DemoRequest.SubIndex)" in source
    assert "case 1: // [DEMO-SET-01] 语言选项" in source
    assert "Demo_Hook_WriteCalendarField(DemoRequest.SubIndex," in source
    assert "g_demoBrightness = (DemoRequest.Data[5] * 256u + DemoRequest.Data[4]);" in source
    assert "Demo_Eeprom_WriteByte(1, g_demoBrightness);" in source
    assert "== 0xA5A55A5Au" in source
    assert "[DEMO-SET-10]" not in source
    assert "#include" not in source
    ack = "Demo_Can_SendResponse(0x580, 0x60"
    reset = "(void)Demo_Hook_ResetDevice("
    reset_case = source[source.index("case 1: // [DEMO-CTL-01] 复位演示设备") :]
    assert reset_case.index(ack) < reset_case.index(reset)
    assert "uint32_t Demo_Hook_ReadIndicator(void)" in hooks
    assert "return Demo_ReadIndicatorState();" in hooks
    assert "bool Demo_Hook_WriteIndicator(uint32_t value)" in hooks
    assert "return Demo_ApplyIndicatorState(value);" in hooks
    assert "(void)Demo_ResetDevice();" in hooks
    assert "(void)value;" in hooks
    assert "return true;" in hooks
    assert "#include" not in hooks


def test_duplicate_object_is_rejected(tmp_path: Path) -> None:
    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    duplicate = dict(document["objects"][0]["entries"][0])
    document["objects"][0]["entries"].append(duplicate)
    config_path = tmp_path / "duplicate.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError, match="duplicate object"):
        load_config(config_path)


def test_code_references_are_configurable(tmp_path: Path) -> None:
    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    document["protocol"]["code_references"] = {
        "command": "Request.Command",
        "index": "Request.Index",
        "subindex": "Request.SubIndex",
        "data": "Request.Payload",
    }
    document["protocol"]["response"]["transmit_function"] = "Custom_Send"
    config_path = tmp_path / "custom.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    fragment = generate(config_path, tmp_path).read_text(encoding="utf-8")

    assert "if (Request.Command == 0x40)" in fragment
    assert "if (Request.Index == 0x2000)" in fragment
    assert "switch (Request.SubIndex)" in fragment
    assert "Request.Payload[5]" in fragment
    assert "Custom_Send(0x580" in fragment


def test_business_description_rejects_unknown_fields(tmp_path: Path) -> None:
    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    document["objects"][0]["entries"][0]["business"]["unsupported"] = "value"
    config_path = tmp_path / "invalid-business.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError, match="unsupported fields"):
        load_config(config_path)


def test_hook_contract_rejects_incompatible_usage(tmp_path: Path) -> None:
    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    document["hooks"]["read_indicator"]["contract"] = "write"
    config_path = tmp_path / "invalid-hook-contract.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")

    with pytest.raises(ConfigError, match="incompatible"):
        load_config(config_path)


def test_generated_hook_rejects_invalid_arguments_and_missing_output(tmp_path: Path) -> None:
    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    document["hooks"]["write_indicator"]["generate"]["arguments"] = ["payload"]
    config_path = tmp_path / "invalid-hook-arguments.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="arguments"):
        load_config(config_path)

    document = yaml.safe_load(SAMPLE.read_text(encoding="utf-8"))
    del document["generator"]["output"]["hook_implementations"]
    config_path = tmp_path / "missing-hook-output.yaml"
    config_path.write_text(yaml.safe_dump(document, allow_unicode=True), encoding="utf-8")
    with pytest.raises(ConfigError, match="hook_implementations"):
        load_config(config_path)
