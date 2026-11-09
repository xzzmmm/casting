# 模块 A：LLM 提示词模板与 JSON Schema

用于 W3-W5 实现「转写 → 结构化日志」链路。内容与 `docs/data_schema.md`、后端 `app/services/llm_struct.py` 保持一致。

## 1. 系统提示词（SYSTEM_PROMPT）

```text
你是莱恩戏剧社的排练记录助手，负责把排练转写整理成结构化日志。
规则：
1. 只输出一个合法 JSON 数组，不要输出解释文字、Markdown 或代码块标记。
2. 每个条目字段必须严格符合给定的 JSON Schema，未定义的字段不要输出。
3. 条目按时间先后排列，ts_start 与 ts_end 取转写片段时间戳；同一主题的连续讨论合并为一条，避免碎片化。
4. item_type 只能取：舞台、道具、灯光、音效、表演、其他。
5. status 只能取：已确定（结论明确、已拍板）或 待解决（仍需跟进）。
6. summary 用简洁中文概括本条要点；decision 记录结论或下一步动作，没有则为空字符串。
7. speakers 是发言者列表，actors 是条目涉及的演员，tags 是 2 到 5 个关键词。
8. 转写中听不清或缺失的人名按原文保留，绝不编造。
```

## 2. 用户提示词模板（USER_PROMPT）

```text
请把以下带时间戳的排练转写整理为符合 JSON Schema 的结构化日志数组。

排练信息：剧目《{play}》，第 {rehearsal_no} 次排练，日期 {date}

输出 Schema：
{schema}

排练转写：
{transcript}
```

变量说明：

| 变量 | 来源 |
| --- | --- |
| `{play}` / `{rehearsal_no}` / `{date}` | 上传时填写的排练场次信息 |
| `{schema}` | 见第 3 节，用 `json.dumps(..., ensure_ascii=False)` 序列化 |
| `{transcript}` | ASR 输出，每行形如 `[12.5-30.2] 导演：...` |

## 3. JSON Schema（机器可校验）

独立文件：`docs/llm_output_schema.json`。核心结构：

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "required": [
      "ts_start", "ts_end", "item_type", "speakers",
      "summary", "decision", "status", "actors", "tags"
    ],
    "properties": {
      "ts_start":  { "type": "number", "minimum": 0 },
      "ts_end":    { "type": "number", "minimum": 0 },
      "item_type": { "type": "string", "enum": ["舞台", "道具", "灯光", "音效", "表演", "其他"] },
      "speakers":  { "type": "array", "items": { "type": "string" } },
      "summary":   { "type": "string", "minLength": 1 },
      "decision":  { "type": "string" },
      "status":    { "type": "string", "enum": ["已确定", "待解决"] },
      "actors":    { "type": "array", "items": { "type": "string" } },
      "tags":      { "type": "array", "items": { "type": "string" } }
    },
    "additionalProperties": false
  }
}
```

## 4. 输出示例

```json
[
  {
    "ts_start": 130.5,
    "ts_end": 156.0,
    "item_type": "表演",
    "speakers": ["导演"],
    "summary": "第二幕开场，甲的情绪转折不够，重音应放在“我早就知道”上",
    "decision": "明天再走一遍开场，重点练重音",
    "status": "待解决",
    "actors": ["甲"],
    "tags": ["台词", "情绪"]
  },
  {
    "ts_start": 210.0,
    "ts_end": 224.5,
    "item_type": "舞台",
    "speakers": ["导演", "舞美"],
    "summary": "确定第三幕椅子摆放：舞台右侧两张，左侧一张",
    "decision": "舞美下周一前布置到位",
    "status": "已确定",
    "actors": [],
    "tags": ["道具布置"]
  },
  {
    "ts_start": 305.2,
    "ts_end": 318.0,
    "item_type": "灯光",
    "speakers": ["灯光师"],
    "summary": "Cue 5 进场太早，需在台词最后一句之后起",
    "decision": "灯光组调整 Cue 5 触发点",
    "status": "待解决",
    "actors": [],
    "tags": ["灯光", "Cue"]
  }
]
```

## 5. 接入与调用建议

1. **参数**：`temperature=0`（保证结构化稳定）；`max_tokens` 按转写长度放大（约转写字数 × 1.5 并留余量）。
2. **分段策略**：转写超过约 6000 字时按幕/场切段，逐段结构化后合并，避免超长截断。
3. **结果校验**：返回后用 JSON Schema 校验；失败时把错误回传给模型自动重试（最多 2 次）；仍失败则标记该排练为待人工复核，原始转写落盘到 `data/review_queue/`，不中断整条管线、不让坏数据直接入库。
4. **人工确认**：入库前保留「一键确认 / 修改」入口（后端 `PATCH /api/logs/{item_id}` 已预留）。
5. **隐私**：排练内容属社团内部资料，优先选用不留存数据的 API 或本地模型（方案书 4.3 节）。
