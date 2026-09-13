"""
CastingNuwa · 选角女娲
角色蒸馏器（Role Distiller）

核心模块：从剧本中蒸馏角色的"认知操作系统"，生成结构化角色卡。

对标 nuwa-skill 的思维蒸馏流水线：
- nuwa-skill: 输入人名 → 调研 → 提炼 → 验证 → 人物 Skill
- CastingNuwa: 输入剧本 → 角色蒸馏 → 解析校验 → 角色卡

支持三种蒸馏模式：
1. distill_all()      - 蒸馏剧本中所有角色
2. distill_one()      - 深度蒸馏单个角色
3. refine_role_card() - 优化已有的角色卡
"""

import os
import json
import re
from typing import List, Optional, Dict, Any

from .models import RoleCard
from .prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    SINGLE_ROLE_PROMPT_TEMPLATE,
    REFINE_PROMPT_TEMPLATE,
)
from .llm_client import LLMClient


class RoleDistiller:
    """
    角色蒸馏器

    将剧本文本转化为结构化的角色卡（Role Card）列表。
    每个角色卡包含 7 个维度的深度分析，特别强调选角指引。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化角色蒸馏器

        Args:
            llm_client: LLM 客户端实例，为 None 时自动创建
        """
        self.llm = llm_client or LLMClient()

    def distill_all(self, script: str, max_retries: int = 2) -> List[RoleCard]:
        """
        蒸馏剧本中所有角色

        Args:
            script: 剧本文本
            max_retries: JSON 解析失败时的最大重试次数

        Returns:
            角色卡列表
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 角色蒸馏")
        print(f"{'='*60}")
        print(f"  剧本长度：{len(script)} 字符")
        print(f"  模式：全角色蒸馏")
        if self.llm.is_mock_mode:
            print(f"  ⚠️  当前为 Mock 演示模式，输出为示例数据")
            print(f"     配置 LLM_API_KEY 后可使用真实 AI 分析")
        print(f"{'='*60}\n")

        user_prompt = USER_PROMPT_TEMPLATE.format(script=script)

        result = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries}] 重新请求 LLM...")

            raw_result = self.llm.chat_json(SYSTEM_PROMPT, user_prompt)

            # 检查是否解析成功
            if "_parse_error" in raw_result:
                if attempt < max_retries:
                    continue
                else:
                    print(f"  ❌ JSON 解析失败，已达最大重试次数")
                    return []

            result = raw_result
            break

        if result is None:
            return []

        # 解析角色卡列表
        roles_data = result.get("roles", [])
        if not roles_data and "role_name" in result:
            # 单角色情况
            roles_data = [result]

        role_cards = []
        for i, role_data in enumerate(roles_data):
            try:
                card = RoleCard.from_dict(role_data)
                role_cards.append(card)
                print(f"  ✅ 角色 {i+1}/{len(roles_data)}：{card.role_name}")
            except Exception as e:
                print(f"  ❌ 角色 {i+1} 解析失败：{e}")

        print(f"\n  蒸馏完成：共 {len(role_cards)} 个角色\n")
        return role_cards

    def distill_one(self, script: str, role_name: str, max_retries: int = 2) -> Optional[RoleCard]:
        """
        深度蒸馏单个角色

        Args:
            script: 剧本文本
            role_name: 要蒸馏的角色名
            max_retries: 最大重试次数

        Returns:
            角色卡，失败返回 None
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 单角色深度蒸馏")
        print(f"  目标角色：{role_name}")
        print(f"{'='*60}\n")

        user_prompt = SINGLE_ROLE_PROMPT_TEMPLATE.format(
            role_name=role_name,
            script=script,
        )

        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries}]...")

            result = self.llm.chat_json(SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                print(f"  ❌ JSON 解析失败")
                return None

            try:
                card = RoleCard.from_dict(result)
                print(f"  ✅ 角色卡生成完成：{card.role_name}\n")
                return card
            except Exception as e:
                print(f"  ❌ 角色卡构建失败：{e}")
                if attempt < max_retries:
                    continue
                return None

        return None

    def refine_role_card(
        self,
        script: str,
        role_card: RoleCard,
        max_retries: int = 2,
    ) -> Optional[RoleCard]:
        """
        优化已有的角色卡

        Args:
            script: 剧本文本
            role_card: 待优化的角色卡
            max_retries: 最大重试次数

        Returns:
            优化后的角色卡
        """
        print(f"\n  [优化] 正在优化角色「{role_card.role_name}」...")

        user_prompt = REFINE_PROMPT_TEMPLATE.format(
            role_name=role_card.role_name,
            script=script,
            role_card_json=role_card.to_json(),
        )

        for attempt in range(max_retries + 1):
            result = self.llm.chat_json(SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in result:
                if attempt < max_retries:
                    continue
                print(f"  ⚠️  优化失败，保留原角色卡")
                return role_card

            try:
                refined = RoleCard.from_dict(result)
                print(f"  ✅ 优化完成：{refined.role_name}")
                return refined
            except Exception as e:
                print(f"  ⚠️  优化结果解析失败：{e}，保留原角色卡")
                return role_card

        return role_card

    @staticmethod
    def save_role_cards(role_cards: List[RoleCard], output_path: str) -> str:
        """
        保存角色卡到 JSON 文件

        Args:
            role_cards: 角色卡列表
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        data = {
            "project": "CastingNuwa · 选角女娲",
            "description": "基于思维蒸馏的戏剧角色认知操作系统",
            "role_count": len(role_cards),
            "roles": [card.to_dict() for card in role_cards],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  💾 角色卡已保存：{output_path}")
        return output_path

    @staticmethod
    def load_role_cards(input_path: str) -> List[RoleCard]:
        """
        从 JSON 文件加载角色卡

        Args:
            input_path: 输入文件路径

        Returns:
            角色卡列表
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        roles_data = data.get("roles", [])
        return [RoleCard.from_dict(rd) for rd in roles_data]

    @staticmethod
    def print_summary(role_cards: List[RoleCard]) -> None:
        """打印所有角色卡的摘要"""
        for card in role_cards:
            print(card.summary())
            print()

    @staticmethod
    def extract_characters_from_script(script: str) -> List[str]:
        """
        从剧本中简单提取角色名（用于预处理和提示）

        基于常见剧本格式：角色名后接冒号或句号
        这是一个简单的启发式方法，不保证完全准确

        Args:
            script: 剧本文本

        Returns:
            候选角色名列表
        """
        # 匹配行首的角色名（中文，2-4个字，后接冒号）
        pattern = r"^([\u4e00-\u9fa5]{2,4})[：:]"
        characters = set()

        for line in script.split("\n"):
            line = line.strip()
            match = re.match(pattern, line)
            if match:
                name = match.group(1)
                # 过滤常见的非角色词
                if name not in ["旁白", "解说", "幕布", "舞台", "灯光", "音乐", "音效"]:
                    characters.add(name)

        return sorted(list(characters))
