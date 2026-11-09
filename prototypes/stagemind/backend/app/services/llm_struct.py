"""LLM 结构化服务：转写文本 -> 结构化日志条目。

校验与容错策略：
1. 调用 LLM 返回原始文本，先剥离 markdown 代码块标记再解析 JSON。
2. 用 OUTPUT_SCHEMA 校验；失败时将错误回传给模型并自动重试，最多 MAX_STRUCTURE_RETRY 次。
3. 重试仍失败则标记需人工复核（StructureResult.needs_manual_review），不抛异常、不中断整条管线。

提示词与 JSON Schema 与 docs/llm_struct_prompt.md、docs/llm_output_schema.json 保持一致。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from jsonschema import ValidationError, validate

from app.core.schemas import LogItemCreate
from app.services import llm_client
from app.services.asr import TranscriptionSegment

MAX_STRUCTURE_RETRY = 2

SYSTEM_PROMPT = """你是莱恩戏剧社的排练记录助手，负责把排练转写整理成结构化日志。
规则：
1. 只输出一个合法 JSON 数组，不要输出解释文字、Markdown 或代码块标记。
2. 每个条目字段必须严格符合给定的 JSON Schema，未定义的字段不要输出。
3. 条目按时间先后排列，ts_start 与 ts_end 取转写片段时间戳；同一主题的连续讨论合并为一条，避免碎片化。
4. item_type 只能取：舞台、道具、灯光、音效、表演、其他。
5. status 只能取：已确定（结论明确、已拍板）或 待解决（仍需跟进）。
6. summary 用简洁中文概括本条要点；decision 记录结论或下一步动作，没有则为空字符串。
7. speakers 是发言者列表，actors 是条目涉及的演员，tags 是 2 到 5 个关键词。
8. 转写中听不清或缺失的人名按原文保留，绝不编造。"""

OUTPUT_SCHEMA: dict = {
    "type": "array",
    "items": {
        "type": "object",
        "required": [
            "ts_start", "ts_end", "item_type", "speakers",
            "summary", "decision", "status", "actors", "tags",
        ],
        "properties": {
            "ts_start": {"type": "number", "minimum": 0},
            "ts_end": {"type": "number", "minimum": 0},
            "item_type": {"type": "string", "enum": ["舞台", "道具", "灯光", "音效", "表演", "其他"]},
            "speakers": {"type": "array", "items": {"type": "string"}},
            "summary": {"type": "string", "minLength": 1},
            "decision": {"type": "string"},
            "status": {"type": "string", "enum": ["已确定", "待解决"]},
            "actors": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class StructureResult:
    """一次结构化尝试的产出：成功条目、是否需要人工复核及错误信息。"""

    items: list[LogItemCreate] = field(default_factory=list)
    needs_manual_review: bool = False
    error: str | None = None


class LogStructurer:
    """把转写片段交给大模型，产出结构化日志条目。"""

    def structure(
        self,
        transcript: list[TranscriptionSegment],
        play: str = "未命名剧目",
        rehearsal_no: int = 1,
        date: str = "",
    ) -> StructureResult:
        """调用 LLM 并做校验重试，返回结构化结果（不抛异常）。"""
        prompt = self.build_prompt(transcript, play, rehearsal_no, date)
        last_error: str | None = None

        for attempt in range(MAX_STRUCTURE_RETRY + 1):
            raw = llm_client.call_llm_api(prompt, SYSTEM_PROMPT)
            payload = llm_client.extract_json_from_text(raw)
            try:
                data = json.loads(payload)
                validate(instance=data, schema=OUTPUT_SCHEMA)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                if attempt < MAX_STRUCTURE_RETRY:
                    prompt = self._repair_prompt(prompt, last_error)
                    continue
                return StructureResult(needs_manual_review=True, error=last_error)
            return StructureResult(
                items=[LogItemCreate(**item) for item in data]
            )

        return StructureResult(needs_manual_review=True, error=last_error)

    @staticmethod
    def _repair_prompt(prompt: str, error: str) -> str:
        """把校验错误回传给模型，要求其修正后重新输出。"""
        return (
            f"{prompt}\n\n"
            f"上次输出未通过校验，错误如下：\n{error}\n"
            "请修正后仅输出符合 Schema 的 JSON 数组，不要任何额外文字。"
        )

    @staticmethod
    def build_prompt(
        transcript: list[TranscriptionSegment],
        play: str = "未命名剧目",
        rehearsal_no: int = 1,
        date: str = "",
    ) -> str:
        """构造提交给 LLM 的用户提示词：排练信息 + 时间戳文本 + 输出 Schema。"""
        lines = "\n".join(
            f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}" for seg in transcript
        )
        schema_text = json.dumps(OUTPUT_SCHEMA, ensure_ascii=False, indent=2)
        return (
            "请把以下带时间戳的排练转写整理为符合 JSON Schema 的结构化日志数组。\n\n"
            f"排练信息：剧目《{play}》，第 {rehearsal_no} 次排练，日期 {date}\n\n"
            f"输出 Schema：\n{schema_text}\n\n"
            f"排练转写：\n{lines}"
        )
