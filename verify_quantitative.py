import json
import sys
sys.path.insert(0, '.')

with open('output/test_report.json', 'r', encoding='utf-8') as f:
    report = json.load(f)

print("=== 数值匹配层验证（端到端测试报告）===")
for r in report['results']:
    role = r['role_name']
    actor = r['actor_name']
    overall = r['overall_score']
    qscore = r.get('quantitative_score', 'N/A')
    tscore = r.get('text_score', 'N/A')
    qweight = r.get('quantitative_weight', 'N/A')
    tweight = r.get('text_weight', 'N/A')
    qm = r.get('quantitative_matches', [])
    included = [x for x in qm if x.get('included')]
    print(f"\n{role} x {actor}:")
    print(f"  综合分:{overall} | 数值分:{qscore} | 文本分:{tscore}")
    print(f"  权重: 数值{qweight} + 文本{tweight}")
    print(f"  有效数值维度: {len(included)}/5")
    for x in included:
        print(f"    {x['dimension_name']}: 角色{x['role_score']} vs 演员{x['actor_score']} = 相似度{x['similarity']:.0f}%")

# 验证角色卡量化特质
print("\n\n=== 角色卡量化特质验证 ===")
with open('output/test_roles.json', 'r', encoding='utf-8') as f:
    roles_data = json.load(f)
for role in roles_data.get('roles', []):
    name = role['role_name']
    qt = role.get('quantitative_traits', {})
    print(f"\n{name}:")
    for key, ts in qt.items():
        from src.models import QUANTITATIVE_TRAITS
        tname = QUANTITATIVE_TRAITS.get(key, {}).get('name', key)
        score = ts.get('score')
        score_str = f"{score}/10" if score is not None else "N/A"
        print(f"  {tname}: {score_str} (置信度:{ts.get('confidence')}, 证据:{ts.get('evidence_count')}条)")

# 验证演员画像量化特质
print("\n\n=== 演员画像量化特质验证 ===")
with open('output/test_actors.json', 'r', encoding='utf-8') as f:
    actors_data = json.load(f)
for actor in actors_data.get('actors', []):
    name = actor['actor_name']
    qt = actor.get('quantitative_traits', {})
    print(f"\n{name}:")
    for key, ts in qt.items():
        from src.models import QUANTITATIVE_TRAITS
        tname = QUANTITATIVE_TRAITS.get(key, {}).get('name', key)
        score = ts.get('score')
        score_str = f"{score}/10" if score is not None else "N/A"
        print(f"  {tname}: {score_str} (置信度:{ts.get('confidence')}, 证据:{ts.get('evidence_count')}条)")
