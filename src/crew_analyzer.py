"""
CastingNuwa · 选角女娲
制作团队需求分析器（Crew Analyzer）

通过剧本中的舞台指示、场景描述、灯光/音效/服装/道具提示，
分析所需的后台岗位与人员配置。

支持两种分析模式：
1. LLM 深度分析（配置 API Key 后使用）
2. 启发式规则分析（无 API Key 时自动启用，基于关键词匹配）

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
from typing import Optional, Dict, Any, List, Tuple

from .models import CrewAnalysisResult, CrewRequirement, CREW_ROLES
from .crew_prompts import CREW_SYSTEM_PROMPT, CREW_USER_PROMPT_TEMPLATE
from .llm_client import LLMClient


# ============================================================
# 启发式分析关键词库
# ============================================================

# 灯光相关关键词
LIGHTING_KEYWORDS = {
    "basic": ["灯光", "光线", "光亮", "照明", "亮", "暗", "黑场", "暗场"],
    "spotlight": ["聚光", "追光", "定点光", "面光", "侧光", "逆光", "顶光"],
    "effect": ["闪光", "频闪", "闪烁", "渐变", "淡入", "淡出", "切换", "变化"],
    "color": ["红光", "蓝光", "绿光", "黄光", "紫光", "彩色", "色光", "暖光", "冷光"],
    "cue": ["灯起", "灯落", "灯亮", "灯灭", "开灯", "关灯", "幕启", "幕落"],
}

# 音效相关关键词
SOUND_KEYWORDS = {
    "music": ["音乐", "乐曲", "旋律", "伴奏", "BGM", "bgm", "配乐", "歌曲", "唱"],
    "nature": ["雷声", "雨声", "风声", "水声", "海浪", "鸟鸣", "虫鸣", "雷声", "闪电"],
    "action": ["敲门声", "关门声", "开门声", "脚步声", "枪声", "爆炸声", "破碎声", "摔门"],
    "object": ["铃声", "电话声", "钟响", "闹钟", "喇叭", "汽笛", "引擎", "刹车"],
    "ambient": ["环境音", "背景音", "嘈杂", "寂静", "沉默", "安静", "喧闹"],
    "cue": ["音效起", "音效落", "音乐起", "音乐落", "声音", "声响"],
}

# 舞美/场景相关关键词
STAGE_KEYWORDS = {
    "scene_marker": ["第", "幕", "场", "场景", "地点", "布景", "舞台"],
    "setting": ["房间", "客厅", "卧室", "厨房", "办公室", "教室", "街道", "公园", "森林", "海边", "山顶", "宫殿", "城堡", "花园", "餐厅", "酒吧", "医院", "监狱"],
    "prop_scene": ["桌子", "椅子", "沙发", "床", "柜子", "书架", "门", "窗", "楼梯", "屏风", "帷幕", "地毯", "挂画", "镜子"],
    "complex": ["旋转", "升降", "移动", "推拉", "折叠", "多层", "立体", "投影", "LED", "屏幕"],
}

# 服装相关关键词
COSTUME_KEYWORDS = {
    "clothing": ["穿着", "身着", "身穿", "打扮", "着装", "服装", "衣服", "外套", "裙子", "西装", "礼服", "古装", "旗袍", "制服", "军装", "婚纱"],
    "accessory": ["帽子", "围巾", "手套", "项链", "耳环", "戒指", "手镯", "眼镜", "领带", "腰带", "鞋子", "靴子"],
    "change": ["换装", "换衣", "更衣", "脱下", "穿上", "换上"],
    "special": ["戏服", "演出服", "特殊服装", "紧身衣", "斗篷", "披风", "铠甲", "盔甲"],
}

# 道具相关关键词
PROPS_KEYWORDS = {
    "handheld": ["拿着", "手持", "手握", "举起", "挥舞", "递给", "接过", "放下", "拿起", "掏出"],
    "objects": ["手机", "电话", "信件", "信封", "照片", "镜子", "梳子", "口红", "香水", "钱包", "钥匙", "雨伞", "拐杖", "手杖", "刀", "剑", "枪", "酒杯", "瓶子", "杯子", "书", "笔记本", "笔", "花", "礼物", "盒子", "包裹"],
    "food": ["食物", "饭菜", "水果", "蛋糕", "面包", "酒", "茶", "咖啡", "水"],
    "breakable": ["花瓶", "瓷器", "玻璃", "杯子", "盘子", "碗"],
}

# 化妆相关关键词
MAKEUP_KEYWORDS = {
    "basic": ["化妆", "妆容", "妆面", "脂粉", "口红", "粉底", "眼影", "腮红"],
    "special": ["伤痕", "伤疤", "血迹", "老年妆", "皱纹", "白发", "秃头", "假发", "胡须", "胡子", "纹身", "胎记", "面具", "面罩"],
    "change": ["卸妆", "补妆", "改妆", "换妆"],
    "effect": ["特效化妆", "假体", "乳胶", "血浆", "假血"],
}


class CrewAnalyzer:
    """
    制作团队需求分析器

    将剧本文本转化为结构化的制作团队需求分析结果，
    包含6个后台岗位的需求评估。

    无 API Key 时自动使用启发式规则分析任意剧本。
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

        有 API Key 时使用 LLM 深度分析，无 API Key 时使用启发式规则分析。

        Args:
            script: 剧本文本
            max_retries: JSON 解析失败时的最大重试次数（仅 LLM 模式）

        Returns:
            制作团队需求分析结果
        """
        print(f"\n{'='*60}")
        print(f"  CastingNuwa · 制作团队需求分析")
        print(f"{'='*60}")
        print(f"  剧本长度：{len(script)} 字符")

        # Mock 模式下使用启发式分析
        if self.llm.is_mock_mode:
            print(f"  ℹ️  未配置 LLM API，使用启发式规则分析")
            print(f"     配置 LLM_API_KEY 后可获得更精准的 AI 分析")
            print(f"{'='*60}\n")
            return self._heuristic_analyze(script)

        print(f"{'='*60}\n")

        # LLM 模式
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
                    print(f"  ❌ JSON 解析失败，回退到启发式分析")
                    return self._heuristic_analyze(script)

            result = raw_result
            break

        if result is None:
            return self._heuristic_analyze(script)

        try:
            analysis = CrewAnalysisResult.from_dict(result)
            self._print_analysis_summary(analysis)
            return analysis
        except Exception as e:
            print(f"  ❌ 分析结果解析失败：{e}，回退到启发式分析")
            return self._heuristic_analyze(script)

    def _heuristic_analyze(self, script: str) -> CrewAnalysisResult:
        """
        基于规则的启发式分析（无 API Key 时使用）

        通过关键词匹配和正则表达式分析剧本中的舞台指示、
        灯光/音效/场景/服装/道具/化妆等信息。

        Args:
            script: 剧本文本

        Returns:
            制作团队需求分析结果
        """
        # 提取舞台指示（方括号内的内容）
        stage_directions = self._extract_stage_directions(script)

        # 统计各岗位关键词
        lighting_stats = self._count_keywords(script, LIGHTING_KEYWORDS)
        sound_stats = self._count_keywords(script, SOUND_KEYWORDS)
        stage_stats = self._count_keywords(script, STAGE_KEYWORDS)
        costume_stats = self._count_keywords(script, COSTUME_KEYWORDS)
        props_stats = self._count_keywords(script, PROPS_KEYWORDS)
        makeup_stats = self._count_keywords(script, MAKEUP_KEYWORDS)

        # 估算场景数和角色数
        scene_count = self.estimate_scenes(script)
        character_count = self._estimate_characters(script)

        # 判断制作规模
        production_scale = self._estimate_production_scale(
            scene_count, character_count,
            lighting_stats["total"], sound_stats["total"],
            stage_stats["total"], costume_stats["total"],
            props_stats["total"], makeup_stats["total"]
        )

        # 构建各岗位需求
        requirements = {}

        # 灯光师
        requirements["lighting"] = self._build_lighting_req(lighting_stats, script, scene_count)

        # 音效师
        requirements["sound"] = self._build_sound_req(sound_stats, script, scene_count)

        # 舞美设计
        requirements["stage_design"] = self._build_stage_req(stage_stats, script, scene_count)

        # 服装师
        requirements["costume"] = self._build_costume_req(costume_stats, script, character_count)

        # 道具师
        requirements["props"] = self._build_props_req(props_stats, script)

        # 化妆师
        requirements["makeup"] = self._build_makeup_req(makeup_stats, script, character_count)

        # 生成总体建议
        overall_summary = self._generate_overall_summary(
            requirements, scene_count, character_count, production_scale
        )

        result = CrewAnalysisResult(
            script_title=self._extract_title(script),
            total_scenes=scene_count,
            total_characters=character_count,
            production_scale=production_scale,
            requirements=requirements,
            overall_summary=overall_summary,
        )

        self._print_analysis_summary(result)
        return result

    # ============================================================
    # 启发式分析辅助方法
    # ============================================================

    @staticmethod
    def _extract_stage_directions(script: str) -> List[str]:
        """提取舞台指示（方括号内的内容）"""
        patterns = [
            r"[【\[](.+?)[】\]]",
            r"（(.+?)）",
        ]
        directions = []
        for pattern in patterns:
            matches = re.findall(pattern, script)
            directions.extend(matches)
        return directions

    @staticmethod
    def _count_keywords(script: str, keyword_dict: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        统计关键词出现次数

        Returns:
            {"total": 总数, "by_category": {类别: 次数}, "matches": [匹配的原文片段]}
        """
        total = 0
        by_category = {}
        matches = []

        for category, keywords in keyword_dict.items():
            count = 0
            for kw in keywords:
                # 查找关键词所在的句子
                pattern = re.compile(r'[^。！？\n]*' + re.escape(kw) + r'[^。！？\n]*')
                found = pattern.findall(script)
                count += len(found)
                for f in found[:2]:
                    f_clean = f.strip()
                    if f_clean and f_clean not in matches:
                        matches.append(f_clean)
            by_category[category] = count
            total += count

        return {
            "total": total,
            "by_category": by_category,
            "matches": matches[:5],
        }

    @staticmethod
    def _estimate_characters(script: str) -> int:
        """估算剧本中的角色数（基于行首角色名模式）"""
        # 中文角色名：2-4个字，行首，后接冒号
        pattern_cn = r"^([\u4e00-\u9fa5]{2,4})[：:]"
        # 英文角色名：全大写或首字母大写，行首，后接冒号
        pattern_en = r"^([A-Z][A-Z\s]{1,20})[：:]"

        characters = set()
        for line in script.split("\n"):
            line = line.strip()
            m = re.match(pattern_cn, line)
            if m:
                name = m.group(1)
                if name not in ["旁白", "解说", "幕布", "舞台", "灯光", "音乐", "音效", "场景", "地点"]:
                    characters.add(name)
            else:
                m = re.match(pattern_en, line)
                if m:
                    name = m.group(1).strip()
                    characters.add(name)

        return max(len(characters), 1)

    @staticmethod
    def _extract_title(script: str) -> str:
        """尝试从剧本开头提取标题"""
        first_lines = script.strip().split("\n")[:5]
        for line in first_lines:
            line = line.strip()
            if line and len(line) < 50 and not line.startswith("第"):
                # 去掉可能的书名号
                line = re.sub(r"[《》【】\[\]]", "", line)
                return line
        return ""

    @staticmethod
    def _estimate_production_scale(
        scene_count: int, character_count: int,
        lighting: int, sound: int, stage: int,
        costume: int, props: int, makeup: int
    ) -> str:
        """估算制作规模"""
        score = (
            scene_count * 2 +
            character_count +
            lighting + sound + stage + costume + props + makeup
        )
        if score >= 40:
            return "大型"
        elif score >= 20:
            return "中型"
        else:
            return "小型"

    def _build_lighting_req(self, stats: Dict, script: str, scene_count: int) -> CrewRequirement:
        """构建灯光师需求"""
        total = stats["total"]
        needed = total > 0 or scene_count > 1

        # 复杂度计算
        complexity = min(10, total // 2 + scene_count)
        if stats["by_category"].get("effect", 0) > 0:
            complexity += 1
        if stats["by_category"].get("color", 0) > 0:
            complexity += 1
        if stats["by_category"].get("spotlight", 0) > 0:
            complexity += 1
        complexity = min(10, complexity)

        # 人数
        headcount = 1 if complexity <= 5 else (2 if complexity <= 8 else 3)

        # 技能要求
        skills = ["基础灯光控制台操作"]
        if stats["by_category"].get("spotlight", 0) > 0:
            skills.append("追光/聚光使用")
        if stats["by_category"].get("effect", 0) > 0:
            skills.append("灯光特效设计")
        if stats["by_category"].get("color", 0) > 0:
            skills.append("色彩灯光设计")
        if scene_count > 2:
            skills.append("多场景灯光切换")

        # 特殊需求
        special = ""
        if stats["by_category"].get("effect", 0) > 2:
            special = "需要配合剧情实现复杂灯光变化效果"
        elif stats["by_category"].get("color", 0) > 0:
            special = "需要色彩灯光配合情绪表达"

        return CrewRequirement(
            role_key="lighting",
            role_name="灯光师",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"] if needed else [],
            special_needs=special,
            notes="基于剧本中灯光提示词分析" if needed else "剧本中未发现明确灯光需求",
        )

    def _build_sound_req(self, stats: Dict, script: str, scene_count: int) -> CrewRequirement:
        """构建音效师需求"""
        total = stats["total"]
        needed = total > 0

        complexity = min(10, total // 2 + scene_count // 2)
        if stats["by_category"].get("music", 0) > 0:
            complexity += 1
        if stats["by_category"].get("nature", 0) > 0:
            complexity += 1
        if stats["by_category"].get("action", 0) > 2:
            complexity += 1
        complexity = min(10, complexity)

        headcount = 1 if complexity <= 6 else 2

        skills = ["音效播放与混音"]
        if stats["by_category"].get("music", 0) > 0:
            skills.append("背景音乐设计")
        if stats["by_category"].get("nature", 0) > 0:
            skills.append("环境音设计")
        if stats["by_category"].get("action", 0) > 0:
            skills.append("现场音效同步")

        special = ""
        if stats["by_category"].get("music", 0) > 2:
            special = "需要多段背景音乐配合剧情情绪"
        elif stats["by_category"].get("nature", 0) > 2:
            special = "需要持续环境音并根据剧情调整音量"

        return CrewRequirement(
            role_key="sound",
            role_name="音效师",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"] if needed else [],
            special_needs=special,
            notes="基于剧本中音效提示词分析" if needed else "剧本中未发现明确音效需求",
        )

    def _build_stage_req(self, stats: Dict, script: str, scene_count: int) -> CrewRequirement:
        """构建舞美设计需求"""
        # 舞美设计几乎总是需要的（除非是完全无布景的独白剧）
        needed = scene_count > 0

        # 统计场景类型
        setting_count = stats["by_category"].get("setting", 0)
        complex_count = stats["by_category"].get("complex", 0)

        complexity = min(10, scene_count + setting_count // 2 + complex_count * 2)

        headcount = 1
        if complexity >= 7:
            headcount = 2

        skills = ["场景设计与搭建"]
        if scene_count > 2:
            skills.append("快速换景设计")
        if complex_count > 0:
            skills.append("复杂舞台装置设计")
            skills.append("机械/投影技术")

        special = ""
        if complex_count > 0:
            special = "需要复杂舞台装置（旋转/升降/移动/投影等）"
        elif scene_count > 3:
            special = "多场景需快速切换，建议使用可移动布景"

        return CrewRequirement(
            role_key="stage_design",
            role_name="舞美设计",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"][:3] if needed else [],
            special_needs=special,
            notes=f"剧本共{scene_count}个场景" if needed else "",
        )

    def _build_costume_req(self, stats: Dict, script: str, character_count: int) -> CrewRequirement:
        """构建服装师需求"""
        total = stats["total"]
        # 有明确服装描述，或角色数较多且非现代剧
        needed = total > 0

        complexity = min(10, total // 2 + character_count // 3)
        if stats["by_category"].get("special", 0) > 0:
            complexity += 2
        if stats["by_category"].get("change", 0) > 0:
            complexity += 1
        complexity = min(10, complexity)

        headcount = 1 if complexity <= 5 else 2

        skills = ["服装设计与制作"]
        if stats["by_category"].get("special", 0) > 0:
            skills.append("特殊服装制作")
        if stats["by_category"].get("change", 0) > 0:
            skills.append("快速换装管理")

        special = ""
        if stats["by_category"].get("special", 0) > 0:
            special = "需要特殊服装（古装/礼服/戏服/铠甲等）"

        return CrewRequirement(
            role_key="costume",
            role_name="服装师",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"] if needed else [],
            special_needs=special,
            notes="基于剧本中服装描述分析" if needed else "剧本中未发现明确服装需求，现代剧可由演员自备",
        )

    def _build_props_req(self, stats: Dict, script: str) -> CrewRequirement:
        """构建道具师需求"""
        total = stats["total"]
        needed = total > 0

        complexity = min(10, total // 3)
        if stats["by_category"].get("breakable", 0) > 0:
            complexity += 1
        if stats["by_category"].get("food", 0) > 0:
            complexity += 1
        complexity = max(1, min(10, complexity)) if needed else 0

        headcount = 1

        skills = ["道具准备与管理"]
        if stats["by_category"].get("handheld", 0) > 0:
            skills.append("手持道具使用指导")
        if stats["by_category"].get("breakable", 0) > 0:
            skills.append("易损道具管理")

        special = ""
        if stats["by_category"].get("food", 0) > 0:
            special = "需要可食用道具，注意保鲜和替换"
        elif stats["by_category"].get("breakable", 0) > 0:
            special = "需要易碎道具，准备备用件"

        return CrewRequirement(
            role_key="props",
            role_name="道具师",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"][:4] if needed else [],
            special_needs=special,
            notes="基于剧本中道具描述分析" if needed else "剧本中未发现明确道具需求",
        )

    def _build_makeup_req(self, stats: Dict, script: str, character_count: int) -> CrewRequirement:
        """构建化妆师需求"""
        total = stats["total"]
        needed = total > 0

        complexity = min(10, total)
        if stats["by_category"].get("special", 0) > 0:
            complexity += 2
        if stats["by_category"].get("effect", 0) > 0:
            complexity += 3
        complexity = min(10, complexity)

        headcount = 1 if complexity <= 5 else 2

        skills = ["基础化妆"]
        if stats["by_category"].get("special", 0) > 0:
            skills.append("特殊妆面设计（伤痕/老年/假发等）")
        if stats["by_category"].get("effect", 0) > 0:
            skills.append("特效化妆（假体/血浆等）")

        special = ""
        if stats["by_category"].get("effect", 0) > 0:
            special = "需要特效化妆，准备专业材料和工具"
        elif stats["by_category"].get("special", 0) > 0:
            special = "需要特殊妆面（伤痕/老年/假发等）"

        return CrewRequirement(
            role_key="makeup",
            role_name="化妆师",
            needed=needed,
            headcount=headcount if needed else 0,
            complexity=complexity if needed else 0,
            skill_requirements=skills if needed else [],
            evidence=stats["matches"] if needed else [],
            special_needs=special,
            notes="基于剧本中化妆描述分析" if needed else "剧本中未发现特殊化妆需求，现代剧演员可自行整理",
        )

    @staticmethod
    def _generate_overall_summary(
        requirements: Dict[str, CrewRequirement],
        scene_count: int,
        character_count: int,
        production_scale: str
    ) -> str:
        """生成总体制作建议"""
        needed = [r for r in requirements.values() if r.needed]
        not_needed = [r for r in requirements.values() if not r.needed]

        total_headcount = sum(r.headcount for r in needed)

        parts = [f"本剧为{scene_count}场景{production_scale}制作，共{character_count}个角色。"]
        parts.append(f"建议配置{total_headcount}名后台人员（{', '.join(r.role_name for r in needed)}）。")

        # 找出复杂度最高的岗位
        if needed:
            most_complex = max(needed, key=lambda r: r.complexity)
            parts.append(f"核心挑战在于{most_complex.role_name}（复杂度{most_complex.complexity}/10）。")

        if not_needed:
            parts.append(f"{', '.join(r.role_name for r in not_needed)}可由演员兼任或无需专门配置。")

        return "".join(parts)

    @staticmethod
    def _print_analysis_summary(analysis: CrewAnalysisResult) -> None:
        """打印分析结果摘要"""
        print(f"  ✅ 分析完成")
        print(f"  📊 场景数：{analysis.total_scenes} | 角色数：{analysis.total_characters}")
        print(f"  🎬 制作规模：{analysis.production_scale or '未评估'}")
        needed_roles = [r.role_name for r in analysis.requirements.values() if r.needed]
        print(f"  👥 需要岗位：{', '.join(needed_roles) if needed_roles else '无'}")
        print()

    # ============================================================
    # 通用方法
    # ============================================================

    @staticmethod
    def save_analysis(analysis: CrewAnalysisResult, output_path: str) -> str:
        """保存分析结果到 JSON 文件"""
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
        """从 JSON 文件加载分析结果"""
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
        """估算剧本中的场景数"""
        patterns = [
            r"第[一二三四五六七八九十\d]+幕",
            r"第[一二三四五六七八九十\d]+场",
            r"Scene\s+\d+",
            r"ACT\s+\d+",
            r"【第[一二三四五六七八九十\d]+场】",
            r"场景[：:]\s*\S+",
            r"地点[：:]\s*\S+",
        ]
        scenes = set()
        for pattern in patterns:
            matches = re.findall(pattern, script, re.IGNORECASE)
            scenes.update(matches)
        return max(len(scenes), 1)
