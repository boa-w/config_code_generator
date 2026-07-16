# Config Code Generator

[English](README.md) | [简体中文](README.zh-CN.md)

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

## Business and implementation descriptions

Protocol entries can carry structured information that does not alter generated
C code but keeps requirements, protocol behavior, and the target implementation
traceable in one file:

```yaml
business:
  requirement_ref: "DEMO-REQ-001"
  category: display
  unit: enum
  default_value: 0
  value_semantics: "0=Chinese, 1=English"
  owner: display-team
  verification_ref: "DEMO-TEST-001"
  notes: "Applied immediately and retained after power loss."
implementation:
  source_file: demo_settings.c
  source_symbol: g_demoLanguage
  module: display_settings
  notes: "Stored in one EEPROM byte."
```

The project mapping also accepts `description`, `source_file`, and
`source_handler` to identify the handwritten handler from which a configuration
was derived. These description fields are validated, shown in the GUI, and
preserved by CSV import/export.

The entry inspector shows identity and inventory state first, then reveals only
the read, write, validation, persistence, authorization, or buffer controls
supported by the selected implementation kind and access mode. Requirement and
source traceability stay in a collapsed section until needed. Field-level
errors appear at the top of the inspector and mark the corresponding control.
The `高级 YAML` dialog handles bit lists, transaction fields, and uncommon
combinations; its changes participate in undo/redo and normal live validation.

The left navigation exposes separate `项目设置`, `命令定义`, `错误响应`, and
`Hook 管理` pages. Together they manage project source information, generated
fragment path, response CAN ID, transmit function, errors, commands, Hook
aliases, and C references. These project-level settings remain in YAML and are
intentionally not replaced by CSV import. Commands use an editable YAML block;
Hooks use a structured registry with contracts and reference-aware rename and
delete operations.

Entries can be added from templates for read-only scalars, read/write scalars,
bitfields, Hooks, actions, transaction fields, and chunked buffers. The compact
dialog asks only for template, SubIndex, internal name, and display name. New
entries start as `planned` and disabled so incomplete implementation details
cannot enter the generated fragment. The inventory supports cross-field search
and configurable visible columns. CSV export uses UTF-8 with BOM for Excel compatibility and
keeps nested `read`, `write`, `fields`, `buffer`, `business`, and
`implementation` values in JSON columns. Older CSV files without the two
description columns remain importable.
CSV import validates the complete configuration, replaces only the `objects`
inventory, and can be reverted with one undo operation.

The switch `.inc` fragment is written to `generator.output.fragment`. Scalar
reads and writes are emitted directly. Complex behavior is dispatched to Hooks.
Hooks remain handwritten by default; Hooks with an enabled `generate` mapping
are emitted as wrapper definitions to `generator.output.hook_implementations`.
The generator still does not emit headers, parsers, or runtime helpers.

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

Every Hook uses a structured definition with an explicit call contract:

```yaml
hooks:
  read_indicator:
    function: Demo_Hook_ReadIndicator
    contract: read
    description: "Read the current indicator state."
```

An explicitly generated Hook can forward to an existing business function:

```yaml
generator:
  output:
    fragment: generated/demo_protocol_switch.inc
    hook_implementations: generated/demo_protocol_hooks.inc

hooks:
  write_indicator:
    function: Demo_Hook_WriteIndicator
    contract: write
    description: "Apply an indicator state."
    generate:
      enabled: true
      call_function: Demo_ApplyIndicatorState
      arguments: [value]
      return_policy: forward
```

`arguments` may contain only parameters exposed by the selected contract. It
can forward all parameters, a supported subset, or no parameters. The
`forward` policy returns the target function result; `always_success` calls the
target as `void` and returns `true`, which is useful for existing void actions.
Read Hooks must use `forward`.

The generated Hook fragment contains function definitions but no includes or
target declarations. Include it after the target functions are declared and
before the generated switch fragment. The surrounding project remains
responsible for implementing or linking each configured `call_function`.

Supported contracts are `read`, `write`, `transaction`, and `chunk_write`.
String-only Hook definitions and untyped contracts are rejected. The validator
also rejects a Hook used at an incompatible call site. The GUI Hook registry
supports adding, renaming, deleting, documenting, and changing contracts.
Renames update every entry reference. Deleting a referenced Hook clears and
disables those operations so invalid calls are not generated.
The entry editor filters Hook choices by contract and can create and bind a new
Hook directly from the read or write field. The Hook management page also
controls wrapper generation, target function, forwarded arguments, and return
policy. Generated wrappers are shown in the `Hook 实现` preview tab and are
written together with the switch fragment.

When `acknowledge_before_hook` is enabled, the generated handler sends the ACK
first and intentionally ignores the hook return value. This is intended for
operations such as a system reset that may not return.
