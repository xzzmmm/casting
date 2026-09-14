"""
CastingNuwa · 选角女娲
制作团队需求分析器（Crew Analyzer）

通过剧本中的舞台指示、场景描述、灯光/音效/服装/道具提示，
分析所需的后台岗位与人员配置。

支持的岗位：
- lighting      灯光师
- sound         音效师
- stage_design  舞美设计
- costume       服装师
- props         道具师
- makeup        化妆师
"""

import os
import json
import re
from typing import Optional, Dict, Any

from .models import CrewAnalysisResult, CrewRequirement, CREW_ROLES
from .crew_prompts import CREW_SYSTEM_PROMPT, CREW_USER_PROMPT_TEMPLATE
from .llm_client import LLMClient


class CrewAnalyzer:
    """
    制作团队需求分析器

    将剧本文本转化为结构化的制作团队需求分析结果，
    包含6个后台岗位的需求评估。
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        初始化制作团队分析器

        Args:
            llm_client: LLM 客户端实例，为 None 时自动创建
        """
        self.llm = llm_client or LLMClient()

    def analyze(self, script: str, max_retries: int = 2) -> CrewAnalysisResult:
        """
        分析剧本的制作团队需求

        Args:
            script: 剧本文本
            max_retries: JSON 解析失败时的最大重试次数

        Returns:
            制作团队需求分析结果
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 制作团队需求分析")
        print(f"{'='*60}")
        print(f"  剧本长度：{len(script)} 字符")
        if self.llm.is_mock_mode:
            print(f"  ⚠️  当前为 Mock 演示模式，输出为示例数据")
            print(f"     配置 LLM_API_KEY 后可使用真实 AI 分析")
        print(f"{'='*60}\n")

        user_prompt = CREW_USER_PROMPT_TEMPLATE.format(script=script)

        result = None
        for attempt in range(max_retries + 1):
            if attempt > 0:
                print(f"  [重试 {attempt}/{max_retries}] 重新请求 LLM...")

            raw_result = self.llm.chat_json(CREW_SYSTEM_PROMPT, user_prompt)

            if "_parse_error" in raw_result:
                if attempt < max_retries:
                    continue
                else:
                    print(f"  ❌ JSON 解析失败，已达最大重试次数")
                    return CrewAnalysisResult()

            result = raw_result
            break

        if result is None:
            return CrewAnalysisResult()

        try:
            analysis = CrewAnalysisResult.from_dict(result)
            print(f"  ✅ 分析完成")
            print(f"  📊 场景数：{analysis.total_scenes} | 角色数：{analysis.total_characters}")
            print(f"  🎬 制作规模：{analysis.production_scale or '未评估'}")
            needed_roles = [r.role_name for r in analysis.requirements.values() if r.needed]
            print(f"  👥 需要岗位：{', '.join(needed_roles) if needed_roles else '无'}")
            print()
            return analysis
        except Exception as e:
            print(f"  ❌ 分析结果解析失败：{e}")
            return CrewAnalysisResult()

    @staticmethod
    def save_analysis(analysis: CrewAnalysisResult, output_path: str) -> str:
        """
        保存分析结果到 JSON 文件

        Args:
            analysis: 制作团队需求分析结果
            output_path: 输出文件路径

        Returns:
            保存的文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        data = {
            "project": "CastingNuwa · 选角女娲",
            "description": "制作团队需求分析结果",
            "analysis": analysis.to_dict(),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"  💾 分析结果已保存：{output_path}")
        return output_path

    @staticmethod
    def load_analysis(input_path: str) -> CrewAnalysisResult:
        """
        从 JSON 文件加载分析结果

        Args:
            input_path: 输入文件路径

        Returns:
            制作团队需求分析结果
        """
        with open(input_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        analysis_data = data.get("analysis", data)
        return CrewAnalysisResult.from_dict(analysis_data)

    @staticmethod
    def print_summary(analysis: CrewAnalysisResult) -> None:
        """打印分析结果摘要"""
        print(analysis.summary())

    @staticmethod
    def estimate_scenes(script: str) -> int:
        """
        简单估算剧本中的场景数

        基于常见的场景标记：第X幕、第X场、Scene、ACT等

        Args:
            script: 剧本文本

        Returns:
            估算的场景数
        """
        patterns = [
            r"第[一二三四五六七八九十\d]+幕",
            r"第[一二三四五六七八九十\d]+场",
            r"Scene\s+\d+",
            r"ACT\s+\d+",
            r"【第[一二三四五六七八九十\d]+场】",
        ]
        scenes = set()
        for pattern in patterns:
            matches = re.findall(pattern, script, re.IGNORECASE)
            scenes.update(matches)
        return max(len(scenes), 1)
