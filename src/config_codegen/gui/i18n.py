from __future__ import annotations


STATUS_OPTIONS = (
    ("", "未设置"),
    ("planned", "规划中"),
    ("implemented", "已实现"),
    ("verified", "已验证"),
    ("deprecated", "已废弃"),
)

ACCESS_OPTIONS = (
    ("", "未配置"),
    ("read_only", "只读"),
    ("write_only", "只写"),
    ("read_write", "读写"),
)

KIND_OPTIONS = (
    ("", "未配置"),
    ("scalar", "标量"),
    ("bitfield", "位域"),
    ("hook", "自定义钩子"),
    ("action", "操作命令"),
    ("transaction_fields", "事务字段"),
    ("chunked_buffer", "分包缓冲区"),
)

KIND_DESCRIPTIONS = {
    "": "尚未选择实现类型。",
    "scalar": "直接读写单个变量，可配置数值范围、存储和写后处理。",
    "bitfield": "将多个布尔状态组合到一个整数的不同位中。",
    "hook": "调用手写 Hook 函数处理无法直接生成的读写逻辑。",
    "action": "执行复位、清零等带副作用且通常只写的操作。",
    "transaction_fields": "多个 SubIndex 组成一组字段，由 Hook 统一处理或提交。",
    "chunked_buffer": "将数组或字符串按固定字节数拆分到多个 SubIndex。",
}

HOOK_CONTRACT_OPTIONS = (
    ("read", "读取值"),
    ("write", "写入或操作"),
    ("transaction", "事务字段写入"),
    ("chunk_write", "分包缓冲区写入"),
)

HOOK_CONTRACT_DESCRIPTIONS = {
    "read": "uint32_t Hook(void)",
    "write": "bool Hook(uint32_t value)",
    "transaction": "bool Hook(uint8_t subindex, uint32_t value)",
    "chunk_write": "bool Hook(uint8_t subindex, const uint8_t payload[4])",
}


def option_label(options: tuple[tuple[str, str], ...], code: object) -> str:
    value = str(code or "")
    return dict(options).get(value, f"未知（{value}）")
