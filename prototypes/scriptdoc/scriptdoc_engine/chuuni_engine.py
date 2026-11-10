# -*- coding: utf-8 -*-
"""
ScriptDoc · 中二度检测规则引擎核心（骨架版）
================================================
分层设计：
  词汇层（规则）  句法层（规则）  语义层（LLM，骨架中以可选参数接入，不实装）
聚合：raw = min(100, Σ规则信号点值 + 语义分 × 0.3)
      （各信号点值与语义权重见 config.weights；未提供语义分时仅计规则点值）
校准：final = raw × calibration(role_type, scene_type)
输出：score / level / signals / suggestion

设计说明：
- 词汇层与句法层全部本地可复算，答辩可现场演示（不依赖网络与 LLM）。
- 词表、句式模板、阈值、校准系数全部来自 config/chuuni_config.json，可配置。
- 语义层（情绪反应比例失调 / 空转宣言 / 语域失配）由 LLM 子任务并行产出，
  通过 semantic 参数注入本引擎；本骨架不实现 LLM 调用。

运行：
  python cli.py          # 命令行演示
  python test_engine.py  # 单元测试
  python -m uvicorn api:app --port 8000   # 启动 API（另见 api.py）
"""
from __future__ import annotations

import json
import re
import sys
from bisect import bisect_left
from dataclasses import dataclass
from pathlib import Path

# Windows PowerShell 控制台中文输出
if sys.stdout and sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    sys.stdout.reconfigure(encoding="utf-8")

try:
    import warnings
    with warnings.catch_warnings():
        # jieba 0.42 内部正则存在无害的 SyntaxWarning，静默之
        warnings.simplefilter("ignore", SyntaxWarning)
        import jieba
        import jieba.posseg as pseg
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False


_STAGE_ONLY = re.compile(r"(?:【[^【】]+】|（[^（）]+）|\[[^\[\]]+\]|\([^()]+\))")
_LEADING_DELIVERY = re.compile(r"^\s*(?:（([^（）]+)）|\(([^()]+)\))\s*")
_INLINE_STAGE = re.compile(r"【([^【】]+)】")


def _line_kind(line: dict) -> str:
    text = line["text"].strip()
    if line.get("kind"):
        return line["kind"]
    if not text:
        return "unassigned"
    return "direction" if _STAGE_ONLY.fullmatch(text) else "dialogue"


def _spoken_text(text: str) -> tuple[str, list[str]]:
    notes = _INLINE_STAGE.findall(text)
    delivery = _LEADING_DELIVERY.match(text)
    if delivery:
        notes.insert(0, delivery[1] or delivery[2])
        text = text[delivery.end():]
    return _INLINE_STAGE.sub(" ", text).strip(), notes


def _cue(line: dict) -> dict:
    return {"line_no": line["line_no"], "speaker": line.get("speaker", ""), "text": line["text"]}


def _rehearsal_note(text: str, notes: list[str], context: dict, speaker: str) -> str:
    if notes:
        return f"按原文提示「{notes[0]}」试读，再听搭档接话。"
    if text.rstrip().endswith(("？", "?")):
        return "保留问句的停顿，给对方留出回答的空间。"
    if re.search(r"[！!]", text):
        return "对照前后句试读两遍，比较加重关键词和单纯提高音量的效果。"
    previous = context["previous"]
    if previous and previous["speaker"] not in ("", speaker):
        return "听完前一句再接话，试着让重音回应上一句的关键信息。"
    if context["next"]:
        return "从本句的具体动作或信息出发试读，并观察下一句怎样承接。"
    return "按自然语速试读，标出句内需要停顿或加重的地方。"


@dataclass
class Signal:
    type: str          # wordlist_hit / absolutism / exclamation / abstract_heavy / template_hit / long_line
    evidence: list     # 命中词 / 模板标签 / 数值说明
    weight: float = 1.0


def load_config(path: str | Path | None = None) -> dict:
    """加载可配置项（词表 / 模板 / 阈值 / 校准 / 分级）。"""
    p = Path(path) if path else Path(__file__).parent / "config" / "chuuni_config.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class ChuuniRuleEngine:
    """中二度规则引擎：detect() 产出信号，score() 聚合，calibration() 情境校准。"""

    # 降档建议模板（输出端）
    SUGGESTIONS = {
        "wordlist_hit": "大词换小词：把「{ev}」换成具体事件或口语词",
        "absolutism": "绝对化表述降级：去掉「永远/一切」类全称词",
        "exclamation": "情绪降档：感叹号改句号，极端情绪词降级",
        "abstract_heavy": "抽象词换成具体指称，落回可见的细节",
        "template_hit": "宣言句式：改写成具体动作或细节，或插入对方打断",
        "long_line": "长哲理句拆分，或加对话打断，打破演讲腔",
    }

    def __init__(self, config: dict | None = None):
        self.cfg = config or load_config()
        self.wordlist = self.cfg["wordlist"]
        self.all_words = [w for words in self.wordlist.values() for w in words]
        self.templates = [(t["pattern"], t["label"]) for t in self.cfg["templates"]]
        self.th = self.cfg["thresholds"]
        self.abstract_words = set(self.cfg["abstract_words"])

    # ---------------- 检测（词汇层 + 句法层）----------------
    def detect(self, text: str) -> tuple[list[Signal], list[Signal]]:
        """返回 (词汇层信号, 句法层信号)。纯本地、可复算。"""
        lex, syn = [], []

        # ---- 词汇层 ----
        hits = [w for w in self.all_words if w in text]
        if len(hits) >= self.th["hit_per_line"]:
            lex.append(Signal("wordlist_hit", hits))

        abs_hits = [w for w in self.th["absolutism_words"] if w in text]
        if abs_hits:
            lex.append(Signal("absolutism", abs_hits))

        ex_ratio = self._exclaim_ratio(text)
        if ex_ratio > self.th["exclaim_ratio"]:
            lex.append(Signal("exclamation", [f"感叹号占比 {ex_ratio:.0%}"]))

        ab_ratio = self._abstract_ratio(text)
        if ab_ratio is not None and ab_ratio > self.th["abstract_ratio"]:
            lex.append(Signal("abstract_heavy", [f"抽象词/名词比 {ab_ratio:.2f}"]))

        # ---- 句法层 ----
        for pattern, label in self.templates:
            if re.search(pattern, text):
                syn.append(Signal("template_hit", [label]))

        if len(text) > self.th["long_line"] and not text.rstrip().endswith(("？", "?")):
            syn.append(Signal("long_line", [f"句长 {len(text)} 字"]))

        return lex, syn

    def _exclaim_ratio(self, text: str) -> float:
        endings = re.findall(r"[。！？!?]+|\.+(?=\s|$)", text)
        exclaims = sum(any(mark in ending for mark in "！!") for ending in endings)
        return exclaims / len(endings) if endings else 0.0

    def _abstract_ratio(self, text: str) -> float | None:
        """抽象名词占比 = 命中抽象词数 / 总名词数；无 jieba 时返回 None（跳过该信号）。"""
        if not HAS_JIEBA:
            return None
        tagged = [(w.word, w.flag) for w in pseg.cut(text)]
        noun_count = sum(1 for _, f in tagged if f.startswith("n"))
        if noun_count == 0:
            return 0.0
        abstract_hits = sum(1 for w, _ in tagged if w in self.abstract_words)
        return abstract_hits / noun_count

    # ---------------- 聚合与校准 ----------------
    def score(self, lexical: list[Signal], syntax: list[Signal],
              semantic: float | None = None) -> dict:
        """累加点值制：规则信号按 config.weights 计点，LLM 语义分贡献上限 30 分。
        raw = min(100, Σ规则点值 + 语义分×0.3)；语义分缺失时仅计规则点值。
        所有点值可在 config 中调整（对应 5.1⑧ 校准计划）。"""
        w = self.cfg["weights"]
        rule_pts = sum(w.get(s.type, 0) for s in lexical + syntax)
        semantic_pts = w.get("semantic", 0.3) * semantic if semantic is not None else 0.0
        raw = min(100.0, rule_pts + semantic_pts)
        return {"rule_points": round(rule_pts, 1),
                "semantic_points": round(semantic_pts, 1),
                "raw": round(raw, 1)}

    def calibration(self, role_type: str, scene_type: str) -> float:
        """情境校准：中二设定角色豁免 > 反派/高潮容忍 > 日常从严。"""
        c = self.cfg["calibration"]
        if role_type == "chuuni_character":
            return c["chuuni_character"]
        if role_type == "villain" or scene_type in c["climax_scene_types"]:
            return c["villain_or_climax"]
        if scene_type == "daily":
            return c["daily"]
        return c["default"]

    def level_of(self, score: float) -> tuple[str, str]:
        for lv in self.cfg["levels"]:
            if score <= lv["max"]:
                return lv["label"], lv["action"]
        lv = self.cfg["levels"][-1]
        return lv["label"], lv["action"]

    def _suggest(self, signals: list[Signal]) -> list[str]:
        out = []
        for s in signals:
            tpl = self.SUGGESTIONS.get(s.type)
            if tpl:
                ev = "、".join(s.evidence[:3])
                out.append(tpl.format(ev=ev))
        return out[:3]

    # ---------------- 对外接口 ----------------
    def analyze_line(self, line: dict, scene_type: str = "daily",
                     role_type: str = "protagonist",
                     semantic: float | None = None, *, context: dict | None = None) -> dict:
        """分析单句台词 → {line_no, speaker, text, score, level, signals, suggestion}"""
        kind = _line_kind(line)
        context = context or {"previous": None, "next": None, "stage_directions": []}
        result = {**_cue(line), "kind": kind, "context": context}
        if kind != "dialogue":
            note = "保留为舞台提示，供前后对白排练时参照。" if kind == "direction" else "请先确认这行的说话人或用途。"
            return {**result, "score": None, "level": "待核对" if kind == "unassigned" else "舞台提示",
                    "level_action": note, "signals": [], "suggestion": [], "rehearsal_note": note}

        speech, notes = _spoken_text(line["text"])
        lexical, syntax = self.detect(speech)
        parts = self.score(lexical, syntax, semantic)
        multiplier = self.calibration(role_type, scene_type)
        final = round(min(100.0, parts["raw"] * multiplier), 1)
        level, action = self.level_of(final)
        signals = lexical + syntax
        return {**result, "spoken_text": speech, "role_type": role_type, "score": final,
                "score_basis": {**parts, "scene_type": scene_type, "multiplier": multiplier},
                "level": level, "level_action": action,
                "signals": [{"type": s.type, "evidence": s.evidence} for s in signals],
                "suggestion": self._suggest(signals),
                "rehearsal_note": _rehearsal_note(speech, notes, context, result["speaker"])}

    def analyze_scene(self, scene: dict, semantic_by_line: dict[int, float] | None = None) -> dict:
        """分析整场 → {scene_id, scene_score, scene_level, per_line}"""
        semantic_by_line = semantic_by_line or {}
        source = scene["lines"]
        kinds = [_line_kind(line) for line in source]
        spoken = [index for index, kind in enumerate(kinds) if kind == "dialogue"]
        character = scene.get("character") or {}
        role_types = scene.get("role_types") or {}
        scene_type = scene.get("scene_type", "daily")
        lines = []
        for index, line in enumerate(source):
            before = bisect_left(spoken, index)
            after = before + (kinds[index] == "dialogue")
            previous = spoken[before - 1] if before else None
            following = spoken[after] if after < len(spoken) else None
            start = max(0 if previous is None else previous + 1, index - 3)
            end = min(len(source) if following is None else following, index + 4)
            context = {
                "previous": _cue(source[previous]) if previous is not None else None,
                "next": _cue(source[following]) if following is not None else None,
                "stage_directions": [
                    {"line_no": source[i]["line_no"], "text": source[i]["text"]}
                    for i in range(start, end) if i != index and kinds[i] == "direction"
                ],
            }
            speaker = line.get("speaker", "")
            default_role = character.get("role_type", "protagonist") if character.get("name") in (None, "", speaker) else "protagonist"
            lines.append(self.analyze_line(
                line,
                scene_type=scene_type,
                role_type=line.get("role_type") or role_types.get(speaker, default_role),
                semantic=semantic_by_line.get(line["line_no"]),
                context=context,
            ))
        scores = [line["score"] for line in lines if line["score"] is not None]
        scene_score = round(sum(scores) / len(scores), 1) if scores else 0.0
        level, _ = self.level_of(scene_score)
        flagged = sum(1 for line in lines if line["score"] is not None and line["level"] != "正常")
        return {"scene_id": scene.get("scene_id"), "act_title": scene.get("act_title", ""),
                "scene_title": scene.get("scene_title", ""), "scene_type": scene_type, "scene_score": scene_score,
                "scene_level": level, "flagged_count": flagged, "per_line": lines}
