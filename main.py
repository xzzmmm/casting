#!/usr/bin/env python3
"""
CastingNuwa · 选角女娲 — 命令行入口

用法：
  # 全角色蒸馏（使用示例剧本）
  python main.py --script examples/sample_script.txt

  # 全角色蒸馏并保存结果
  python main.py --script my_script.txt --output output/result.json

  # 单角色深度蒸馏
  python main.py --script my_script.txt --role "莱恩"

  # 查看角色卡摘要
  python main.py --script my_script.txt --summary

  # 从已有 JSON 加载并查看
  python main.py --load output/result.json --summary
"""

import argparse
import os
import sys

# 将 src 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.llm_client import LLMClient


def read_script(file_path: str) -> str:
    """读取剧本文件"""
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在：{file_path}")
        sys.exit(1)

    # 尝试不同编码
    for encoding in ["utf-8", "utf-8-sig", "gbk", "gb2312"]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue

    print(f"❌ 无法读取文件（编码不支持）：{file_path}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="CastingNuwa · 选角女娲 — 基于思维蒸馏的 AI 戏剧选角辅助系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py --script examples/sample_script.txt
  python main.py --script my_script.txt --output output/result.json
  python main.py --script my_script.txt --role "莱恩"
  python main.py --load output/result.json --summary
        """,
    )

    parser.add_argument(
        "--script", "-s",
        type=str,
        help="剧本文件路径（支持 .txt）",
    )
    parser.add_argument(
        "--role", "-r",
        type=str,
        help="单角色深度蒸馏模式：指定角色名",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output/role_cards.json",
        help="输出 JSON 文件路径（默认：output/role_cards.json）",
    )
    parser.add_argument(
        "--load", "-l",
        type=str,
        help="从已有 JSON 文件加载角色卡（跳过蒸馏）",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="打印角色卡的人类可读摘要",
    )
    parser.add_argument(
        "--refine",
        action="store_true",
        help="对蒸馏结果进行优化（需要 API，Mock 模式下无效）",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="LLM API Key（也可通过环境变量 LLM_API_KEY 设置）",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="LLM API 地址（也可通过环境变量 LLM_BASE_URL 设置）",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="LLM 模型名称（也可通过环境变量 LLM_MODEL 设置）",
    )

    args = parser.parse_args()

    # 如果没有任何操作参数，打印帮助
    if not args.script and not args.load:
        parser.print_help()
        print("\n💡 快速开始：python main.py --script examples/sample_script.txt")
        return

    # 初始化 LLM 客户端
    llm_kwargs = {}
    if args.api_key:
        llm_kwargs["api_key"] = args.api_key
    if args.base_url:
        llm_kwargs["base_url"] = args.base_url
    if args.model:
        llm_kwargs["model"] = args.model

    llm_client = LLMClient(**llm_kwargs) if llm_kwargs else LLMClient()
    distiller = RoleDistiller(llm_client=llm_client)

    # 模式 1：从已有文件加载
    if args.load:
        print(f"\n📂 从文件加载角色卡：{args.load}")
        role_cards = RoleDistiller.load_role_cards(args.load)
        print(f"   已加载 {len(role_cards)} 个角色卡")

    # 模式 2：单角色深度蒸馏
    elif args.role and args.script:
        script = read_script(args.script)
        card = distiller.distill_one(script, args.role)
        if card:
            role_cards = [card]
            # 保存
            output_path = args.output
            RoleDistiller.save_role_cards(role_cards, output_path)
        else:
            print("❌ 角色蒸馏失败")
            return

    # 模式 3：全角色蒸馏
    elif args.script:
        script = read_script(args.script)

        # 预处理：提取候选角色名
        candidates = RoleDistiller.extract_characters_from_script(script)
        if candidates:
            print(f"  📋 检测到候选角色：{', '.join(candidates)}")

        role_cards = distiller.distill_all(script)

        if not role_cards:
            print("❌ 未生成任何角色卡")
            return

        # 优化（可选）
        if args.refine and not llm_client.is_mock_mode:
            print("\n  🔧 开始优化角色卡...")
            refined_cards = []
            for card in role_cards:
                refined = distiller.refine_role_card(script, card)
                refined_cards.append(refined)
            role_cards = refined_cards

        # 保存
        output_path = args.output
        RoleDistiller.save_role_cards(role_cards, output_path)

    else:
        parser.print_help()
        return

    # 打印摘要
    if args.summary:
        print("\n" + "=" * 60)
        print("  角色卡摘要")
        print("=" * 60)
        RoleDistiller.print_summary(role_cards)

    # 最终提示
    print(f"\n{'='*60}")
    print(f"  ✅ 完成！共 {len(role_cards)} 个角色卡")
    if not args.load:
        print(f"  📄 结果已保存：{args.output}")
    if llm_client.is_mock_mode:
        print(f"  ⚠️  当前为 Mock 演示模式")
        print(f"     配置 LLM_API_KEY 后可使用真实 AI 分析")
        print(f"     详见 .env.example 和 README.md")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
