"""
CastingNuwa · 选角女娲
试镜任务设计器（Audition Designer）

角色的可观察表演要求 → 一套可直接执行的两轮试镜任务（AuditionTask）。

- 真实模式：调用 LLM 生成；服务失败抛 LLMServiceError（不回退假数据），
  JSON 解析失败重试后用确定性模板兜底（模板基于角色要求，不伪装成 AI 结果）。
- 演示模式（无 API Key）：直接用确定性模板，保证流程可体验。
"""

from typing import Optional, List
import re

from .models import RoleCard, AuditionTask, ObservationFocus, ProductionSettings
from .audition_prompts import AUDITION_SYSTEM_PROMPT, AUDITION_USER_PROMPT_TEMPLATE
from .llm_client import LLMClient, LLMServiceError


class AuditionDesigner:
    """根据角色要求设计两轮试镜任务"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def design_for_role(
        self,
        role_card: RoleCard,
        script_text: str = "",
        settings: Optional[ProductionSettings] = None,
        max_retries: int = 2,
    ) -> AuditionTask:
        """为单个角色生成试镜任务。真实服务故障抛 LLMServiceError。"""
        if self.llm.is_mock_mode:
            return self._build_template_task(role_card, script_text, settings)

        settings_section = self._format_settings(settings)
        script_section = self._format_script_section(script_text)
        user_prompt = AUDITION_USER_PROMPT_TEMPLATE.format(
            role_card_json=role_card.to_json(),
            settings_section=settings_section,
            script_section=script_section,
        )

        for attempt in range(max_retries + 1):
            result = self.llm.chat_json(AUDITION_SYSTEM_PROMPT, user_prompt)
            if "_parse_error" not in result:
                task = self._parse_task(result, role_card.role_name)
                if task and (task.scene_description or task.observation_focus):
                    return task
            if attempt < max_retries:
                print(f"  [AuditionDesigner] 重试 {attempt + 1}/{max_retries}")

        # 解析持续失败：用基于角色要求的确定性模板兜底（非伪造的 AI 结论）
        print("  [AuditionDesigner] LLM 返回无法解析，改用角色要求模板生成试镜任务")
        return self._build_template_task(role_card, script_text, settings)

    def design_all(
        self,
        role_cards: List[RoleCard],
        script_text: str = "",
        settings: Optional[ProductionSettings] = None,
    ) -> List[AuditionTask]:
        """为所有角色生成试镜任务，任一角色服务故障则向上抛出。"""
        tasks = []
        for card in role_cards:
            print(f"  设计试镜任务：{card.role_name}")
            tasks.append(self.design_for_role(card, script_text, settings))
        return tasks

    # ----------------------------------------------------------
    # 解析 LLM 返回
    # ----------------------------------------------------------
    def _parse_task(self, data: dict, role_name: str) -> Optional[AuditionTask]:
        if not isinstance(data, dict):
            return None
        try:
            raw_focus = data.get("observation_focus", [])
            focus = []
            if isinstance(raw_focus, list):
                for item in raw_focus:
                    if not isinstance(item, dict):
                        continue
                    focus.append(ObservationFocus(
                        focus=item.get("focus", "") or "",
                        explanation=item.get("explanation", "") or "",
                        positive_signals=self._as_str_list(item.get("positive_signals")),
                        negative_signals=self._as_str_list(item.get("negative_signals")),
                    ))
            return AuditionTask(
                role_name=data.get("role_name", role_name) or role_name,
                scene_description=data.get("scene_description", "") or "",
                script_excerpt=data.get("script_excerpt", "") or "",
                observation_focus=focus,
                adjustment_instruction=data.get("adjustment_instruction", "") or "",
                retest_task=data.get("retest_task", "") or "",
                retest_focus=data.get("retest_focus", "") or "",
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [AuditionDesigner] 解析失败：{exc}")
            return None

    @staticmethod
    def _as_str_list(value) -> List[str]:
        if isinstance(value, list):
            return [str(x) for x in value if x]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    # ----------------------------------------------------------
    # 确定性模板兜底（演示模式 / 解析失败时使用）
    # ----------------------------------------------------------
    def _build_template_task(
        self,
        role_card: RoleCard,
        script_text: str = "",
        settings: Optional[ProductionSettings] = None,
    ) -> AuditionTask:
        guide = role_card.casting_guide
        requirements = guide.observable_requirements

        style_hint = ""
        if settings and settings.performance_style:
            style_hint = f"整体表演风格按剧团设定：{settings.performance_style}。"

        scene_parts = [
            f"试镜场景围绕「{role_card.role_name}」的一段关键冲突展开。",
        ]
        if guide.audition_focus:
            scene_parts.append(f"考察重点：{guide.audition_focus}。")
        if style_hint:
            scene_parts.append(style_hint)
        scene_parts.append(
            "请演员明确：此刻角色想要什么、在对谁说话、最大的阻碍是什么，再开始表演。"
        )
        scene_description = "".join(scene_parts)

        script_excerpt = self._extract_excerpt(script_text, role_card.role_name)
        if not script_excerpt and guide.audition_focus:
            script_excerpt = (
                f"（请从剧本中选取「{role_card.role_name}」最能体现以下重点的 1-2 分钟片段："
                f"{guide.audition_focus}）"
            )

        focus = []
        for req in requirements[:3]:
            signals = req.observable_signals or [req.requirement]
            negative = [
                "没有出现上述具体信号，而是用提高音量、夸张表情等笼统方式代替细节"
            ]
            explanation = req.audition_check or (
                f"对应角色特征「{req.source_trait or req.requirement}」，"
                "看演员能否把它变成可观察的动作而非自我说明。"
            )
            focus.append(ObservationFocus(
                focus=req.requirement,
                explanation=explanation,
                positive_signals=signals[:4],
                negative_signals=negative,
            ))

        must_reqs = [r for r in requirements if r.must_have]
        anchor = must_reqs[0] if must_reqs else (requirements[0] if requirements else None)
        if anchor:
            adjustment_instruction = (
                f"这一遍保持台词不变，但请把你刚才最直白、最外放的处理收住，"
                f"改为围绕「{anchor.requirement}」"
                f"（如{('、'.join(anchor.observable_signals[:2]) if anchor.observable_signals else '更细微的动作')}）"
                "来传递同样的意图，看看你能否换一种方式完成。"
            )
            retest_focus = (
                f"对照第一遍，观察演员是否真的改变了表达方式来满足「{anchor.requirement}」，"
                "变化是否服务于情境任务，而不是表面收敛。"
            )
        else:
            adjustment_instruction = (
                "这一遍保持台词不变，请用与第一遍相反的力度处理同一段"
                "（外放改克制，或克制改外放），但保持角色目标不变。"
            )
            retest_focus = "对照第一遍，观察演员能否理解并执行调整指令，变化是否有依据。"

        return AuditionTask(
            role_name=role_card.role_name,
            scene_description=scene_description,
            script_excerpt=script_excerpt,
            observation_focus=focus,
            adjustment_instruction=adjustment_instruction,
            retest_task="请演员在上述调整指令下重演同一片段，评委不打断、只记录。",
            retest_focus=retest_focus,
        )

    @staticmethod
    def _extract_excerpt(script_text: str, role_name: str, max_chars: int = 600) -> str:
        """从剧本中粗略截取含角色名的一段台词作为试镜片段。"""
        if not script_text or not role_name:
            return ""
        lines = script_text.splitlines()
        hit = next(
            (i for i, line in enumerate(lines) if role_name in line and len(line.strip()) > 0),
            None,
        )
        if hit is None:
            return ""
        start = max(0, hit - 2)
        end = min(len(lines), hit + 18)
        excerpt = "\n".join(lines[start:end]).strip()
        if len(excerpt) > max_chars:
            excerpt = excerpt[:max_chars] + "……"
        return excerpt

    @staticmethod
    def _format_settings(settings: Optional[ProductionSettings]) -> str:
        if not settings:
            return ""
        parts = ["\n【剧团制作与选角设定】"]
        if settings.performance_style:
            parts.append(f"- 表演风格：{settings.performance_style}")
        if settings.role_interpretation:
            parts.append(f"- 导演阐述/角色理解：{settings.role_interpretation}")
        if settings.must_have_requirements:
            parts.append("- 必须满足：" + "、".join(settings.must_have_requirements))
        if settings.can_rehearse:
            parts.append("- 可排练改善：" + "、".join(settings.can_rehearse))
        if settings.schedule_constraints:
            parts.append(f"- 档期/排练时间约束：{settings.schedule_constraints}")
        parts.append(f"- 是否接受反串：{'是' if settings.allow_cross_gender else '否'}")
        parts.append(f"- 是否接受兼角：{'是' if settings.allow_double_casting else '否'}")
        return "\n".join(parts) + "\n"

    @staticmethod
    def _format_script_section(script_text: str) -> str:
        if not script_text or not script_text.strip():
            return ""
        snippet = script_text.strip()
        if len(snippet) > 4000:
            snippet = snippet[:4000] + "\n……（剧本较长，已截断，试镜片段优先取角色关键段落）"
        return f"\n【剧本原文（供选取试镜台词）】\n---\n{snippet}\n---\n"
