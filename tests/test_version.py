from config_codegen.version import BASE_VERSION, format_version, get_version_info


def test_version_combines_manual_version_and_commit(monkeypatch) -> None:
    monkeypatch.setenv("CONFIG_CODE_GENERATOR_COMMIT", "ABCDEF1234567890")

    info = get_version_info()

    assert info.base_version == BASE_VERSION
    assert info.commit == "abcdef12"
    assert info.version == f"{BASE_VERSION}+gabcdef12"


def test_version_omits_unknown_commit() -> None:
    assert format_version(BASE_VERSION, "unknown") == BASE_VERSION
    assert format_version(BASE_VERSION, "not-a-hash") == BASE_VERSION
