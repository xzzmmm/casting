"""Conservative structure detection for plain-text rehearsal scripts."""
from __future__ import annotations

import re


_NUMBER = r"[0-9０-９零〇一二三四五六七八九十百两兩]+"
_ZH_ACT = rf"第\s*{_NUMBER}\s*幕"
_ZH_SCENE = rf"(?:第\s*{_NUMBER}\s*[场場]|[场場](?:次|景)\s*{_NUMBER}|序幕|尾[声聲]|楔子)"
_EN_NUMBER = r"(?:[0-9]+[A-Z]?|[IVXLCDM]+|ONE|TWO|THREE|FOUR|FIVE)"
_ACT = rf"(?:{_ZH_ACT}|ACT\s+{_EN_NUMBER})"
_SCENE = rf"(?:{_ZH_SCENE}|SCENE\s+{_EN_NUMBER})"
_HEADING_END = r"(?:$|[\s:：.．、—–-])"
_ACT_SCENE_RE = re.compile(rf"^({_ACT})[\s,，.．·、:：—–-]*({_SCENE}){_HEADING_END}", re.I)
_ACT_RE = re.compile(rf"^{_ACT}{_HEADING_END}", re.I)
_SCENE_RE = re.compile(rf"^{_SCENE}{_HEADING_END}", re.I)
_SLUG_RE = re.compile(r"^\.?\s*(?:INT\.?/EXT|EXT\.?/INT|INT|EXT|I/E)\.(?=\s|$)", re.I)
_MARKDOWN_HEADING_RE = re.compile(r"^#{1,6}\s+")

_CAST_RE = re.compile(
    r"^(?:剧中人物|劇中人物|人物表|角色表|演员表|演員表|CAST(?: LIST)?|CHARACTERS|ROLES|DRAMATIS PERSONAE)\s*[:：]?$",
    re.I,
)
_METADATA_TAGS = {
    "编剧", "編劇", "作者", "导演", "導演", "改编", "改編", "翻译", "翻譯", "制片", "製片",
    "剧名", "劇名", "标题", "標題", "版本", "日期", "时间", "時間", "地点", "地點", "背景",
    "简介", "簡介", "梗概", "剧情简介", "劇情簡介", "备注", "備註", "说明", "說明", "场景", "場景",
    "剧中人物", "劇中人物", "人物", "角色", "演员", "演員", "人物表", "角色表", "演员表", "演員表",
    "author", "writer", "written by", "director", "adapted by", "title", "version", "draft", "date", "time",
    "location", "setting", "summary", "synopsis", "note", "notes", "cast", "cast list", "characters",
    "scene", "act", "chapter", "roles",
}
_DIRECTION_TAG_RE = re.compile(
    r"^(?:舞台(?:提示|指示|动作|動作)|走位|动作|動作|灯光|燈光|音效|音响|音響|音乐|音樂|"
    r"布景|布光|投影|字幕|大屏幕|舞美|道具|LX|SFX|FX|SOUND|MUSIC|LIGHTS?|CURTAIN|PROJECTION|STAGE DIRECTION)"
    r"(?:\s*(?:Q\s*)?[0-9０-９]+[A-Z]?)?\s*[:：]",
    re.I,
)
_DIRECTION_RE = re.compile(
    r"^(?:BLACKOUT|FADE (?:IN|OUT)|LIGHTS? (?:UP|DOWN|FADE(?: OUT)?)|CURTAIN (?:UP|DOWN)|"
    r"灯光(?:渐暗|渐亮|全灭)|燈光(?:漸暗|漸亮|全滅)|全黑|黑场|黑場)[.!。！]?$",
    re.I,
)
_BRACKETED_RE = re.compile(r"^(?:【[^】]*】|（[^）]*）|\[[^\]]*\]|\([^)]*\))\s*")
_SPEAKER_RE = re.compile(r"^(?P<label>[^:：]+?)\s*[:：]\s*(?P<text>.*)$")
_HAN_NAME_RE = re.compile(r"[\u3400-\u9fff]{1,8}")
_EN_NAME_RE = re.compile(r"[A-Z][A-Za-z'’\-]*\.?(?:\s+[A-Z][A-Za-z'’\-]*\.?){0,3}")
_LABEL_ASIDE_RE = re.compile(r"\s*(?:\([^)]*\)|（[^）]*）)$")
_REPORTED_SPEECH_RE = re.compile(r"^[我你他她它咱](?:.*(?:说|說|想|问|問|道|喊|叫|答|觉得|覺得))$")


def _without_directions(text: str) -> str:
    """Remove only leading, explicitly bracketed performance notes."""
    while match := _BRACKETED_RE.match(text):
        text = text[match.end():]
    return text


def _speaker_name(label: str) -> str | None:
    name = " ".join(_LABEL_ASIDE_RE.sub("", label).split())
    squeezed = name.replace(" ", "")
    if name.casefold() in _METADATA_TAGS or squeezed in _METADATA_TAGS:
        return None
    if _HAN_NAME_RE.fullmatch(squeezed) and not _REPORTED_SPEECH_RE.fullmatch(squeezed):
        return squeezed
    if len(name) <= 40 and _EN_NAME_RE.fullmatch(name):
        return name
    return None


def parse_script(text: str) -> list[dict]:
    """Split headings and mark spoken, stage-direction, and unresolved lines.

    Dialogue requires an explicit speaker label and nonempty speech. Blank
    lines and headings are not scored. Every returned line keeps its original
    one-based text line number, including unassigned credits and cast entries.
    """
    scenes: list[dict] = []
    lines: list[dict] = []
    canonical_names: dict[str, str] = {}
    act_title = scene_title = ""
    in_cast = cast_has_rows = False

    def finish_scene() -> None:
        if lines:
            index = len(scenes) + 1
            scenes.append({
                "scene_id": f"scene_{index}", "act_title": act_title,
                "scene_title": scene_title or f"未分场 {index}", "lines": lines.copy(),
            })
            lines.clear()

    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip().lstrip("\ufeff").strip()
        if not line:
            if cast_has_rows:
                in_cast = cast_has_rows = False
            continue

        heading = _MARKDOWN_HEADING_RE.sub("", line)
        if match := _ACT_SCENE_RE.match(heading):
            finish_scene()
            act_title, scene_title = match[1], heading[match.start(2):]
            in_cast = cast_has_rows = False
            continue
        if _ACT_RE.match(heading):
            finish_scene()
            act_title, scene_title = heading, ""
            in_cast = cast_has_rows = False
            continue
        if _SCENE_RE.match(heading) or _SLUG_RE.match(heading):
            finish_scene()
            scene_title = heading
            in_cast = cast_has_rows = False
            continue

        speaker, content, kind = "", line, "unassigned"
        if _CAST_RE.fullmatch(line):
            in_cast, cast_has_rows = True, False
        elif (_DIRECTION_TAG_RE.match(line) or _DIRECTION_RE.fullmatch(line)
              or not _without_directions(line)):
            kind = "direction"
            in_cast = cast_has_rows = False
        elif in_cast:
            cast_has_rows = True
        elif match := _SPEAKER_RE.fullmatch(line):
            name = _speaker_name(match["label"])
            if name:
                if _without_directions(match["text"]):
                    speaker = canonical_names.setdefault(name.casefold(), name)
                    content, kind = match["text"], "dialogue"
                elif match["text"]:
                    kind = "direction"

        lines.append({"line_no": line_no, "speaker": speaker, "text": content, "kind": kind})

    finish_scene()
    return scenes
