from pathlib import Path

from config_codegen.update.installer import replace_installation, restore_installation


def test_replace_preserves_config_and_can_restore(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    backup = tmp_path / "backup"
    source.mkdir()
    target.mkdir()
    (source / "config-code-generator.exe").write_text("new", encoding="utf-8")
    (source / "library.dll").write_text("new lib", encoding="utf-8")
    (source / "config").mkdir()
    (source / "config" / "protocol.example.yaml").write_text("new example", encoding="utf-8")
    (target / "config-code-generator.exe").write_text("old", encoding="utf-8")
    (target / "old.dll").write_text("old lib", encoding="utf-8")
    (target / "config").mkdir()
    (target / "config" / "private.yaml").write_text("private", encoding="utf-8")

    replace_installation(source, target, backup)

    assert (target / "config-code-generator.exe").read_text(encoding="utf-8") == "new"
    assert (target / "library.dll").is_file()
    assert not (target / "old.dll").exists()
    assert (target / "config" / "private.yaml").read_text(encoding="utf-8") == "private"
    assert not (target / "config" / "protocol.example.yaml").exists()

    restore_installation(target, backup)

    assert (target / "config-code-generator.exe").read_text(encoding="utf-8") == "old"
    assert (target / "old.dll").is_file()
    assert not (target / "library.dll").exists()
