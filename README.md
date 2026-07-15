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
