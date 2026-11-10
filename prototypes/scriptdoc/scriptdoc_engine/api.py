# -*- coding: utf-8 -*-
"""
ScriptDoc 中二度检测 API（FastAPI）
====================================
启动：
  python -m uvicorn api:app --host 127.0.0.1 --port 8000
接口文档（Swagger）：
  http://127.0.0.1:8000/docs

示例请求：
  POST /api/analysis/chuuni
  {
    "scene_id": "act2_scene3",
    "scene_type": "daily",
    "character": {"name": "林默", "role_type": "protagonist"},
    "lines": [
      {"line_no": 34, "speaker": "林默", "text": "我的命运，终将在此终结！"}
    ],
    "semantic_by_line": {}
  }
"""
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from chuuni_engine import ChuuniRuleEngine
from script_input import parse_script

app = FastAPI(title="ScriptDoc 中二度检测 API", version="0.1.0")
engine = ChuuniRuleEngine()
share_page = Path(__file__).resolve().parents[1] / "share" / "index.html"


class Character(BaseModel):
    name: str
    role_type: str = Field(
        "protagonist",
        description="villain / protagonist / chuuni_character / ...",
    )


class Line(BaseModel):
    line_no: int
    speaker: str
    text: str
    kind: Literal["dialogue", "direction", "unassigned"] | None = None
    role_type: str | None = None


class AnalyzeRequest(BaseModel):
    scene_id: str
    scene_type: str = Field("daily", description="daily / climax / villain_entrance / ...")
    character: Character
    lines: list[Line]
    role_types: dict[str, str] = Field(default_factory=dict)
    semantic_by_line: dict[int, float] = Field(
        default_factory=dict,
        description="LLM 语义分（0-100），可选；缺省时引擎自动归一化权重",
    )


class AnalyzeResponse(BaseModel):
    scene_id: str
    act_title: str = ""
    scene_title: str = ""
    scene_type: str
    scene_score: float
    scene_level: str
    flagged_count: int
    per_line: list[dict]


class ScriptRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    scene_type: str = "daily"
    role_types: dict[str, str] = Field(default_factory=dict)


class ScriptResponse(BaseModel):
    scenes: list[AnalyzeResponse]


@app.get("/", include_in_schema=False)
def share_demo():
    return FileResponse(share_page)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analysis/chuuni", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest):
    scene = {
        "scene_id": req.scene_id,
        "scene_type": req.scene_type,
        "character": {"name": req.character.name, "role_type": req.character.role_type},
        "role_types": req.role_types,
        "lines": [_to_dict(l) for l in req.lines],
    }
    return engine.analyze_scene(scene, req.semantic_by_line)


@app.post("/api/analysis/script", response_model=ScriptResponse)
def analyze_script(req: ScriptRequest):
    scenes = parse_script(req.text)
    if not scenes:
        raise HTTPException(status_code=422, detail="请输入包含对白或舞台提示的剧本。")
    return {"scenes": [engine.analyze_scene({**scene, "scene_type": req.scene_type,
                                           "role_types": req.role_types}) for scene in scenes]}


def _to_dict(obj):
    """兼容 pydantic v1/v2。"""
    return obj.model_dump() if hasattr(obj, "model_dump") else obj.dict()
