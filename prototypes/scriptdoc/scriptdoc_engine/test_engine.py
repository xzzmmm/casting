# -*- coding: utf-8 -*-
"""
规则引擎单元测试：python test_engine.py
========================================
零第三方测试依赖（纯 assert）；API 冒烟测试在缺 httpx 时自动跳过。
"""
import sys

from chuuni_engine import ChuuniRuleEngine

if sys.stdout and sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    sys.stdout.reconfigure(encoding="utf-8")

engine = ChuuniRuleEngine()
passed = 0


def check(name: str, cond: bool):
    global passed
    assert cond, f"FAIL: {name}"
    passed += 1
    print(f"  PASS  {name}")


def test_wordlist_and_template():
    lex, syn = engine.detect("我的命运，终将在此终结！")
    check("词汇层命中 wordlist_hit（命运+终结）",
          any(s.type == "wordlist_hit" and {"命运", "终结"} <= set(s.evidence) for s in lex))
    check("句法层命中 template_hit（命运……终结）",
          any(s.type == "template_hit" for s in syn))


def test_clean_daily_lines():
    for t in ["这事，你不能再瞒了。", "行，那晚饭你请。"]:
        lex, syn = engine.detect(t)
        check(f"日常台词零信号：{t}", len(lex) + len(syn) == 0)


def test_exclamation():
    lex, _ = engine.detect("你竟敢背叛我！！")
    check("感叹号信号（占比 100%）", any(s.type == "exclamation" for s in lex))


def test_template_forms():
    cases = [
        "我是被黑暗选中的人",
        "我即是毁灭",
        "给我记住！",
        "这场闹剧，到此为止了",
        "这就是我的觉悟！",
        "感受痛苦吧",
        "世界不过是弱者的牢笼",
        "伪善什么的最讨厌了",
        "你以为我会原谅你？太天真了",
    ]
    for t in cases:
        _, syn = engine.detect(t)
        check(f"模板命中：{t}", any(s.type == "template_hit" for s in syn))


def test_absolutism():
    lex, _ = engine.detect("你必须永远服从我！")
    check("绝对化词信号", any(s.type == "absolutism" for s in lex))


def test_long_line():
    _, syn = engine.detect("所谓命运不过是弱者为自己寻找的借口而我早已超越了这一切凡俗的桎梏并且凌驾于所有规则之上")
    check("超长哲理句信号（>40 字非问句）", any(s.type == "long_line" for s in syn))


def test_calibration():
    line = {"line_no": 1, "speaker": "A", "text": "我的命运，终将在此终结！"}
    daily = engine.analyze_line(line, scene_type="daily", role_type="protagonist")
    climax = engine.analyze_line(line, scene_type="villain_entrance", role_type="villain")
    check("校准：反派+高潮场景分数更低", climax["score"] < daily["score"])
    check("校准：分数不为负且不超 100", 0 <= daily["score"] <= 100)


def test_calibration_chuuni_exemption():
    # 回归：中二设定角色在 daily 场景也必须豁免（曾因判断顺序被 daily ×1.3 抢先）
    line = {"line_no": 1, "speaker": "A", "text": "我的命运，终将在此终结！"}
    normal = engine.analyze_line(line, scene_type="daily", role_type="protagonist")
    chuuni = engine.analyze_line(line, scene_type="daily", role_type="chuuni_character")
    check("校准：中二设定角色豁免（分数显著低于日常主角）", chuuni["score"] < normal["score"] * 0.6)


def test_levels():
    check("级别边界 <30 → 正常", engine.level_of(20)[0] == "正常")
    check("级别边界 60-85 → 明显中二", engine.level_of(70)[0] == "明显中二")
    check("级别边界 ≥85 → 严重", engine.level_of(90)[0] == "严重")


def test_suggestion_present():
    r = engine.analyze_line({"line_no": 1, "speaker": "A", "text": "我的命运，终将在此终结！"})
    check("命中台词带降档建议", len(r["suggestion"]) >= 1)


def test_api_smoke():
    try:
        from fastapi.testclient import TestClient
        from api import app
    except ImportError:
        print("  SKIP  API 冒烟（缺 httpx，可 pip install httpx 后重跑）")
        return
    client = TestClient(app)
    payload = {
        "scene_id": "s1",
        "scene_type": "daily",
        "character": {"name": "林默", "role_type": "protagonist"},
        "lines": [{"line_no": 1, "speaker": "林默", "text": "我的命运，终将在此终结！"}],
        "semantic_by_line": {},
    }
    r = client.post("/api/analysis/chuuni", json=payload)
    check("API 冒烟：200 且含 per_line", r.status_code == 200 and "per_line" in r.json())
    check("API 冒烟：健康检查", client.get("/health").json()["status"] == "ok")


if __name__ == "__main__":
    print("ScriptDoc 规则引擎 · 单元测试\n")
    test_wordlist_and_template()
    test_clean_daily_lines()
    test_exclamation()
    test_template_forms()
    test_absolutism()
    test_long_line()
    test_calibration()
    test_calibration_chuuni_exemption()
    test_levels()
    test_suggestion_present()
    test_api_smoke()
    print(f"\n共 {passed} 项通过")
