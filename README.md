# Config Code Generator

Generate an embeddable C `if`/`switch-case` protocol fragment from YAML. The
public example contains fictional identifiers and values and is not based on a
production protocol.

## Setup

```powershell
python -m pip install -e ".[test,gui]"
```

## Usage

```powershell
cfggen validate config/protocol.example.yaml
cfggen list config/protocol.example.yaml
cfggen generate config/protocol.example.yaml
pytest
```

## Graphical editor

```powershell
cfggen-gui config/protocol.example.yaml
```

## Windows executable

```powershell
python -m pip install -e ".[gui,exe]"
python packaging/build_exe.py
```

The portable application is written to `dist/config-code-generator/`. The ZIP
release asset is written to
`artifacts/config-code-generator-nightly-windows-x64.zip`. Keep the external
`config/protocol.example.yaml` beside the EXE directory so it remains editable.

Every push to `main` runs tests, builds the Windows x64 portable package, smoke
tests the packaged EXE, and replaces the ZIP and `update-manifest.json` assets
in the `nightly` prerelease.

## Application updates

The About page provides the complete manual update flow: check the nightly
channel, download the package, verify its declared size and SHA-256 digest, and
install it after confirmation. Automatic checks are not scheduled; the update
service exposes a reserved configuration interface for a future opt-in policy.

On Windows, a separate one-file updater waits for the editor to exit, replaces
the portable runtime, and restarts the new version. The entire external
`config/` directory is preserved. If the new process does not report a healthy
startup within the timeout, the updater restores the previous runtime and
restarts it. ZIP extraction rejects path traversal, symbolic links, excessive
file counts, and excessive expanded size.

The nightly manifest uses the GitHub Actions `run_number` as a monotonic build
number. Local builds default to build 1; official workflow builds embed their
actual run number in the application and manifest.

## Versioning

The manually maintained version is `BASE_VERSION` in
`src/config_codegen/version.py`. Runtime versions use the form
`<base>+g<8-character-commit>`, for example `0.1.0+g1a2b3c4d`.

```powershell
cfggen --version
cfggen-gui --version
```

Development runs read the commit from Git. The EXE build embeds the current
commit into a PyInstaller runtime hook and writes the same version into Windows
file properties. Change only `BASE_VERSION` when manually releasing a new
version.

The desktop editor provides Index navigation, entry enable/disable controls,
protocol metadata editing, read/write operation switches, undo/redo, validation,
generated fragment preview, and a diff against the current generated file.
YAML comments and field order are preserved when saving.

The `基础配置` node manages the generated fragment path, response CAN ID,
transmit function, and the C references used for command, Index, SubIndex, and
payload data. These project-level settings remain in YAML and are intentionally
not replaced by CSV import.

Entries can be added or deleted from the toolbar. New entries start as
`planned` and disabled so incomplete implementation details cannot enter the
generated fragment. CSV export uses UTF-8 with BOM for Excel compatibility and
keeps nested `read`, `write`, `fields`, and `buffer` values in JSON columns.
CSV import validates the complete configuration, replaces only the `objects`
inventory, and can be reverted with one undo operation.

The generated `.inc` fragment is written to `generator.output.fragment`. Scalar
reads and writes are emitted directly. Complex behavior is dispatched to
handwritten hooks, but the generator does not emit a function, header, parser,
runtime helpers, or hook declarations.

Use `enabled` at object, entry, read, or write level to control generated code.
Disabled entries remain in the YAML protocol inventory and appear as `OFF` in
`cfggen list`, so planned and product-specific protocol items are not lost.

The surrounding project must provide the configured request references, send
function, application variables, storage functions, and hook implementations.

Hook contracts used by generated call sites are:

- Read hook: `uint32_t Hook(void)`
- Write/action hook: `bool Hook(uint32_t value)`
- Transaction hook: `bool Hook(uint8_t subindex, uint32_t value)`
- Chunk write hook: `bool Hook(uint8_t subindex, const uint8_t payload[4])`

When `acknowledge_before_hook` is enabled, the generated handler sends the ACK
first and intentionally ignores the hook return value. This is intended for
operations such as a system reset that may not return.
