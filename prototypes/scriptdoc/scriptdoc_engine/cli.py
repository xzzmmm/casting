# -*- coding: utf-8 -*-
"""
命令行演示：python cli.py
================================
展示：
  1. 场景级中二度检测（台词 → 分数 / 级别 / 命中信号 / 降档建议）
  2. 情境校准效果对比（同一句台词，反派+高潮场景 vs 日常主角）
"""
import sys

from chuuni_engine import ChuuniRuleEngine

if sys.stdout and sys.stdout.encoding and "utf" not in sys.stdout.encoding.lower():
    sys.stdout.reconfigure(encoding="utf-8")

# 演示场景：一日常场，主角林默（台词包含典型中二样本与正常样本）
DEMO_SCENE = {
    "scene_id": "demo_daily_scene",
    "scene_type": "daily",
    "character": {"name": "林默", "role_type": "protagonist"},
    "lines": [
        {"line_no": 1, "speaker": "林默", "text": "我的命运，终将在此终结！"},
        {"line_no": 2, "speaker": "阿哲", "text": "给我记住！"},
        {"line_no": 3, "speaker": "林默", "text": "你竟敢背叛我！！"},
        {"line_no": 4, "speaker": "林默", "text": "这就是我的觉悟！"},
        {"line_no": 5, "speaker": "阿哲", "text": "这事，你不能再瞒了。"},
        {"line_no": 6, "speaker": "林默", "text": "凡人，怎会懂得苍生的意志。"},
        {"line_no": 7, "speaker": "阿哲", "text": "行，那晚饭你请。"},
    ],
}


def main():
    engine = ChuuniRuleEngine()
    print("=" * 70)
    print("ScriptDoc 中二度检测 · 规则引擎演示（词汇层 + 句法层，纯本地可复算）")
    print("=" * 70)

    res = engine.analyze_scene(DEMO_SCENE)
    n = len(DEMO_SCENE["lines"])
    print(f"\n场景 {res['scene_id']} · {DEMO_SCENE['scene_type']} · "
          f"场景中二度 {res['scene_score']}（{res['scene_level']}）· 问题行 {res['flagged_count']}/{n}\n")
    for l in res["per_line"]:
        print(f"[{l['line_no']:>2}] {l['speaker']}：{l['text']}")
        print(f"     中二度 {l['score']:>5.1f} · {l['level']}")
        if l["signals"]:
            for s in l["signals"]:
                print(f"     信号  {s['type']:<18} 证据：{'、'.join(s['evidence'])}")
        else:
            print("     信号  无")
        for sug in l["suggestion"]:
            print(f"     建议  {sug}")

    print("\n" + "=" * 70)
    print("情境校准对比：同一句台词，反派 + 高潮场景 应显著低于 日常主角")
    print("=" * 70)
    line = {"line_no": 1, "speaker": "反派", "text": "我的命运，终将在此终结！"}
    for scene_type, role_type in [("daily", "protagonist"),
                                  ("villain_entrance", "villain"),
                                  ("daily", "chuuni_character")]:
        r = engine.analyze_line(line, scene_type=scene_type, role_type=role_type)
        print(f"  {scene_type:<18} × {role_type:<16} → 中二度 {r['score']:>5.1f} · {r['level']}")


if __name__ == "__main__":
    main()
