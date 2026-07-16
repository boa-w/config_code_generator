# Config Code Generator

[English](README.md) | [简体中文](README.zh-CN.md)

根据 YAML 配置生成可嵌入现有项目的 C `if` / `switch-case` 协议处理片段。公开示例中的标识符、地址和值均为虚构内容，不来源于生产协议。

## 环境安装

```powershell
python -m pip install -e ".[test,gui]"
```

## 命令行使用

```powershell
cfggen validate config/protocol.example.yaml
cfggen list config/protocol.example.yaml
cfggen generate config/protocol.example.yaml
pytest
```

生成结果是可以直接嵌入现有函数的代码片段，不包含完整函数、头文件、解析器或运行时辅助代码。

## 图形化编辑器

```powershell
cfggen-gui config/protocol.example.yaml
```

编辑器提供：

- Index 对象导航和条目启停管理；
- 协议条目搜索、列显示管理和模板化新增；
- 读取、写入、校验、持久化、授权和分包参数配置；
- 项目设置、命令定义、错误响应和 Hook 管理；
- 撤销、重做、实时校验、代码预览和 Diff；
- YAML 注释与字段顺序的往返保存。

条目检查器会根据实现类型和访问权限，只显示当前条目需要的控件。例如标量条目显示变量、范围和存储配置；Hook 条目显示契约匹配的 Hook；分包条目显示缓冲区参数。业务追踪信息默认折叠，完整条目 YAML 放在专家入口中。

## 新增条目

GUI 支持以下模板：

- 只读标量；
- 读写标量；
- 位域状态；
- Hook 处理；
- 操作命令；
- 事务字段；
- 分包缓冲区。

新增对话框只要求选择模板并填写 SubIndex、内部名称和显示名称。新条目默认状态为 `planned` 且关闭生成，避免尚未完成的实现进入生成代码。

## 业务和实现描述

条目可以保存不影响代码生成的结构化追踪信息，将需求、协议语义和业务代码位置放在同一份配置中：

```yaml
business:
  requirement_ref: "DEMO-REQ-001"
  category: display
  unit: enum
  default_value: 0
  value_semantics: "0=中文，1=English"
  owner: display-team
  verification_ref: "DEMO-TEST-001"
  notes: "修改后立即生效，并在掉电后保持。"
implementation:
  source_file: demo_settings.c
  source_symbol: g_demoLanguage
  module: display_settings
  notes: "使用单字节 EEPROM 保存。"
```

项目级 `project` 映射还支持 `description`、`source_file` 和 `source_handler`，用于标记配置对应的手写协议处理代码。这些字段会接受校验、显示在 GUI 中，并由 CSV 导入导出保留。

## 项目级配置

左侧导航提供四个独立入口：

- `项目设置`：输出路径、响应 CAN ID、发送函数和 C 代码引用；
- `命令定义`：读写命令字、载荷宽度和成功响应；
- `错误响应`：错误响应命令和错误码；
- `Hook 管理`：Hook 别名、C 函数、调用契约和用途说明。

这些项目级配置不会被 CSV 导入替换。命令定义使用 YAML 编辑区，使项目增加新命令时不需要升级 GUI。

## Hook 配置

Hook 可以使用旧版紧凑写法：

```yaml
hooks:
  read_indicator: Demo_Hook_ReadIndicator
```

也可以使用包含契约和说明的结构化定义：

```yaml
hooks:
  read_indicator:
    function: Demo_Hook_ReadIndicator
    contract: read
    description: "读取当前指示状态。"
```

支持的契约和调用签名：

- `read`：`uint32_t Hook(void)`；
- `write`：`bool Hook(uint32_t value)`；
- `transaction`：`bool Hook(uint8_t subindex, uint32_t value)`；
- `chunk_write`：`bool Hook(uint8_t subindex, const uint8_t payload[4])`；
- `generic`：兼容旧配置，不限制引用位置。

校验器会拒绝契约与调用位置不匹配的结构化 Hook。GUI 支持新增、重命名、删除、说明和修改契约；重命名会同步所有条目引用，删除被引用的 Hook 会清除引用并停用相关操作。条目检查器会按契约过滤候选 Hook，也可以在读取或写入字段旁直接创建并绑定。

当 `acknowledge_before_hook` 开启时，生成代码会先发送 ACK，再调用 Hook，并有意忽略 Hook 返回值。这适用于复位等可能不会返回的操作。

## CSV 导入导出

CSV 使用带 BOM 的 UTF-8 编码，兼容 Excel。`read`、`write`、`fields`、`buffer`、`business` 和 `implementation` 等嵌套配置使用 JSON 列保存。

导入时只替换 `objects` 协议清单，不修改项目级命令、错误码、Hook 和代码引用。导入会先校验完整配置，并可通过一次撤销恢复。缺少新增业务描述列的旧版 CSV 仍可导入。

## 生成控制

生成片段写入 `generator.output.fragment`。标量读写会直接生成；复杂状态、复位、跨模块操作等行为通过手写 Hook 分派。

可以在对象、条目、读取或写入层级使用 `enabled` 控制代码生成。关闭的条目仍保留在 YAML 协议清单中，并在 `cfggen list` 中显示为 `OFF`，因此规划中或产品专用条目不会丢失。

目标项目需要提供配置中引用的请求对象、发送函数、应用变量、存储函数和 Hook 实现。

## Windows EXE 打包

```powershell
python -m pip install -e ".[gui,exe]"
python packaging/build_exe.py
```

便携程序输出到 `dist/config-code-generator/`，发布 ZIP 输出到 `artifacts/config-code-generator-nightly-windows-x64.zip`。外部 `config/` 目录与 EXE 同级保存，因此协议配置可以直接编辑，并在软件更新时得到保留。

每次推送到 `main` 都会运行测试、构建 Windows x64 便携包、执行打包 smoke test，并更新 `nightly` 预发布中的 ZIP 和 `update-manifest.json`。

## 检查更新和自更新

About 页面提供完整的手动更新流程：检查 Nightly、下载更新包、校验文件大小与 SHA-256，然后确认安装。当前不会在启动时或后台自动检查，服务层只保留未来可选自动检查的接口。

Windows 使用独立的单文件更新器：等待主程序退出、替换便携运行文件、保留整个外部 `config/` 目录并启动新版。新版未能在超时内报告健康状态时，更新器会恢复旧运行目录并重新启动旧版。

ZIP 解压会拒绝目录穿越、符号链接、异常文件数量和超大解压体积。Nightly 使用 GitHub Actions `run_number` 作为单调递增构建号。

## 版本管理

手工版本号位于 `src/config_codegen/version.py` 的 `BASE_VERSION`。运行时版本格式为 `<基础版本>+g<8 位 commit>`，例如 `0.1.0+g1a2b3c4d`。

```powershell
cfggen --version
cfggen-gui --version
```

开发环境从 Git 读取 commit。EXE 构建会通过 PyInstaller runtime hook 嵌入 commit，并将相同版本写入 Windows 文件属性。发布新手工版本时只需修改 `BASE_VERSION`。
