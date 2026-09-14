#!/usr/bin/env python3
"""
CastingNuwa · 选角女娲 — Web 应用

基于 Gradio 的交互式 Web 界面，串联完整工作流：
1. 角色蒸馏：剧本 → 角色卡
2. 演员画像：演员材料 → 演员画像
3. 智能匹配：角色卡 × 演员画像 → 匹配报告
4. 选角报告：匹配矩阵 + 推荐汇总

运行方式：
    pip install gradio openai
    python app.py
"""

import os
import sys
import json
import gradio as gr

# 将 src 目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.role_distiller import RoleDistiller
from src.actor_profiler import ActorProfiler
from src.matching_engine import MatchingEngine
from src.llm_client import LLMClient
from src.models import RoleCard, CrewAnalysisResult
from src.actor_models import ActorProfile
from src.crew_analyzer import CrewAnalyzer


# ============================================================
# 全局状态
# ============================================================

class AppState:
    """应用状态管理"""
    def __init__(self):
        self.llm_client = LLMClient()
        self.role_distiller = RoleDistiller(llm_client=self.llm_client)
        self.actor_profiler = ActorProfiler(llm_client=self.llm_client)
        self.matching_engine = MatchingEngine(llm_client=self.llm_client)
        self.crew_analyzer = CrewAnalyzer(llm_client=self.llm_client)

        self.role_cards = []       # 已生成的角色卡列表
        self.actor_profiles = []   # 已生成的演员画像列表
        self.casting_report = None # 选角报告
        self.crew_analysis = None  # 制作团队需求分析结果

    def is_mock(self):
        return self.llm_client.is_mock_mode


state = AppState()


# ============================================================
# 工具函数
# ============================================================

def load_example_script():
    """加载示例剧本"""
    path = os.path.join(os.path.dirname(__file__), "examples", "sample_script.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_example_actors():
    """加载示例演员材料"""
    path = os.path.join(os.path.dirname(__file__), "examples", "sample_actors.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def format_role_card_markdown(card: RoleCard) -> str:
    """将角色卡格式化为 Markdown"""
    lines = [
        f"## 🎭 {card.role_name}",
        f"",
        f"**身份**：{card.profile.identity or '未提及'}",
        f"**年龄/性别**：{card.profile.age_gender or '未提及'}",
        f"",
        f"### 性格特质",
    ]
    for t in card.personality:
        lines.append(f"- **{t.trait}**：{t.evidence}")
        if t.nuance:
            lines.append(f"  - 细微差别：{t.nuance}")

    lines.extend([
        f"",
        f"### 核心动机",
        f"- **表层欲望（Want）**：{card.motivation.want}",
        f"- **深层需求（Need）**：{card.motivation.need}",
        f"- **核心恐惧**：{card.motivation.fear}",
        f"",
        f"### 语言 DNA",
        f"- 用词：{card.linguistic_dna.vocabulary}",
        f"- 句式：{card.linguistic_dna.sentence_style}",
        f"- 语气：{card.linguistic_dna.tone}",
        f"",
        f"### 情感弧线",
        f"- 开场：{card.emotional_arc.opening_state}",
        f"- 类型：{card.emotional_arc.arc_type}",
        f"- 结尾：{card.emotional_arc.ending_state}",
        f"",
        f"### 🎬 选角指引",
        f"- **适合演员类型**：{card.casting_guide.actor_type}",
        f"- **核心能力要求**：",
    ])
    for req in card.casting_guide.core_requirements:
        lines.append(f"  - {req}")
    lines.extend([
        f"- **试镜重点**：{card.casting_guide.audition_focus}",
        f"- **选角风险**：{card.casting_guide.risks}",
    ])

    return "\n".join(lines)


def format_actor_profile_markdown(profile: ActorProfile) -> str:
    """将演员画像格式化为 Markdown"""
    lines = [
        f"## 🎬 {profile.actor_name}",
        f"",
        f"**年龄/性别**：{profile.basic_info.age_gender or '未提供'}",
        f"**表演经验**：{profile.basic_info.experience or '未提供'}",
        f"**背景**：{profile.basic_info.background or '未提供'}",
        f"",
        f"### 声线特质",
        f"- 音高：{profile.vocal_traits.pitch} | 音色：{profile.vocal_traits.timbre}",
        f"- 语速节奏：{profile.vocal_traits.pace}",
        f"- 优势：{', '.join(profile.vocal_traits.strengths) if profile.vocal_traits.strengths else '无'}",
        f"- 局限：{', '.join(profile.vocal_traits.limitations) if profile.vocal_traits.limitations else '无'}",
        f"",
        f"### 面部表现力",
        f"- 表情幅度：{profile.facial_expressiveness.expression_range}",
        f"- 眼神传达：{profile.facial_expressiveness.eye_contact}",
        f"",
        f"### 肢体表现力",
        f"- 手势丰富度：{profile.physical_expressiveness.gesture_richness}",
        f"- 姿态自然度：{profile.physical_expressiveness.posture_naturalness}",
        f"- 空间使用：{profile.physical_expressiveness.spatial_usage}",
        f"",
        f"### 情感表达范围",
        f"- 能表达的情感：{', '.join(profile.emotional_range.expressible_emotions) if profile.emotional_range.expressible_emotions else '未分析'}",
        f"- 情感深度：{profile.emotional_range.emotional_depth}",
        f"- 最擅长：{', '.join(profile.emotional_range.strongest_emotions) if profile.emotional_range.strongest_emotions else '无'}",
        f"",
        f"### 气质类型",
        f"- 主要气质：{profile.temperament.primary_type}",
        f"- 次要气质：{profile.temperament.secondary_type}",
        f"- 整体印象：{profile.temperament.overall_impression}",
        f"- 适合类型：{', '.join(profile.temperament.suitable_genres) if profile.temperament.suitable_genres else '未分析'}",
        f"",
        f"### 表演风格与潜力",
        f"- 风格倾向：{profile.acting_style.style_tendency}",
        f"- 自然度：{profile.acting_style.naturalness}",
        f"- 台词功底：{profile.acting_style.line_delivery}",
        f"- 经验水平：{profile.acting_style.experience_level}",
        f"- 潜力评估：{profile.acting_style.potential}",
        f"- 发展建议：",
    ]
    for s in profile.acting_style.development_suggestions:
        lines.append(f"  - {s}")

    return "\n".join(lines)


def format_match_result_markdown(match) -> str:
    """将匹配结果格式化为 Markdown"""
    score_color = "🟢" if match.overall_score >= 75 else ("🟡" if match.overall_score >= 60 else "🔴")

    lines = [
        f"## {score_color} {match.role_name} × {match.actor_name}",
        f"",
        f"**综合匹配度：{match.overall_score:.0f}分 | {match.match_level}**",
        f"",
        f"> {match.summary}",
        f"",
    ]

    if match.match_reasons:
        lines.append("### ✅ 匹配优势")
        for r in match.match_reasons:
            lines.append(f"- {r}")
        lines.append("")

    if match.risks:
        lines.append("### ⚠️ 风险提示")
        for r in match.risks:
            lines.append(f"- {r}")
        lines.append("")

    if match.audition_suggestions:
        lines.append("### 🎬 试镜建议")
        for s in match.audition_suggestions:
            lines.append(f"- {s}")
        lines.append("")

    if match.dimension_scores:
        lines.append("### 📊 分维度评分")
        lines.append("")
        lines.append("| 维度 | 评分 | 理由 | 风险 |")
        lines.append("|------|------|------|------|")
        for ds in match.dimension_scores:
            lines.append(f"| {ds.dimension} | {ds.score:.0f} | {ds.reason} | {ds.risk} |")
        lines.append("")

    return "\n".join(lines)


def format_crew_analysis_markdown(analysis: CrewAnalysisResult) -> str:
    """将制作团队需求分析结果格式化为 Markdown"""
    if not analysis or not analysis.requirements:
        return "### 暂无分析结果\n\n请输入剧本后点击分析按钮。"

    lines = [
        f"## 🎬 制作团队需求分析",
        f"",
        f"**剧本**：{analysis.script_title or '未识别'}",
        f"**场景数**：{analysis.total_scenes} | **角色数**：{analysis.total_characters}",
        f"**制作规模**：{analysis.production_scale or '未评估'}",
        f"",
    ]

    # 统计需要的岗位
    needed = [r for r in analysis.requirements.values() if r.needed]
    not_needed = [r for r in analysis.requirements.values() if not r.needed]

    if needed:
        lines.append("### ✅ 需要的岗位")
        lines.append("")
        lines.append("| 岗位 | 人数 | 复杂度 | 核心技能 |")
        lines.append("|------|------|--------|----------|")
        for r in needed:
            skills = "、".join(r.skill_requirements[:2]) if r.skill_requirements else "-"
            lines.append(f"| {r.role_name} | {r.headcount}人 | {r.complexity}/10 | {skills} |")
        lines.append("")

    if not_needed:
        lines.append(f"### ➖ 不需要的岗位")
        lines.append("")
        lines.append(f"{', '.join(r.role_name for r in not_needed)}")
        lines.append("")

    # 详细信息
    lines.append("### 📋 岗位详情")
    lines.append("")
    for key, req in analysis.requirements.items():
        status = "✅ 需要" if req.needed else "➖ 不需要"
        lines.append(f"#### {req.role_name}（{status}）")
        lines.append("")
        if req.needed:
            lines.append(f"- **建议人数**：{req.headcount}人")
            lines.append(f"- **复杂度**：{req.complexity}/10")
            if req.skill_requirements:
                lines.append(f"- **技能要求**：{', '.join(req.skill_requirements)}")
            if req.special_needs:
                lines.append(f"- **特殊需求**：{req.special_needs}")
            if req.evidence:
                lines.append(f"- **剧本依据**：")
                for ev in req.evidence[:3]:
                    lines.append(f"  - {ev}")
                if len(req.evidence) > 3:
                    lines.append(f"  - ... 等共{len(req.evidence)}条")
            if req.notes:
                lines.append(f"- **备注**：{req.notes}")
        else:
            if req.notes:
                lines.append(f"- {req.notes}")
            elif req.evidence:
                lines.append(f"- 依据：{req.evidence[0]}")
        lines.append("")

    if analysis.overall_summary:
        lines.append("### 💡 总体建议")
        lines.append("")
        lines.append(f"> {analysis.overall_summary}")
        lines.append("")

    return "\n".join(lines)


# ============================================================
# 标签页 1：角色蒸馏
# ============================================================

def distill_roles(script_text):
    """执行角色蒸馏"""
    if not script_text or not script_text.strip():
        return "⚠️ 请输入剧本内容", "", []

    # 检测候选角色
    candidates = RoleDistiller.extract_characters_from_script(script_text)
    candidate_info = f"检测到候选角色：{', '.join(candidates)}" if candidates else "未检测到明确角色名"

    # 执行蒸馏
    role_cards = state.role_distiller.distill_all(script_text)
    state.role_cards = role_cards

    if not role_cards:
        return f"❌ 角色蒸馏失败\n\n{candidate_info}", "", []

    # 生成 Markdown 展示
    md_parts = [f"### 蒸馏完成：共 {len(role_cards)} 个角色\n"]
    for card in role_cards:
        md_parts.append(format_role_card_markdown(card))
        md_parts.append("\n---\n")

    # JSON 输出
    json_output = json.dumps(
        {"roles": [c.to_dict() for c in role_cards]},
        indent=2, ensure_ascii=False
    )

    # 角色名列表（用于匹配标签页的下拉框）
    role_names = [c.role_name for c in role_cards]

    return "\n".join(md_parts), json_output, role_names


def update_role_dropdown():
    """更新角色下拉框选项"""
    names = [c.role_name for c in state.role_cards]
    return gr.update(choices=names, value=names[0] if names else None)


# ============================================================
# 标签页 2：演员画像
# ============================================================

def profile_actors(actor_text):
    """执行演员画像"""
    if not actor_text or not actor_text.strip():
        return "⚠️ 请输入演员材料", "", []

    # 解析多个演员（以【演员】分隔）
    import re
    actor_blocks = re.split(r'\n---\s*\n', actor_text.strip())

    profiles = []
    for block in actor_blocks:
        # 提取演员名
        name_match = re.search(r'【演员[^】]*[:：]\s*([^】]+)】', block)
        actor_name = name_match.group(1).strip() if name_match else "未命名演员"

        profile = state.actor_profiler.profile_from_text(
            actor_material=block,
            actor_name=actor_name,
        )
        if profile:
            profiles.append(profile)

    state.actor_profiles = profiles

    if not profiles:
        return "❌ 演员画像生成失败", "", []

    # 生成 Markdown
    md_parts = [f"### 画像完成：共 {len(profiles)} 位演员\n"]
    for p in profiles:
        md_parts.append(format_actor_profile_markdown(p))
        md_parts.append("\n---\n")

    json_output = json.dumps(
        {"actors": [p.to_dict() for p in profiles]},
        indent=2, ensure_ascii=False
    )

    actor_names = [p.actor_name for p in profiles]
    return "\n".join(md_parts), json_output, actor_names


def update_actor_dropdown():
    """更新演员下拉框选项"""
    names = [p.actor_name for p in state.actor_profiles]
    return gr.update(choices=names, value=names[0] if names else None)


def profile_from_video_file(video_path, actor_name, text_material):
    """从视频文件生成演员画像（三模态：文本+音频+视频）"""
    if not video_path:
        return "⚠️ 请先上传视频文件", ""

    print(f"\n[Web] 从视频生成演员画像: {video_path}")

    try:
        profile = state.actor_profiler.profile_from_video(
            video_path=video_path,
            actor_name=actor_name or "视频演员",
            text_material=text_material or "",
        )

        if profile is None:
            return "❌ 视频分析失败", ""

        # 添加到状态
        state.actor_profiles.append(profile)

        md = format_actor_profile_markdown(profile)
        json_output = profile.to_json()

        return md, json_output

    except Exception as e:
        import traceback
        error_msg = f"❌ 视频处理出错：{str(e)}\n\n{traceback.format_exc()}"
        return error_msg, ""


def profile_from_audio_file(audio_path, actor_name, text_material):
    """从音频文件生成演员画像（双模态：文本+音频）"""
    if not audio_path:
        return "⚠️ 请先上传音频文件", ""

    print(f"\n[Web] 从音频生成演员画像: {audio_path}")

    try:
        profile = state.actor_profiler.profile_from_audio(
            audio_path=audio_path,
            actor_name=actor_name or "音频演员",
            text_material=text_material or "",
        )

        if profile is None:
            return "❌ 音频分析失败", ""

        # 添加到状态
        state.actor_profiles.append(profile)

        md = format_actor_profile_markdown(profile)
        json_output = profile.to_json()

        return md, json_output

    except Exception as e:
        import traceback
        error_msg = f"❌ 音频处理出错：{str(e)}\n\n{traceback.format_exc()}"
        return error_msg, ""


# ============================================================
# 标签页 3：智能匹配
# ============================================================

def match_single(role_name, actor_name):
    """匹配单个角色和演员"""
    if not role_name or not actor_name:
        return "⚠️ 请先在前面的标签页生成角色卡和演员画像"

    role = next((r for r in state.role_cards if r.role_name == role_name), None)
    actor = next((a for a in state.actor_profiles if a.actor_name == actor_name), None)

    if not role or not actor:
        return "❌ 未找到对应的角色卡或演员画像"

    match = state.matching_engine.match_one(role, actor)
    if not match:
        return "❌ 匹配失败"

    return format_match_result_markdown(match)


def run_full_matching():
    """执行全量匹配"""
    if not state.role_cards or not state.actor_profiles:
        return "⚠️ 请先在前面的标签页生成角色卡和演员画像", ""

    report = state.matching_engine.match_all(state.role_cards, state.actor_profiles)
    state.casting_report = report

    # 生成报告 Markdown
    lines = [
        f"## 📋 选角报告",
        f"",
        f"**角色数**：{report.role_count} | **演员数**：{report.actor_count} | **匹配组合**：{len(report.results)}",
        f"",
        f"### 🏆 推荐汇总",
        f"",
        f"| 角色 | 推荐演员 | 匹配度 | 等级 |",
        f"|------|----------|--------|------|",
    ]

    for role_name, actor_name in report.recommendations.items():
        best = report.get_best_actor_for_role(role_name)
        if best:
            lines.append(f"| {role_name} | {actor_name} | {best.overall_score:.0f}分 | {best.match_level} |")

    lines.append("")
    lines.append("### 📊 匹配矩阵")
    lines.append("")

    # 匹配矩阵
    role_names = [r.role_name for r in state.role_cards]
    actor_names = [a.actor_name for a in state.actor_profiles]

    header = "| 角色 \\ 演员 | " + " | ".join(actor_names) + " |"
    separator = "|" + "|".join(["---"] * (len(actor_names) + 1)) + "|"
    lines.append(header)
    lines.append(separator)

    for role_name in role_names:
        row = f"| **{role_name}** |"
        for actor_name in actor_names:
            match = next(
                (m for m in report.results if m.role_name == role_name and m.actor_name == actor_name),
                None
            )
            if match:
                score_str = f"{match.overall_score:.0f}"
                if match.overall_score >= 75:
                    row += f" 🟢{score_str} |"
                elif match.overall_score >= 60:
                    row += f" 🟡{score_str} |"
                else:
                    row += f" 🔴{score_str} |"
            else:
                row += " - |"
        lines.append(row)

    lines.append("")
    lines.append("### 📝 详细匹配结果")
    lines.append("")

    for role_name in role_names:
        role_results = sorted(
            [m for m in report.results if m.role_name == role_name],
            key=lambda x: x.overall_score,
            reverse=True,
        )
        for m in role_results:
            lines.append(format_match_result_markdown(m))
            lines.append("")

    json_output = report.to_json()
    return "\n".join(lines), json_output


# ============================================================
# 标签页 4：制作团队需求分析
# ============================================================

def analyze_crew(script_text):
    """执行制作团队需求分析"""
    if not script_text or not script_text.strip():
        return "⚠️ 请输入剧本内容", ""

    try:
        analysis = state.crew_analyzer.analyze(script_text)
        state.crew_analysis = analysis
        markdown = format_crew_analysis_markdown(analysis)
        json_output = analysis.to_json()
        return markdown, json_output
    except Exception as e:
        return f"❌ 分析失败：{str(e)}", ""


# ============================================================
# Gradio 界面构建
# ============================================================

def build_ui():
    """构建 Gradio 界面"""

    with gr.Blocks(
        title="CastingNuwa · 选角女娲",
    ) as demo:

        gr.Markdown("# 🎭 CastingNuwa · 选角女娲", elem_classes="main-title")
        gr.Markdown("### 基于思维蒸馏的 AI 戏剧选角辅助系统", elem_classes="subtitle")
        gr.Markdown("女娲造人，我们造角色卡。蒸馏戏剧角色的认知操作系统，智能匹配演员与角色。")

        # Mock 模式提示
        if state.is_mock():
            gr.Markdown(
                "⚠️ **当前为演示模式**：未配置 LLM API Key，输出为示例数据。"
                "配置 `LLM_API_KEY` 环境变量后可使用真实 AI 分析。详见 `.env.example`。",
                elem_classes="mock-banner",
            )

        with gr.Tabs():

            # ========== 标签页 1：角色蒸馏 ==========
            with gr.Tab("📝 角色蒸馏"):
                gr.Markdown("### 输入剧本，AI 自动蒸馏所有角色的认知操作系统")

                with gr.Row():
                    with gr.Column(scale=1):
                        script_input = gr.Textbox(
                            label="剧本内容",
                            placeholder="在此粘贴剧本，或点击下方按钮加载示例剧本...",
                            lines=20,
                            value=load_example_script(),
                        )
                        with gr.Row():
                            load_example_btn = gr.Button("📄 加载示例剧本", variant="secondary")
                            clear_btn = gr.Button("🗑️ 清空", variant="secondary")
                            distill_btn = gr.Button("🎭 开始角色蒸馏", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        role_output = gr.Markdown(label="角色卡结果")
                        role_json = gr.Code(label="JSON 输出", language="json", visible=True)

                load_example_btn.click(
                    fn=load_example_script,
                    outputs=script_input,
                )
                clear_btn.click(
                    fn=lambda: "",
                    outputs=script_input,
                )
                distill_btn.click(
                    fn=distill_roles,
                    inputs=script_input,
                    outputs=[role_output, role_json],
                )

            # ========== 标签页 2：演员画像 ==========
            with gr.Tab("🎬 演员画像"):
                gr.Markdown("### 支持文本/音频/视频多模态输入，AI 生成 7 维度演员画像")

                with gr.Tabs():
                    # --- 文本模式 ---
                    with gr.Tab("📝 文本模式"):
                        with gr.Row():
                            with gr.Column(scale=1):
                                actor_input = gr.Textbox(
                                    label="演员材料",
                                    placeholder="在此粘贴演员的自我介绍和试镜片段...\n\n多位演员用 --- 分隔，格式参考示例。",
                                    lines=18,
                                    value=load_example_actors(),
                                )
                                with gr.Row():
                                    load_actor_btn = gr.Button("📄 加载示例", variant="secondary")
                                    clear_actor_btn = gr.Button("🗑️ 清空", variant="secondary")
                                    profile_btn = gr.Button("🎬 生成画像", variant="primary", size="lg")

                            with gr.Column(scale=1):
                                actor_output = gr.Markdown(label="演员画像结果")
                                actor_json = gr.Code(label="JSON 输出", language="json")

                        load_actor_btn.click(
                            fn=load_example_actors,
                            outputs=actor_input,
                        )
                        clear_actor_btn.click(
                            fn=lambda: "",
                            outputs=actor_input,
                        )
                        profile_btn.click(
                            fn=profile_actors,
                            inputs=actor_input,
                            outputs=[actor_output, actor_json],
                        )

                    # --- 视频模式（三模态） ---
                    with gr.Tab("🎥 视频模式（三模态）"):
                        gr.Markdown("上传试镜视频，AI 自动提取音频（Whisper转写+声学特征）+ 视觉（面部表情+肢体语言），三模态融合分析")

                        with gr.Row():
                            with gr.Column(scale=1):
                                video_actor_name = gr.Textbox(
                                    label="演员姓名（可选）",
                                    placeholder="输入演员姓名，不填则自动命名",
                                )
                                video_upload = gr.Video(
                                    label="上传试镜视频",
                                    sources=["upload"],
                                )
                                video_extra_text = gr.Textbox(
                                    label="额外文本材料（可选，如自我介绍）",
                                    placeholder="可粘贴演员的自我介绍等文本材料...",
                                    lines=4,
                                )
                                video_profile_btn = gr.Button(
                                    "🎬 从视频生成画像（三模态）",
                                    variant="primary",
                                    size="lg",
                                )
                                gr.Markdown("""
                                **分析内容：**
                                - 🎵 音频：Whisper 语音转写 + 音高/音色/语速/韵律等声学特征
                                - 👤 视觉：MediaPipe 面部关键点（笑容/眼神/微表情）+ 姿态检测（手势/姿态/空间使用）
                                - 📝 文本：转写文本 + 额外材料
                                - 🧠 融合：LLM 综合三模态信息生成演员画像
                                """)

                            with gr.Column(scale=1):
                                video_output = gr.Markdown(label="视频分析结果")
                                video_json = gr.Code(label="JSON 输出", language="json")

                        video_profile_btn.click(
                            fn=profile_from_video_file,
                            inputs=[video_upload, video_actor_name, video_extra_text],
                            outputs=[video_output, video_json],
                        )

                    # --- 音频模式（双模态） ---
                    with gr.Tab("🎵 音频模式（双模态）"):
                        gr.Markdown("上传试镜音频，AI 进行 Whisper 转写 + 声学特征分析，双模态融合生成演员画像")

                        with gr.Row():
                            with gr.Column(scale=1):
                                audio_actor_name = gr.Textbox(
                                    label="演员姓名（可选）",
                                    placeholder="输入演员姓名，不填则自动命名",
                                )
                                audio_upload = gr.Audio(
                                    label="上传试镜音频",
                                    sources=["upload"],
                                    type="filepath",
                                )
                                audio_extra_text = gr.Textbox(
                                    label="额外文本材料（可选，如自我介绍）",
                                    placeholder="可粘贴演员的自我介绍等文本材料...",
                                    lines=4,
                                )
                                audio_profile_btn = gr.Button(
                                    "🎬 从音频生成画像（双模态）",
                                    variant="primary",
                                    size="lg",
                                )
                                gr.Markdown("""
                                **分析内容：**
                                - 🎵 音频：Whisper 语音转写 + 音高/音色/语速/韵律等声学特征
                                - 📝 文本：转写文本 + 额外材料
                                - 🧠 融合：LLM 综合双模态信息生成演员画像
                                """)

                            with gr.Column(scale=1):
                                audio_output = gr.Markdown(label="音频分析结果")
                                audio_json = gr.Code(label="JSON 输出", language="json")

                        audio_profile_btn.click(
                            fn=profile_from_audio_file,
                            inputs=[audio_upload, audio_actor_name, audio_extra_text],
                            outputs=[audio_output, audio_json],
                        )

            # ========== 标签页 3：智能匹配 ==========
            with gr.Tab("🎯 智能匹配"):
                gr.Markdown("### 选择角色和演员，AI 进行多维度匹配分析")

                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("**请先在前面的标签页生成角色卡和演员画像**")
                        role_dropdown = gr.Dropdown(
                            label="选择角色",
                            choices=[],
                            interactive=True,
                        )
                        actor_dropdown = gr.Dropdown(
                            label="选择演员",
                            choices=[],
                            interactive=True,
                        )
                        refresh_btn = gr.Button("🔄 刷新列表", variant="secondary")
                        match_btn = gr.Button("🎯 开始匹配", variant="primary", size="lg")

                        gr.Markdown("---")
                        full_match_btn = gr.Button("📋 执行全量匹配（所有角色×所有演员）", variant="primary")

                    with gr.Column(scale=2):
                        match_output = gr.Markdown(label="匹配结果")

                refresh_btn.click(
                    fn=lambda: (update_role_dropdown(), update_actor_dropdown()),
                    outputs=[role_dropdown, actor_dropdown],
                )
                match_btn.click(
                    fn=match_single,
                    inputs=[role_dropdown, actor_dropdown],
                    outputs=match_output,
                )
                full_match_btn.click(
                    fn=run_full_matching,
                    outputs=[match_output],
                )

            # ========== 标签页 4：制作团队需求分析 ==========
            with gr.Tab("🎬 制作团队分析"):
                gr.Markdown("### 输入剧本，AI 自动分析所需的后台岗位与人员配置")
                gr.Markdown("支持分析：灯光师、音效师、舞美设计、服装师、道具师、化妆师")

                with gr.Row():
                    with gr.Column(scale=1):
                        crew_script_input = gr.Textbox(
                            label="剧本内容",
                            placeholder="在此粘贴剧本，包含舞台指示、场景描述、灯光/音效提示等...",
                            lines=18,
                        )
                        with gr.Row():
                            crew_load_example_btn = gr.Button("📄 加载示例剧本", variant="secondary")
                            crew_analyze_btn = gr.Button("🔍 分析制作团队需求", variant="primary", size="lg")

                        gr.Markdown("---")
                        gr.Markdown("""
                        **分析维度**：
                        - 灯光师：灯光提示、场景切换、特殊光效
                        - 音效师：音效提示、背景音乐、现场播放
                        - 舞美设计：场景数量、换景难度、舞台装置
                        - 服装师：服装描述、换装次数、特殊服装
                        - 道具师：手持道具、场景道具、特殊道具
                        - 化妆师：特殊化妆、妆面变化
                        """)

                    with gr.Column(scale=2):
                        crew_output = gr.Markdown(label="分析结果")
                        with gr.Accordion("📋 JSON 原始数据", open=False):
                            crew_json_output = gr.Code(label="JSON", language="json")

                crew_load_example_btn.click(
                    fn=load_example_script,
                    outputs=crew_script_input,
                )
                crew_analyze_btn.click(
                    fn=analyze_crew,
                    inputs=[crew_script_input],
                    outputs=[crew_output, crew_json_output],
                )

            # ========== 标签页 5：关于 ==========
            with gr.Tab("ℹ️ 关于"):
                gr.Markdown("""
                ## CastingNuwa · 选角女娲

                ### 项目理念

                灵感来源于 GitHub 开源项目 [nuwa-skill](https://github.com/alchaincyf/nuwa-skill)（女娲.skill）。

                nuwa-skill 蒸馏的是真实人物的思维方式（心智模型、决策启发式、表达 DNA），让 AI 用乔布斯、芒格、费曼的思维方式帮你分析问题。

                **CastingNuwa 将这一理念迁移到戏剧领域**：蒸馏戏剧角色的"认知操作系统"——性格特质、核心动机、行为模式、语言 DNA、情感弧线——生成结构化的"角色卡"，再与演员的多维度画像做智能匹配，辅助导演做出可解释的选角决策。

                ### 工作流程

                1. **角色蒸馏**：输入剧本 → AI 自动分析所有角色，生成 7 维度角色卡
                2. **演员画像**：输入演员材料 → AI 生成 7 维度演员画像（支持文本/音频/视频）
                3. **智能匹配**：角色卡 × 演员画像 → 匹配度评分 + 匹配理由 + 风险提示 + 试镜建议
                4. **制作团队分析**：输入剧本 → AI 分析所需后台岗位（灯光/音效/舞美/服装/道具/化妆）
                5. **选角报告**：全量匹配矩阵 + 推荐汇总

                ### 角色卡 7 维度

                1. 基本信息
                2. 性格特质（附剧本证据）
                3. 核心动机（Want / Need / Fear）
                4. 行为模式
                5. 语言 DNA
                6. 情感弧线
                7. **选角指引**（适合演员类型、核心能力要求、试镜重点、风险提示）

                ### 技术栈

                - LLM 推理：OpenAI 兼容 API（DeepSeek / 智谱 GLM / 豆包 / 通义千问等）
                - Web 界面：Gradio
                - 数据模型：Python dataclass + JSON

                ### 项目阶段

                - ✅ Phase 1：角色蒸馏模块
                - ✅ Phase 2：演员画像模块（文本分析）
                - ✅ Phase 3：匹配引擎 + Web 界面
                - ✅ Phase 4：视频/音频多模态演员画像（Whisper + MediaPipe + librosa）
                - ✅ Phase 5：制作团队需求分析（灯光/音效/舞美/服装/道具/化妆）
                - 🔲 Phase 6：真实场景验证与迭代
                """)

        gr.Markdown("---")
        gr.Markdown("*CastingNuwa · 选角女娲 | 基于思维蒸馏的 AI 戏剧选角辅助系统*")

    return demo


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(),
        css="""
        .main-title { text-align: center; margin-bottom: 0; }
        .subtitle { text-align: center; color: #666; margin-top: 0; }
        .mock-banner { background: #fff3cd; padding: 10px; border-radius: 8px; text-align: center; }
        """,
    )
