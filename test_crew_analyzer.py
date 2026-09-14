#!/usr/bin/env python3
"""
CastingNuwa · 制作团队需求分析器测试套件

用5个不同类型的剧本测试启发式分析器的准确性：
1. 经典悲剧（哈姆雷特风格）- 多场景、灯光音效需求高
2. 荒诞剧（等待戈多风格）- 极简舞台、少道具
3. 中国现代话剧（雷雨风格）- 家庭场景、时代服装
4. 纯对话无舞台指示 - 边界测试
5. 古装宫廷戏 - 服装化妆需求高

评估维度：
- 岗位识别准确率（需要/不需要判断是否正确）
- 人数合理性
- 复杂度评分合理性
- 证据相关性
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src import CrewAnalyzer
from src.models import CrewAnalysisResult


# ============================================================
# 测试用例定义
# ============================================================

TEST_CASES = [
    {
        "name": "测试1：经典悲剧（哈姆雷特风格）",
        "description": "多场景、有明确灯光音效提示、服装需求中等",
        "script": """第一幕：城堡露台
【灯光：昏暗，月光冷照】
【音效：远处雷声，风声】
哈姆雷特：（手持佩剑）生存还是毁灭，这是一个问题。
鬼魂：（从阴影中走出）哈姆雷特，你必须为我复仇。
【灯光：聚光打在鬼魂身上】

第二幕：王宫大厅
【灯光：明亮，金碧辉煌】
克劳狄斯：（身着王袍）我的侄子，为何如此忧郁？
乔特鲁德：（戴着珠宝）孩子，开心一点吧。
【音效：宫廷音乐响起】

第三幕：王后寝宫
【灯光：昏暗，烛光摇曳】
哈姆雷特：（愤怒）母亲，你怎能嫁给杀父仇人！
【音效：雷声大作】
【灯光：闪电照亮房间】
波洛涅斯：（躲在帷幕后）救命！
哈姆雷特：（拔剑刺向帷幕）有贼！
""",
        "expected": {
            "scenes": 3,
            "characters_min": 4,
            "scale": "大型",
            "needed_roles": ["lighting", "sound", "stage_design", "costume", "props"],
            "not_needed_roles": ["makeup"],
            "lighting_headcount_min": 2,
            "sound_headcount_min": 1,
        }
    },
    {
        "name": "测试2：荒诞剧（等待戈多风格）",
        "description": "极简舞台、单一场景、少道具、服装简单",
        "script": """【场景：一条乡间小路，一棵树】
【灯光：白天，自然光】
弗拉季米尔：（坐在树墩上）咱们走吧。
爱斯特拉冈：咱们不能。
弗拉季米尔：为什么不能？
爱斯特拉冈：咱们在等待戈多。
弗拉季米尔：（摘下帽子，往里看，伸手进去摸了摸）嗯。
爱斯特拉冈：你说什么？
弗拉季米尔：没什么。
【音效：沉默】
爱斯特拉冈：（脱掉靴子，往里面看，伸手进去摸了摸）什么也没有。
""",
        "expected": {
            "scenes": 1,
            "characters_min": 2,
            "scale": "小型",
            "needed_roles": ["stage_design", "props"],
            "not_needed_roles": ["lighting", "sound", "costume", "makeup"],
        }
    },
    {
        "name": "测试3：中国现代话剧（雷雨风格）",
        "description": "家庭场景、多角色、时代服装、有音效提示",
        "script": """第一幕：周公馆客厅
【场景：客厅，沙发，茶几，窗户】
【灯光：下午，阳光透过窗户】
【音效：蝉鸣，远处雷声】
周朴园：（穿着西装，严肃）繁漪，你今天又没有吃药。
繁漪：（穿着旗袍，苍白）我不想吃。
周萍：（穿着长衫，犹豫）爸，我想明天就去矿上。
鲁侍萍：（穿着旧布衫，颤抖）这屋子……我好像来过。
【音效：雷声渐响】
【灯光：天色渐暗】
四凤：（穿着丫鬟服，端着茶）老爷，茶来了。
""",
        "expected": {
            "scenes": 1,
            "characters_min": 5,
            "scale": "中型",
            "needed_roles": ["stage_design", "costume", "props", "sound", "lighting"],
            "not_needed_roles": ["makeup"],
        }
    },
    {
        "name": "测试4：纯对话无舞台指示（边界测试）",
        "description": "完全没有舞台指示，只有纯对话",
        "script": """张三：你好。
李四：你好。
张三：今天天气不错。
李四：是啊。
张三：一起去吃饭吗？
李四：好啊。
张三：走吧。
李四：嗯。
""",
        "expected": {
            "scenes": 1,
            "characters_min": 2,
            "scale": "小型",
            "needed_roles": ["stage_design"],
            "not_needed_roles": ["lighting", "sound", "costume", "props", "makeup"],
        }
    },
    {
        "name": "测试5：古装宫廷戏（服装化妆需求高）",
        "description": "古装、多场景、服装化妆需求极高",
        "script": """第一幕：金銮殿
【场景：宫殿，龙椅，屏风，香炉】
【灯光：金色，辉煌】
皇帝：（身着龙袍，戴皇冠，留胡须）众卿平身。
大臣：（身着官服，戴官帽）谢陛下。
【化妆：皇帝戴胡须，大臣戴假发】
【道具：圣旨，玉玺】
【音效：钟声，礼乐】

第二幕：后宫
皇后：（身着凤袍，戴凤冠，涂胭脂）皇上今天又去哪个妃子那里了？
宫女：（身着宫女服）回皇后，皇上去了丽妃宫中。
【服装：皇后换便服】
【化妆：皇后补妆】
丽妃：（身着华服，戴珠宝）臣妾参见皇后娘娘。
【化妆：丽妃浓妆】
""",
        "expected": {
            "scenes": 2,
            "characters_min": 4,
            "scale": "中型",
            "needed_roles": ["lighting", "sound", "stage_design", "costume", "props", "makeup"],
            "not_needed_roles": [],
            "costume_complexity_min": 3,
            "makeup_complexity_min": 3,
        }
    },
]


# ============================================================
# 测试执行
# ============================================================

def run_tests():
    """运行所有测试用例"""
    analyzer = CrewAnalyzer()

    print("=" * 70)
    print("  CastingNuwa · 制作团队需求分析器测试报告")
    print("=" * 70)
    print()

    total_score = 0
    max_score = 0
    results = []

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"{'─' * 70}")
        print(f"  {test_case['name']}")
        print(f"  描述：{test_case['description']}")
        print(f"{'─' * 70}")
        print()

        # 运行分析
        result = analyzer.analyze(test_case["script"])
        expected = test_case["expected"]

        # 评分
        case_score = 0
        case_max = 0
        details = []

        # 1. 场景数估算（10分）
        case_max += 10
        if result.total_scenes == expected["scenes"]:
            case_score += 10
            details.append(f"✅ 场景数：{result.total_scenes}（预期{expected['scenes']}）")
        elif abs(result.total_scenes - expected["scenes"]) <= 1:
            case_score += 7
            details.append(f"🟡 场景数：{result.total_scenes}（预期{expected['scenes']}，接近）")
        else:
            details.append(f"❌ 场景数：{result.total_scenes}（预期{expected['scenes']}）")

        # 2. 角色数估算（10分）
        case_max += 10
        if result.total_characters >= expected["characters_min"]:
            case_score += 10
            details.append(f"✅ 角色数：{result.total_characters}（预期≥{expected['characters_min']}）")
        elif result.total_characters >= expected["characters_min"] - 1:
            case_score += 7
            details.append(f"🟡 角色数：{result.total_characters}（预期≥{expected['characters_min']}，接近）")
        else:
            details.append(f"❌ 角色数：{result.total_characters}（预期≥{expected['characters_min']}）")

        # 3. 制作规模（10分）
        case_max += 10
        if result.production_scale == expected["scale"]:
            case_score += 10
            details.append(f"✅ 制作规模：{result.production_scale}（预期{expected['scale']}）")
        else:
            details.append(f"❌ 制作规模：{result.production_scale}（预期{expected['scale']}）")

        # 4. 岗位识别（每个岗位5分，共30分）
        case_max += 30
        role_correct = 0
        role_total = 0
        for role_key in ["lighting", "sound", "stage_design", "costume", "props", "makeup"]:
            role_total += 1
            req = result.requirements.get(role_key)
            if not req:
                continue
            expected_needed = role_key in expected["needed_roles"]
            if req.needed == expected_needed:
                role_correct += 1
            else:
                status = "需要" if req.needed else "不需要"
                exp_status = "需要" if expected_needed else "不需要"
                details.append(f"   ❌ {req.role_name}：{status}（预期{exp_status}）")

        role_score = int(30 * role_correct / role_total)
        case_score += role_score
        details.append(f"✅ 岗位识别：{role_correct}/{role_total} 正确（{role_score}分）")

        # 5. 人数合理性（10分，仅检查有明确预期的）
        case_max += 10
        headcount_ok = True
        if "lighting_headcount_min" in expected:
            lighting = result.requirements.get("lighting")
            if lighting and lighting.headcount < expected["lighting_headcount_min"]:
                headcount_ok = False
                details.append(f"   ❌ 灯光师人数：{lighting.headcount}（预期≥{expected['lighting_headcount_min']}）")
        if "sound_headcount_min" in expected:
            sound = result.requirements.get("sound")
            if sound and sound.headcount < expected["sound_headcount_min"]:
                headcount_ok = False
                details.append(f"   ❌ 音效师人数：{sound.headcount}（预期≥{expected['sound_headcount_min']}）")
        if headcount_ok:
            case_score += 10
            details.append(f"✅ 人数合理性：符合预期")

        # 6. 复杂度评分合理性（10分，仅检查有明确预期的）
        case_max += 10
        complexity_ok = True
        if "costume_complexity_min" in expected:
            costume = result.requirements.get("costume")
            if costume and costume.complexity < expected["costume_complexity_min"]:
                complexity_ok = False
                details.append(f"   ❌ 服装复杂度：{costume.complexity}（预期≥{expected['costume_complexity_min']}）")
        if "makeup_complexity_min" in expected:
            makeup = result.requirements.get("makeup")
            if makeup and makeup.complexity < expected["makeup_complexity_min"]:
                complexity_ok = False
                details.append(f"   ❌ 化妆复杂度：{makeup.complexity}（预期≥{expected['makeup_complexity_min']}）")
        if complexity_ok:
            case_score += 10
            details.append(f"✅ 复杂度评分：符合预期")

        # 7. 证据相关性（10分：需要的岗位是否有证据）
        case_max += 10
        evidence_ok = True
        for role_key in expected["needed_roles"]:
            req = result.requirements.get(role_key)
            if req and req.needed and (not req.evidence or len(req.evidence) == 0):
                evidence_ok = False
                details.append(f"   ❌ {req.role_name}：缺少剧本依据")
        if evidence_ok:
            case_score += 10
            details.append(f"✅ 证据相关性：需要的岗位均有剧本依据")

        # 输出详情
        for detail in details:
            print(f"  {detail}")

        percentage = int(case_score / case_max * 100)
        print()
        print(f"  📊 本测试得分：{case_score}/{case_max}（{percentage}%）")
        print()

        total_score += case_score
        max_score += case_max
        results.append({
            "name": test_case["name"],
            "score": case_score,
            "max": case_max,
            "percentage": percentage,
        })

    # 汇总
    print("=" * 70)
    print("  测试汇总")
    print("=" * 70)
    print()
    print(f"  {'测试用例':<35} {'得分':<10} {'百分比':<10}")
    print(f"  {'─'*35} {'─'*10} {'─'*10}")
    for r in results:
        print(f"  {r['name']:<35} {r['score']}/{r['max']:<6} {r['percentage']}%")

    total_percentage = int(total_score / max_score * 100)
    print(f"  {'─'*35} {'─'*10} {'─'*10}")
    print(f"  {'总分':<35} {total_score}/{max_score:<6} {total_percentage}%")
    print()

    # 评级
    if total_percentage >= 90:
        grade = "优秀（A）"
        comment = "分析器表现优秀，能够准确识别各类剧本的制作团队需求。"
    elif total_percentage >= 80:
        grade = "良好（B）"
        comment = "分析器表现良好，大部分场景能准确识别，少数边界情况需要优化。"
    elif total_percentage >= 70:
        grade = "中等（C）"
        comment = "分析器表现中等，基本功能可用，但在准确性和细节上有较大提升空间。"
    elif total_percentage >= 60:
        grade = "及格（D）"
        comment = "分析器勉强可用，但错误率较高，需要显著优化。"
    else:
        grade = "不及格（F）"
        comment = "分析器表现较差，需要重新设计核心算法。"

    print(f"  🏆 综合评级：{grade}")
    print(f"  💬 评价：{comment}")
    print()
    print("=" * 70)

    return total_percentage, grade, comment


if __name__ == "__main__":
    run_tests()
