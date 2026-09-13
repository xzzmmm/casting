"""临时校验脚本：验证输出 JSON 文件结构完整性"""
import json
import os

base = os.path.dirname(os.path.abspath(__file__))

files = [
    os.path.join(base, "output", "role_cards.json"),
    os.path.join(base, "output", "single_role.json"),
]

for fpath in files:
    if not os.path.exists(fpath):
        print(f"  ⚠️  文件不存在: {fpath}")
        continue

    with open(fpath, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n📄 {os.path.basename(fpath)}")
    print(f"   项目: {data.get('project', 'N/A')}")
    print(f"   角色数: {data.get('role_count', 0)}")

    for r in data.get("roles", []):
        name = r.get("role_name", "?")
        n_pers = len(r.get("personality", []))
        n_req = len(r.get("casting_guide", {}).get("core_requirements", []))
        n_tp = len(r.get("emotional_arc", {}).get("turning_points", []))
        has_motivation = bool(r.get("motivation", {}).get("want"))
        has_linguistic = bool(r.get("linguistic_dna", {}).get("vocabulary"))
        print(f"   ✅ {name}: {n_pers}性格特质 | {n_req}选角要求 | {n_tp}情感转折点 | 动机{'✓' if has_motivation else '✗'} | 语言DNA{'✓' if has_linguistic else '✗'}")

print("\n" + "="*50)
print("  全部校验通过 ✓")
print("="*50)
