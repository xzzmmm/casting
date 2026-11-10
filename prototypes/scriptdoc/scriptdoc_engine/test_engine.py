# -*- coding: utf-8 -*-
"""
规则引擎单元测试：python test_engine.py
========================================
零第三方测试依赖（纯 assert）；API 冒烟测试在缺 httpx 时自动跳过。
"""
import sys

from chuuni_engine import ChuuniRuleEngine
from script_input import parse_script

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


def test_script_review():
    text = "\n".join(("编剧：合成示例", "第一幕第一场：门厅", "阿 青：（低声）你要去哪儿？",
                      "【灯光渐暗！】", "小林：我的命运，终将在此终结！", "等待进一步确认",
                      "第二场", "阿青：我们从这里开始。"))
    scenes = parse_script(text)
    first, second = scenes[-2:]
    result = engine.analyze_scene({**first, "role_types": {"小林": "villain"}})
    question, direction, reply, unassigned = result["per_line"]
    check("中文幕场标题与原文行号保留",
          first["act_title"] == "第一幕" and second["scene_title"] == "第二场" and question["line_no"] == 3)
    check("相邻对白跳过舞台提示，保留前后线索",
          question["context"]["next"]["speaker"] == "小林"
          and reply["context"]["previous"]["speaker"] == "阿青"
          and reply["context"]["stage_directions"][0]["line_no"] == 4)
    check("舞台提示与待核对行不参与场景评分",
          direction["kind"] == "direction" and unassigned["kind"] == "unassigned"
          and direction["score"] is None and unassigned["score"] is None
          and result["scene_score"] == round((question["score"] + reply["score"]) / 2, 1))
    check("语气提示保留原文，评分只计算对白",
          "低声" in question["rehearsal_note"] and question["spoken_text"] == "你要去哪儿？")
    check("角色校准按说话人应用",
          question["score_basis"]["multiplier"] == 1.3 and reply["score_basis"]["multiplier"] == 0.6)
    check("下一场独立建立对白上下文", engine.analyze_scene(second)["per_line"][0]["context"]["previous"] is None)
    lex, _ = engine.detect("快走！我随后来。把门带上。我们在门口见。")
    check("感叹比例包含句号，避免多句对白误判", all(signal.type != "exclamation" for signal in lex))


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
    r = client.post("/api/analysis/script", json={"text": "第一场\n甲：你还好吗？\n乙：我没事。"})
    check("API 冒烟：剧本入口返回角色与接话提示",
          r.status_code == 200 and r.json()["scenes"][0]["per_line"][0]["context"]["next"]["speaker"] == "乙")


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
    test_script_review()
    test_api_smoke()
    print(f"\n共 {passed} 项通过")
