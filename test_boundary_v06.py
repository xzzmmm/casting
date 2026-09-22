# -*- coding: utf-8 -*-
"""CastingNuwa v0.6 边界回归测试（20 项）。

由第三方测试者的 v06_boundary_checks.py 适配为项目内长期回归：
- 在项目根运行，直接 `python test_boundary_v06.py` 或 `pytest test_boundary_v06.py`；
- 覆盖证据强约束、空画像拒绝、音视频成功回调、名单 upsert、同秒存档、
  推断/自述分级、LLM 提案校验、设定失效与拦截、会话隔离、原子导入等高风险边界。

真实 LLM 场景一律用可控替身（Fake）模拟，不消耗模型额度。
"""
import io
import json
import os
import pathlib
import sys
import traceback
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

BASE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))
os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.chdir(BASE)

import gradio  # noqa: E402,F401
import app  # noqa: E402
from src.models import (  # noqa: E402
    TraitScore, RoleCard, CastingGuide, ObservableRequirement,
)
from src.actor_models import (  # noqa: E402
    ActorProfile, ObservationRecord, AdjustmentResponse,
)
from src.matching_engine import (  # noqa: E402
    MatchingEngine, CastingReport, RoleCastingResult,
)
from src.llm_client import LLMClient, LLMServiceError  # noqa: E402
from src.actor_profiler import ActorProfiler  # noqa: E402
from src.multimodal_analyzer import MultimodalAnalyzer  # noqa: E402

try:
    import cv2  # noqa: E402
    CV2_VERSION = cv2.__version__
except Exception:  # noqa: BLE001
    CV2_VERSION = "not-installed"
try:
    import openai  # noqa: E402
    OPENAI_VERSION = openai.__version__
except Exception:  # noqa: BLE001
    OPENAI_VERSION = "not-installed"


class Fake:
    """可控 LLM 替身：返回固定 JSON，标记为非演示模式。"""
    is_mock_mode = False

    def __init__(self, result):
        self.result = result

    def chat_json(self, *a, **k):
        return self.result


ROLE = RoleCard(
    role_name="R",
    casting_guide=CastingGuide(observable_requirements=[
        ObservableRequirement(
            requirement="通过停顿表达犹豫",
            observable_signals=["停顿"],
            must_have=True,
        )
    ]),
)


def _declared_count_without_evidence():
    score = TraitScore.from_dict(
        {"score": 8, "evidence_count": 3, "evidence": [], "confidence": "高"}
    )
    return score.score is None


def _duplicate_evidence():
    score = TraitScore.from_dict(
        {"score": 8, "evidence_count": 2,
         "evidence": ["相同证据", "相同证据"], "confidence": "高"}
    )
    return score.score is None


def _out_of_range_trait_rejected():
    score = TraitScore.from_dict(
        {"score": 99, "evidence_count": 2, "evidence": ["一", "二"], "confidence": "高"}
    )
    return score.score is None


def _api_failure_no_mock():
    client = LLMClient()
    client._mock_mode = False
    client._demo_by_default = False

    def fail(**kw):
        raise RuntimeError("simulated offline failure")

    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=fail))
    )
    try:
        client.chat("", "")
        raised = False
    except LLMServiceError:
        raised = True
    return raised and not client.is_mock_mode


def _configured_key_missing_sdk():
    with patch("src.llm_client.HAS_OPENAI", False):
        client = LLMClient(api_key="dummy-test-key")
    return not client.is_mock_mode


def _empty_text_response():
    profile = ActorProfiler(Fake({})).profile_from_text(
        "测试材料", actor_name="A", max_retries=0
    )
    return profile is None or profile.analysis_status == "failed"


def _empty_multimodal_response():
    result = MultimodalAnalyzer(Fake({})).analyze(
        actor_name="A", text_material="材料", max_retries=0
    )
    return result.actor_profile.analysis_status == "failed"


def _multimodal_parse_failure_status():
    result = MultimodalAnalyzer(Fake({"_parse_error": "simulated"})).analyze(
        actor_name="A", text_material="材料", max_retries=0
    )
    return result.actor_profile.analysis_status == "failed"


def _media_success_callback(kind):
    state = app.AppState()
    setattr(
        state.actor_profiler,
        "profile_from_" + kind,
        lambda **kw: ActorProfile(actor_name="A"),
    )
    fn = getattr(app, "profile_from_" + kind + "_file")
    result = fn(state, "synthetic-file", "A", "")
    stored_once = state.actor_names().count("A") == 1
    return "✅" in result[-1] and stored_once


def _settings_invalidate_report():
    state = app.AppState()
    state.role_cards = [ROLE]
    state.casting_report = CastingReport(results=[
        RoleCastingResult(role_name="R", confirmed_actor_name="A",
                          confirmation_reason="old")
    ])
    result = app.save_settings(state, "新风格", "", "新必须项", "", False, False, "")
    return result[0].casting_report is None


def _text_actor_addition_preserves_previous():
    state = app.AppState()
    state.actor_profiles = [ActorProfile(actor_name="已有演员")]
    state.actor_profiler = SimpleNamespace(
        profile_from_text=lambda **kw: ActorProfile(actor_name=kw["actor_name"])
    )
    result = app.profile_actors(state, "【演员：新增演员】\n材料", "", "", "", "")
    return len(result[0].actor_profiles) == 2


def _two_sessions_same_second_save():
    s1 = app.AppState()
    s1.role_cards = [RoleCard(role_name="项目一")]
    s2 = app.AppState()
    s2.role_cards = [RoleCard(role_name="项目二")]
    with patch.object(app, "datetime") as mocked:
        mocked.now.return_value = datetime(2026, 9, 22, 12, 0, 0)
        mocked.side_effect = lambda *a, **k: datetime(*a, **k)
        path1, _ = app.save_project(s1)
        path2, _ = app.save_project(s2)
    first_owner = json.loads(
        pathlib.Path(path1).read_text(encoding="utf-8")
    )["roles"][0]["role_name"]
    return path1 != path2 and first_owner == "项目一"


def _inference_not_direct_support():
    actor = ActorProfile(actor_name="A", observations=[ObservationRecord(
        observed_behavior="自述擅长",
        possible_interpretation="可能善于停顿",
        evidence_type="推断",
        source="self_report",
        confidence="低",
    )])
    proposal = MatchingEngine(LLMClient()).match_one(ROLE, actor)
    return proposal.category == "needs_more_audition"


def _negated_signal():
    actor = ActorProfile(actor_name="A", observations=[
        ObservationRecord(observed_behavior="全程没有停顿")
    ])
    proposal = MatchingEngine(LLMClient()).match_one(ROLE, actor)
    return proposal.category != "priority_audition"


def _ineffective_retest_count():
    actor = ActorProfile(
        actor_name="A",
        adjustment_responses=[AdjustmentResponse(change_quality="无效")],
    )
    proposal = MatchingEngine(LLMClient()).match_one(ROLE, actor)
    return "0/1" in proposal.adjustment_note


def _llm_priority_without_evidence():
    engine = MatchingEngine(Fake({
        "category": "priority_audition",
        "actor_name": "不存在的演员",
        "reference_score": 150,
    }))
    proposal = engine.match_one(ROLE, ActorProfile(actor_name="A"))
    return (
        proposal.category != "priority_audition"
        and proposal.actor_name == "A"
        and 0 <= proposal.reference_score <= 100
    )


def _single_match_settings_gate():
    state = app.AppState()
    state.role_cards = [ROLE]
    state.actor_profiles = [ActorProfile(actor_name="A")]
    result = app.match_single(state, "R", "A")
    return "✅" not in result[-1]


def _session_objects_isolated():
    a = app.AppState()
    b = app.AppState()
    a.role_cards.append(ROLE)
    return len(b.role_cards) == 0


def _failed_import_atomic():
    state = app.AppState()
    state.script_text = "原剧本"
    state.role_cards = [ROLE]
    try:
        state.load_project_dict({"script_text": "错误存档", "roles": None})
    except Exception:  # noqa: BLE001
        pass
    return state.script_text == "原剧本"


CHECKS = [
    ("declared_count_without_evidence", _declared_count_without_evidence),
    ("duplicate_evidence", _duplicate_evidence),
    ("out_of_range_trait_rejected", _out_of_range_trait_rejected),
    ("api_failure_no_mock", _api_failure_no_mock),
    ("configured_key_missing_sdk", _configured_key_missing_sdk),
    ("empty_text_response", _empty_text_response),
    ("empty_multimodal_response", _empty_multimodal_response),
    ("multimodal_parse_failure_status", _multimodal_parse_failure_status),
    ("video_success_callback", lambda: _media_success_callback("video")),
    ("audio_success_callback", lambda: _media_success_callback("audio")),
    ("settings_invalidate_report", _settings_invalidate_report),
    ("text_actor_addition_preserves_previous", _text_actor_addition_preserves_previous),
    ("two_sessions_same_second_save", _two_sessions_same_second_save),
    ("inference_not_direct_support", _inference_not_direct_support),
    ("negated_signal", _negated_signal),
    ("ineffective_retest_count", _ineffective_retest_count),
    ("llm_priority_without_evidence", _llm_priority_without_evidence),
    ("single_match_settings_gate", _single_match_settings_gate),
    ("session_objects_isolated", _session_objects_isolated),
    ("failed_import_atomic", _failed_import_atomic),
]


def run():
    results = []
    for name, fn in CHECKS:
        try:
            passed = bool(fn())
            item = {"name": name, "passed": passed}
        except Exception as exc:  # noqa: BLE001
            item = {"name": name, "passed": False, "error": repr(exc),
                    "traceback": traceback.format_exc()}
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    return results


def test_boundary_suite():
    """pytest 入口：20 项边界必须全部通过。"""
    results = run()
    failed = [r["name"] for r in results if not r["passed"]]
    assert not failed, f"边界检查未通过：{failed}"


if __name__ == "__main__":
    results = run()
    versions = {
        "python": sys.version,
        "gradio": gradio.__version__,
        "openai": OPENAI_VERSION,
        "opencv": CV2_VERSION,
    }
    out_dir = BASE / "output"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "boundary_results.json").write_text(
        json.dumps({"versions": versions, "tests": results},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    passed = sum(r["passed"] for r in results)
    print("VERSIONS", versions)
    print(f"SUMMARY {passed}/{len(results)}")
    sys.exit(0 if passed == len(results) else 1)
