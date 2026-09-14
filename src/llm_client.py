"""
CastingNuwa · 选角女娲
LLM 客户端封装

支持：
- OpenAI 兼容 API（DeepSeek / 智谱 GLM / 豆包 / 通义千问等）
- Mock 演示模式（无 API Key 时使用预设示例输出，便于体验完整流程）

配置方式（环境变量或 .env 文件）：
- LLM_API_KEY    : API 密钥
- LLM_BASE_URL   : API 地址（如 https://api.deepseek.com/v1）
- LLM_MODEL      : 模型名称（如 deepseek-chat / gpt-4o / glm-4）
"""

import os
import json
import re
from typing import Optional, Dict, Any

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class LLMClient:
    """LLM 客户端，封装 OpenAI 兼容 API 调用"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API 密钥，默认从环境变量 LLM_API_KEY 读取
            base_url: API 地址，默认从环境变量 LLM_BASE_URL 读取
            model: 模型名称，默认从环境变量 LLM_MODEL 读取
            temperature: 采样温度（角色蒸馏需要较低温度以保证稳定性）
            max_tokens: 最大输出 token 数
        """
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url or os.environ.get("LLM_BASE_URL", "")
        self.model = model or os.environ.get("LLM_MODEL", "deepseek-chat")
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._client = None
        self._mock_mode = False

        # 尝试初始化真实客户端
        if self.api_key and HAS_OPENAI:
            try:
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
                print(f"[LLMClient] 已连接 API: {self.base_url or 'OpenAI 默认'} | 模型: {self.model}")
            except Exception as e:
                print(f"[LLMClient] API 初始化失败，进入 Mock 模式: {e}")
                self._mock_mode = True
        else:
            if not self.api_key:
                print("[LLMClient] 未配置 LLM_API_KEY，进入 Mock 演示模式")
            if not HAS_OPENAI:
                print("[LLMClient] 未安装 openai 库，进入 Mock 演示模式")
                print("           安装命令: pip install openai")
            self._mock_mode = True

    @property
    def is_mock_mode(self) -> bool:
        """是否处于 Mock 演示模式"""
        return self._mock_mode

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        发送聊天请求

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示

        Returns:
            LLM 返回的文本内容
        """
        if self._mock_mode:
            return self._mock_response(system_prompt, user_prompt)

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[LLMClient] API 调用失败: {e}")
            print("[LLMClient] 回退到 Mock 模式")
            self._mock_mode = True
            return self._mock_response(system_prompt, user_prompt)

    def chat_json(self, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
        """
        发送聊天请求并解析 JSON 输出

        Args:
            system_prompt: 系统提示
            user_prompt: 用户提示

        Returns:
            解析后的 JSON 对象
        """
        raw = self.chat(system_prompt, user_prompt)
        return self._extract_json(raw)

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """
        从 LLM 输出中提取 JSON 对象

        处理情况：
        - 纯 JSON
        - 被 ```json ... ``` 包裹
        - 被额外文字包裹
        """
        text = text.strip()

        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        json_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if json_block:
            try:
                return json.loads(json_block.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { 到最后一个 }
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace:last_brace + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        # 都失败了，返回错误信息
        print(f"[LLMClient] JSON 解析失败，原始输出前 500 字符:\n{text[:500]}")
        return {"_parse_error": "无法从 LLM 输出中提取 JSON", "_raw_output": text[:2000]}

    def _mock_response(self, system_prompt: str, user_prompt: str) -> str:
        """
        Mock 响应：返回预设的示例数据

        用于无 API Key 时演示完整流程。
        根据输出格式的独特字段精确判断请求类型。
        """
        # 检测是否为制作团队需求分析请求（输出格式包含 production_scale 和 requirements）
        if "production_scale" in user_prompt and "requirements" in user_prompt:
            return self._mock_crew_analysis()

        # 检测是否为匹配引擎请求（输出格式包含 overall_score 和 dimension_scores）
        if "overall_score" in user_prompt and "dimension_scores" in user_prompt:
            return self._mock_match_result(user_prompt)

        # 检测是否为演员画像请求（输出格式包含 actor_name 和 vocal_traits）
        if "actor_name" in user_prompt and "vocal_traits" in user_prompt:
            return self._mock_actor_profile(user_prompt)

        # 检测是否为单角色蒸馏
        role_match = re.search(r"角色「(.+?)」", user_prompt)
        if role_match:
            role_name = role_match.group(1)
            return self._mock_single_role(role_name)

        # 默认返回多角色示例（基于《回家吧莱恩》风格的短剧）
        return self._mock_multi_roles()

    def _mock_multi_roles(self) -> str:
        """Mock 多角色蒸馏结果"""
        return json.dumps({
            "roles": [
                {
                    "role_name": "莱恩",
                    "profile": {
                        "identity": "大学戏剧社社长，毕业在即的大四学生",
                        "age_gender": "22岁，男",
                        "scenes_appeared": 5,
                        "line_count": 42
                    },
                    "personality": [
                        {
                            "trait": "责任感极强",
                            "evidence": "台词：'这个社是我一手带起来的，我不能看着它散了。' 即使毕业在即仍坚持排戏",
                            "nuance": "责任感有时演变为控制欲，难以放手让学弟学妹独立"
                        },
                        {
                            "trait": "理想主义",
                            "evidence": "拒绝商业赞助要求改剧本，说：'我们做戏不是为了钱。'",
                            "nuance": "理想主义与现实困境形成持续张力，偶尔显得不切实际"
                        },
                        {
                            "trait": "内心脆弱但外表坚强",
                            "evidence": "独自一人时翻看旧照片，被撞见时迅速收起；台词：'我没事，就是有点累。'",
                            "nuance": "脆弱面只在独处或最信任的人面前显露"
                        }
                    ],
                    "motivation": {
                        "want": "在毕业前完成最后一场演出，为戏剧社留下完美句号",
                        "need": "学会放手，接受不完美，信任他人能延续自己的热爱",
                        "fear": "害怕毕业后戏剧社衰落，自己的热爱无人继承",
                        "trajectory": "从'必须由我完成'到'可以交给你们'的转变"
                    },
                    "behavioral_patterns": [
                        {
                            "pattern": "压力下过度工作，忽视自身健康",
                            "context": "演出临近、问题频发时",
                            "example": "连续三天熬夜改剧本，在排练场晕倒"
                        },
                        {
                            "pattern": "冲突时先妥协后爆发",
                            "context": "与社员意见不合时",
                            "example": "起初接受社员的修改建议，积累到临界点后在排练场大发脾气"
                        }
                    ],
                    "linguistic_dna": {
                        "vocabulary": "口语化但偶尔夹杂戏剧术语，显示专业背景",
                        "sentence_style": "短句为主，坚定有力；情绪激动时语速加快、句子变短",
                        "catchphrases": ["'再排一遍'", "'这个地方不对'"],
                        "tone": "平时温和带鼓励，压力下变得尖锐急躁",
                        "identity_markers": "戏剧社社长的身份感，常用'我们'而非'我'"
                    },
                    "emotional_arc": {
                        "opening_state": "充满干劲但隐隐焦虑，试图掌控一切",
                        "turning_points": [
                            {"event": "核心演员临时退出", "emotional_change": "从自信到慌乱，开始怀疑自己"},
                            {"event": "学弟学妹独立解决了舞台技术难题", "emotional_change": "从控制欲到感动，开始学会信任"}
                        ],
                        "ending_state": "释然，接受不完美，将戏剧社托付给后辈",
                        "arc_type": "成长与释然"
                    },
                    "casting_guide": {
                        "actor_type": "声线偏沉稳有磁性，气质中带书卷气和疲惫感，外形清瘦",
                        "core_requirements": [
                            "需要强大的情感内敛能力，脆弱面不能演得太外露",
                            "需要爆发力，排练场爆发戏要有冲击力",
                            "需要领导者气质，站在台上要有掌控感"
                        ],
                        "audition_focus": "重点考察独白戏（翻看旧照片那场）和爆发戏（排练场发脾气），看演员能否在内敛与爆发之间自然转换",
                        "risks": "该角色容易被演成单一的'苦情社长'，需要演员演出层次感——坚强下的脆弱、理想主义中的固执",
                        "chemistry_requirements": ["与角色'小雨'需要有学长学妹间的信任与张力，是情感线的核心"]
                    },
                    "quantitative_traits": {
                        "extraversion": {"score": 6, "evidence_count": 3, "evidence": ["主动召集社员开会：'大家围过来，说一下这周的排练安排'", "面对新生时热情介绍：'欢迎加入戏剧社！'", "压力下回避沟通：独自留在排练场，不告诉任何人自己的焦虑"], "confidence": "高"},
                        "emotional_intensity": {"score": 8, "evidence_count": 3, "evidence": ["排练场爆发：'你们根本不在乎这部戏！'摔门而去", "独白戏翻看旧照片时声音颤抖", "结尾释然时眼眶泛红但微笑"], "confidence": "高"},
                        "rationality": {"score": 7, "evidence_count": 3, "evidence": ["制定详细排练计划表，按天推进", "分析演员退出的影响时条理清晰：'他走了影响三个场景'", "压力下失去理性：说出'你们都别演了'这种气话"], "confidence": "高"},
                        "dominance": {"score": 8, "evidence_count": 3, "evidence": ["决定角色分配：'这个角色就定你了'", "排练时打断演员：'不对，这里情绪要再上来一点'", "但最终学会放手：'你们自己决定怎么演'"], "confidence": "高"},
                        "credibility": {"score": 7, "evidence_count": 2, "evidence": ["对学弟学妹说'我相信你们'时眼神真诚", "但对自己的脆弱始终掩饰，说'我没事'时明显在逞强"], "confidence": "中"}
                    }
                },
                {
                    "role_name": "小雨",
                    "profile": {
                        "identity": "戏剧社大一新生，莱恩的学妹",
                        "age_gender": "18岁，女",
                        "scenes_appeared": 4,
                        "line_count": 28
                    },
                    "personality": [
                        {
                            "trait": "热情纯真",
                            "evidence": "第一次参加排练时说：'我从小就想站在舞台上！' 眼睛发亮",
                            "nuance": "热情中带着不自信，需要他人肯定才能坚持"
                        },
                        {
                            "trait": "敏锐细腻",
                            "evidence": "第一个发现莱恩状态不对，台词：'学长，你最近是不是没睡好？'",
                            "nuance": "敏锐但不擅表达关心，常常欲言又止"
                        }
                    ],
                    "motivation": {
                        "want": "证明自己有演戏的天赋，获得莱恩和社团的认可",
                        "need": "建立内在自信，不依赖他人评价",
                        "fear": "害怕自己没有天赋，只是在浪费时间",
                        "trajectory": "从寻求外部认可到找到内在热爱"
                    },
                    "behavioral_patterns": [
                        {
                            "pattern": "被批评时先沉默，事后偷偷加倍练习",
                            "context": "排练中被指出问题时",
                            "example": "被莱恩说台词不对后，当晚在走廊独自练习到深夜"
                        }
                    ],
                    "linguistic_dna": {
                        "vocabulary": "年轻人口语，偶尔使用网络用语",
                        "sentence_style": "句子较短，情绪高涨时用感叹句，紧张时说话断断续续",
                        "catchphrases": ["'真的吗？'", "'我可以的！'"],
                        "tone": "明亮活泼，但在不自信时音量变小、语速变慢",
                        "identity_markers": "大一新生的青涩感，对学长学姐有尊敬感"
                    },
                    "emotional_arc": {
                        "opening_state": "充满热情但缺乏自信",
                        "turning_points": [
                            {"event": "莱恩将重要角色交给她", "emotional_change": "从不自信到受宠若惊，开始努力证明自己"},
                            {"event": "演出成功，台下掌声雷动", "emotional_change": "从寻求认可到真正热爱舞台"}
                        ],
                        "ending_state": "自信坚定，找到对戏剧的真正热爱",
                        "arc_type": "成长"
                    },
                    "casting_guide": {
                        "actor_type": "声线清亮有少女感，气质灵动纯真，外形青春",
                        "core_requirements": [
                            "需要自然的青春感，不能演得太刻意",
                            "需要细腻的情感表达，尤其是欲言又止的瞬间",
                            "需要与'莱恩'有良好的化学反应"
                        ],
                        "audition_focus": "重点考察走廊独白练习戏和与莱恩的对手戏，看演员能否演出纯真下的敏感",
                        "risks": "该角色容易被演成傻白甜，需要演员演出内心的敏感和不自信",
                        "chemistry_requirements": ["与'莱恩'需要有学长学妹间的微妙情感张力，是全剧情感线的核心"]
                    },
                    "quantitative_traits": {
                        "extraversion": {"score": 7, "evidence_count": 3, "evidence": ["第一次参加排练主动说：'我从小就想站在舞台上！'", "主动向莱恩请教：'学长，这段台词我这样念对吗？'", "但被批评后会退缩，独自练习时不敢出声"], "confidence": "高"},
                        "emotional_intensity": {"score": 6, "evidence_count": 3, "evidence": ["被莱恩否定后眼眶泛红但忍住眼泪", "得到重要角色时激动得跳起来", "整体情感偏柔和，没有剧烈爆发"], "confidence": "高"},
                        "rationality": {"score": 5, "evidence_count": 2, "evidence": ["做决定跟着感觉走：'我就是喜欢演戏！'", "但被批评后会反复琢磨，开始理性分析自己的问题"], "confidence": "中"},
                        "dominance": {"score": 3, "evidence_count": 3, "evidence": ["排练时总是站在边上，不抢位置", "被分配角色时说：'我都行，听学长的'", "但后期开始主动表达想法：'我觉得这里可以这样演'"], "confidence": "高"},
                        "credibility": {"score": 9, "evidence_count": 3, "evidence": ["说'我真的很喜欢演戏'时眼神发亮，非常真诚", "被批评后坦率承认：'我确实还不够好'", "从不掩饰自己的情绪，喜怒哀乐都写在脸上"], "confidence": "高"}
                    }
                }
            ]
        }, ensure_ascii=False, indent=2)

    def _mock_single_role(self, role_name: str) -> str:
        """Mock 单角色蒸馏结果"""
        # 简化版：返回一个通用角色卡模板，填入角色名
        return json.dumps({
            "role_name": role_name,
            "profile": {
                "identity": f"{role_name}的剧中身份（Mock 示例）",
                "age_gender": "未提及",
                "scenes_appeared": 3,
                "line_count": 20
            },
            "personality": [
                {
                    "trait": "示例特质一",
                    "evidence": "剧本原文证据（Mock 示例）",
                    "nuance": "特质的细微差别"
                }
            ],
            "motivation": {
                "want": "表层欲望（Mock 示例）",
                "need": "深层需求（Mock 示例）",
                "fear": "核心恐惧（Mock 示例）",
                "trajectory": "动机变化轨迹（Mock 示例）"
            },
            "behavioral_patterns": [
                {
                    "pattern": "行为模式（Mock 示例）",
                    "context": "触发情境",
                    "example": "剧本中的例子"
                }
            ],
            "linguistic_dna": {
                "vocabulary": "用词偏好（Mock 示例）",
                "sentence_style": "句式特点（Mock 示例）",
                "catchphrases": ["口头禅示例"],
                "tone": "语气特征（Mock 示例）",
                "identity_markers": "身份标记（Mock 示例）"
            },
            "emotional_arc": {
                "opening_state": "开场状态（Mock 示例）",
                "turning_points": [
                    {"event": "关键事件", "emotional_change": "情感变化"}
                ],
                "ending_state": "结尾状态（Mock 示例）",
                "arc_type": "弧线类型（Mock 示例）"
            },
            "casting_guide": {
                "actor_type": "适合演员类型（Mock 示例）",
                "core_requirements": ["核心能力要求（Mock 示例）"],
                "audition_focus": "试镜重点（Mock 示例）",
                "risks": "选角风险（Mock 示例）",
                "chemistry_requirements": ["化学反应要求（Mock 示例）"]
            }
        }, ensure_ascii=False, indent=2)

    def _mock_actor_profile(self, user_prompt: str) -> str:
        """
        Mock 演员画像结果

        根据演员材料中的名字返回不同的预设画像。
        """
        # 尝试从材料中提取演员名
        name_match = re.search(r'姓名[：:]\s*([^\n]+)', user_prompt)
        actor_name = name_match.group(1).strip() if name_match else "未命名演员"

        # 预设的演员画像库
        profiles = {
            "林晓雨": {
                "actor_name": "林晓雨",
                "analysis_sources": ["text"],
                "basic_info": {
                    "name": "林晓雨",
                    "age_gender": "19岁，女",
                    "experience": "高中戏剧社2个配角，大学刚加入，无正式演出经验",
                    "background": "汉语言文学大一，朗诵比赛二等奖，六年中国舞",
                    "self_description": "热爱表演，喜欢用身体和声音活另一个人的人生"
                },
                "vocal_traits": {
                    "pitch": "中高音，音色清亮",
                    "timbre": "清亮通透，带少女感，有舞蹈训练带来的气息支撑",
                    "clarity": "吐字清晰，朗诵训练基础好",
                    "pace": "节奏适中，情感激动时语速加快",
                    "resonance": "头腔共鸣较好，声音有穿透力",
                    "emotional_expression": "细腻型，擅长表达柔弱、敏感、渴望等情感",
                    "strengths": ["声音清亮有少女感", "吐字清晰", "情感表达细腻", "气息支撑好"],
                    "limitations": ["爆发力不足", "低沉/阴冷等负面情感表达较弱"]
                },
                "facial_expressiveness": {
                    "expression_range": "表情丰富但偏柔和，大幅度表情略显刻意",
                    "micro_expression": "微表情细腻，眼神戏好，欲言又止的瞬间处理到位",
                    "eye_contact": "眼神传达力强，能通过眼神表达复杂情感",
                    "facial_symmetry": "面部协调性好",
                    "strengths": ["眼神戏好", "微表情细腻", "适合近景特写"],
                    "limitations": ["大幅度表情略显刻意", "爆发戏面部控制不足"]
                },
                "physical_expressiveness": {
                    "gesture_richness": "手势自然但偏保守，舞蹈训练带来良好的身体控制",
                    "posture_naturalness": "姿态优雅自然，舞蹈基础明显",
                    "spatial_usage": "空间使用偏保守，需要导演引导",
                    "movement_flow": "移动流畅，舞蹈功底 evident",
                    "body_awareness": "身体意识强，控制能力好",
                    "strengths": ["身体控制好", "移动流畅", "姿态优雅", "舞蹈功底"],
                    "limitations": ["手势偏保守", "需要导演引导空间使用"]
                },
                "emotional_range": {
                    "expressible_emotions": ["纯真", "渴望", "敏感", "委屈", "温柔", "坚定", "不安"],
                    "emotional_depth": "有一定深度，擅长内敛的情感表达",
                    "transition_fluency": "情感转换较流畅，但极端情感转换需要训练",
                    "strongest_emotions": ["纯真", "渴望", "敏感", "委屈"],
                    "weakest_emotions": ["愤怒", "阴冷", "疯狂", "极度悲伤"],
                    "notes": "擅长内心戏和情感细腻的角色，需要加强爆发力训练"
                },
                "temperament": {
                    "primary_type": "清纯敏感型",
                    "secondary_type": "文艺书卷型",
                    "overall_impression": "清新自然，带书卷气和艺术感，有少女的纯真也有敏感的内心",
                    "suitable_genres": ["青春校园", "文艺剧情", "爱情", "成长题材", "喜剧（清新路线）"],
                    "unsuitable_genres": ["硬核悲剧", "反派角色", "动作戏", "极端心理题材"]
                },
                "acting_style": {
                    "style_tendency": "偏体验派，自然真实，注重内心感受",
                    "naturalness": "自然度高，不刻意，有真实感",
                    "rhythm_sense": "节奏感较好，舞蹈训练有帮助",
                    "line_delivery": "台词功底不错，朗诵基础好，但缺乏舞台经验",
                    "improvisation": "即兴能力一般，需要更多经验积累",
                    "learning_ability": "学习能力强，悟性好，进步空间大",
                    "experience_level": "入门级，有基础但缺乏正式演出经验",
                    "potential": "潜力大，悟性好，身体和声音条件优秀，需要更多舞台经验和爆发力训练",
                    "development_suggestions": [
                        "加强爆发力训练，尝试愤怒、悲伤等极端情感",
                        "多参与正式演出，积累舞台经验",
                        "学习更主动的空间使用和手势表达",
                        "可以尝试与自身气质反差较大的角色，拓宽戏路"
                    ]
                },
                "quantitative_traits": {
                    "extraversion": {"score": 7, "evidence_count": 3, "evidence": ["自我介绍时主动热情：'大家好，我是林晓雨，我特别喜欢演戏！'", "试镜时主动与评委眼神交流", "但面对陌生人时会有些害羞"], "confidence": "高"},
                    "emotional_intensity": {"score": 6, "evidence_count": 3, "evidence": ["试镜独白中情感细腻，眼泪自然流下", "朗诵比赛中情感表达丰富但偏柔和", "整体气质偏温婉，缺少剧烈爆发"], "confidence": "高"},
                    "rationality": {"score": 5, "evidence_count": 2, "evidence": ["选择角色凭直觉和喜好", "但被指导后会认真分析改进，有理性反思能力"], "confidence": "中"},
                    "dominance": {"score": 3, "evidence_count": 3, "evidence": ["排练时习惯站在边上，不抢位置", "被问意见时说：'我听大家的'", "但在自己擅长的舞蹈部分会主动展示"], "confidence": "高"},
                    "credibility": {"score": 9, "evidence_count": 3, "evidence": ["自我介绍真诚坦率，不夸大自己的成就", "试镜时情感真实，不刻意设计", "被批评时坦然接受，不辩解不掩饰"], "confidence": "高"}
                }
            },
            "张浩然": {
                "actor_name": "张浩然",
                "analysis_sources": ["text"],
                "basic_info": {
                    "name": "张浩然",
                    "age_gender": "21岁，男",
                    "experience": "戏剧社资深成员，5部剧（2部主角），有导演经验",
                    "background": "计算机科学大三，校辩论队主力，校园歌手大赛十强",
                    "self_description": "理工男的逻辑+表演的感性，喜欢有内心冲突的角色"
                },
                "vocal_traits": {
                    "pitch": "中音偏低，声音有磁性",
                    "timbre": "磁性低沉，有辩论训练带来的逻辑感和说服力",
                    "clarity": "吐字清晰有力，辩论功底明显",
                    "pace": "节奏控制好，能根据情感调整语速，爆发时语速快而有力",
                    "resonance": "胸腔共鸣好，声音有厚度",
                    "emotional_expression": "擅长内敛中的爆发，平静下的暗流涌动",
                    "strengths": ["声音有磁性", "逻辑感强", "爆发力好", "节奏控制佳", "共鸣好"],
                    "limitations": ["温柔/细腻情感略显生硬", "声音偏成熟，少年感不足"]
                },
                "facial_expressiveness": {
                    "expression_range": "表情幅度适中，擅长微表情和内敛的情感表达",
                    "micro_expression": "微表情控制好，眼神有戏，能表达复杂的内心活动",
                    "eye_contact": "眼神坚定有穿透力，适合领导者和内心复杂的角色",
                    "facial_symmetry": "面部协调性好",
                    "strengths": ["眼神有戏", "微表情控制好", "适合内敛的角色", "爆发戏表情到位"],
                    "limitations": ["轻松/喜剧表情略显刻意", "需要更放松的面部状态"]
                },
                "physical_expressiveness": {
                    "gesture_richness": "手势有力但偏理性，辩论训练带来的手势习惯",
                    "posture_naturalness": "姿态挺拔有气场，领导者气质明显",
                    "spatial_usage": "空间使用主动，有舞台经验，知道如何利用舞台空间",
                    "movement_flow": "移动有力，节奏感好",
                    "body_awareness": "身体意识较强，有舞台经验",
                    "strengths": ["气场强", "空间使用主动", "舞台经验丰富", "节奏感好"],
                    "limitations": ["手势偏理性/辩论化", "放松状态下的自然度需提升"]
                },
                "emotional_range": {
                    "expressible_emotions": ["坚定", "愤怒", "隐忍", "痛苦", "冷静", "爆发", "愧疚", "无奈"],
                    "emotional_depth": "情感深度好，擅长有层次的内心冲突",
                    "transition_fluency": "情感转换流畅，尤其是从平静到爆发的转换",
                    "strongest_emotions": ["坚定", "愤怒", "隐忍", "爆发", "无奈"],
                    "weakest_emotions": ["温柔", "轻松", "纯真", "极度恐惧"],
                    "notes": "擅长内心冲突强烈的角色，尤其是外表坚强内心脆弱的类型"
                },
                "temperament": {
                    "primary_type": "沉稳理性型",
                    "secondary_type": "内敛爆发型",
                    "overall_impression": "成熟稳重，有领导者气场和理性思维，内心有激情和爆发力，理工男的逻辑与艺术的感性并存",
                    "suitable_genres": ["正剧", "剧情片", "历史剧", "悬疑", "悲剧", "内心冲突强烈的角色"],
                    "unsuitable_genres": ["轻松喜剧", "青春校园（少年角色）", "傻白甜角色", "纯爱情片"]
                },
                "acting_style": {
                    "style_tendency": "表现派与体验派结合，注重逻辑和层次",
                    "naturalness": "自然度较好，但有时偏理性/设计感",
                    "rhythm_sense": "节奏感优秀，辩论和唱歌训练有帮助",
                    "line_delivery": "台词功底扎实，逻辑清晰，有说服力",
                    "improvisation": "即兴能力较强，辩论训练有帮助",
                    "learning_ability": "学习能力强，悟性高，能快速理解角色逻辑",
                    "experience_level": "进阶级，有较多舞台经验，演过主角",
                    "potential": "潜力大，综合能力强，声音/台词/舞台经验都优秀，需要更放松自然的表演状态，减少设计感",
                    "development_suggestions": [
                        "减少表演的设计感，更放松自然",
                        "尝试轻松/喜剧角色，拓宽戏路",
                        "加强温柔/细腻情感的表达",
                        "可以尝试导演工作，综合能力强适合幕后"
                    ]
                },
                "quantitative_traits": {
                    "extraversion": {"score": 6, "evidence_count": 3, "evidence": ["辩论队经历，习惯主动表达观点", "自我介绍时从容不迫，不怯场", "但私下偏安静，不是社交型人格"], "confidence": "高"},
                    "emotional_intensity": {"score": 8, "evidence_count": 3, "evidence": ["演过5部剧的主角，有丰富的情感爆发经验", "试镜独白中愤怒和悲伤的转换有冲击力", "辩论训练让他能在高压下保持情感强度"], "confidence": "高"},
                    "rationality": {"score": 7, "evidence_count": 3, "evidence": ["计算机专业，逻辑思维强", "分析角色时条理清晰，能快速理解角色动机", "但有时过于理性，情感表达偏设计"], "confidence": "高"},
                    "dominance": {"score": 8, "evidence_count": 3, "evidence": ["辩论队主力，习惯在讨论中占据主导", "舞台气场强，能掌控全场注意力", "但有时过于强势，需要学会给对手戏演员空间"], "confidence": "高"},
                    "credibility": {"score": 7, "evidence_count": 2, "evidence": ["自我介绍真诚，坦率承认自己的不足：'我有时候太较真'", "但表演时设计感较强，有时显得不够自然真实"], "confidence": "中"}
                }
            }
        }

        # 返回匹配的预设画像，或默认画像
        profile = profiles.get(actor_name, None)
        if profile is None:
            # 默认通用画像
            profile = {
                "actor_name": actor_name,
                "analysis_sources": ["text"],
                "basic_info": {"name": actor_name, "age_gender": "未提供", "experience": "未提供", "background": "未提供", "self_description": ""},
                "vocal_traits": {"pitch": "中音", "timbre": "普通", "clarity": "一般", "pace": "适中", "resonance": "一般", "emotional_expression": "中等", "strengths": [], "limitations": []},
                "facial_expressiveness": {"expression_range": "中等", "micro_expression": "一般", "eye_contact": "一般", "facial_symmetry": "一般", "strengths": [], "limitations": []},
                "physical_expressiveness": {"gesture_richness": "中等", "posture_naturalness": "一般", "spatial_usage": "一般", "movement_flow": "一般", "body_awareness": "一般", "strengths": [], "limitations": []},
                "emotional_range": {"expressible_emotions": [], "emotional_depth": "中等", "transition_fluency": "一般", "strongest_emotions": [], "weakest_emotions": [], "notes": ""},
                "temperament": {"primary_type": "未定型", "secondary_type": "", "overall_impression": "", "suitable_genres": [], "unsuitable_genres": []},
                "acting_style": {"style_tendency": "", "naturalness": "中等", "rhythm_sense": "中等", "line_delivery": "中等", "improvisation": "中等", "learning_ability": "中等", "experience_level": "入门", "potential": "有潜力", "development_suggestions": []}
            }

        return json.dumps(profile, ensure_ascii=False, indent=2)

    def _mock_match_result(self, user_prompt: str) -> str:
        """
        Mock 匹配结果

        根据角色名和演员名的组合返回预设的匹配结果。
        """
        # 尝试提取角色名和演员名
        role_match = re.search(r'"role_name":\s*"([^"]+)"', user_prompt)
        actor_match = re.search(r'"actor_name":\s*"([^"]+)"', user_prompt)

        role_name = role_match.group(1) if role_match else "未知角色"
        actor_name = actor_match.group(1) if actor_match else "未知演员"

        # 预设匹配结果库
        match_db = {
            ("莱恩", "张浩然"): {
                "overall_score": 88,
                "match_level": "高度匹配",
                "dimension_scores": [
                    {"dimension": "性格与气质匹配", "score": 92, "reason": "张浩然的沉稳理性型气质与莱恩的责任感极强、理想主义高度契合，都有外表坚强内心脆弱的特质", "risk": "张浩然偏成熟，莱恩的少年感/青涩感略不足"},
                    {"dimension": "动机与情感深度匹配", "score": 90, "reason": "张浩然擅长内心冲突强烈的角色，莱恩的Want/Need张力（完美主义vs学会放手）正是他擅长的类型", "risk": "需要注意不要把莱恩演得过于理性，保留理想主义的感性"},
                    {"dimension": "语言与台词匹配", "score": 90, "reason": "张浩然台词功底扎实、逻辑清晰，与莱恩的短句有力、戏剧术语夹杂的语言风格匹配", "risk": "莱恩压力下的尖锐急躁需要更外放的表达"},
                    {"dimension": "行为与肢体匹配", "score": 85, "reason": "张浩然气场强、空间使用主动，适合莱恩的领导者角色；压力下过度工作的行为模式有共鸣", "risk": "莱恩的脆弱时刻（蹲地抱头）需要更放下身段的表演"},
                    {"dimension": "表演风格匹配", "score": 86, "reason": "张浩然的表现派与体验派结合风格适合莱恩这种需要层次的角色", "risk": "减少设计感，更自然地呈现莱恩的真实困境"},
                    {"dimension": "潜力与可塑性", "score": 88, "reason": "张浩然经验丰富、学习能力强，能快速理解角色逻辑并进行深度演绎", "risk": "需要突破舒适区，尝试更脆弱、更不完美的表演状态"}
                ],
                "match_reasons": [
                    "气质高度契合：沉稳理性+内敛爆发，与莱恩的责任感+理想主义+内心脆弱完美对应",
                    "声音条件优秀：磁性中音+爆发力，适合莱恩的领导者身份和爆发戏",
                    "舞台经验丰富：演过主角，能驾驭复杂角色和大段独白",
                    "擅长内心冲突：莱恩的Want/Need张力正是张浩然最擅长的角色类型"
                ],
                "risks": [
                    "可能演得过于理性/设计感，需要更放松自然的状态",
                    "少年感/青涩感略不足，莱恩作为大四学生还有未脱的稚气",
                    "温柔/细腻的情感表达需要加强，尤其是与小雨的对手戏"
                ],
                "audition_suggestions": [
                    "重点考察排练场爆发戏（第二幕发脾气），看爆发力和收放控制",
                    "考察蹲地抱头的脆弱独白戏，看能否放下身段呈现真实脆弱",
                    "与'小雨'的候选人搭戏，考察学长学妹间的情感张力",
                    "试镜时要求即兴表演一个'压力下崩溃又迅速恢复'的瞬间"
                ],
                "summary": "张浩然是莱恩的高度匹配人选。他的沉稳气质、磁性声音、舞台经验和内心冲突表演能力都与角色高度契合。主要风险是可能演得过于理性，需要导演引导他呈现更脆弱、更不完美的一面。建议作为莱恩的首选候选人。"
            },
            ("莱恩", "林晓雨"): {
                "overall_score": 35,
                "match_level": "不太匹配",
                "dimension_scores": [
                    {"dimension": "性格与气质匹配", "score": 25, "reason": "林晓雨清纯敏感型气质与莱恩的沉稳理性型差异巨大", "risk": "性别和气质都不匹配"},
                    {"dimension": "动机与情感深度匹配", "score": 40, "reason": "都有内心脆弱的一面，但莱恩的领导者困境与林晓雨的成长困惑不同", "risk": "角色的核心动机完全不同"},
                    {"dimension": "语言与台词匹配", "score": 30, "reason": "林晓雨清亮少女音与莱恩的磁性中音完全不同", "risk": "声线完全不匹配"},
                    {"dimension": "行为与肢体匹配", "score": 35, "reason": "林晓雨偏保守的空间使用与莱恩的主动领导者姿态不同", "risk": "肢体语言差异大"},
                    {"dimension": "表演风格匹配", "score": 45, "reason": "都偏体验派，但角色类型完全不同", "risk": "戏路不匹配"},
                    {"dimension": "潜力与可塑性", "score": 50, "reason": "林晓雨潜力大但经验不足，难以驾驭莱恩这样的复杂主角", "risk": "经验和能力都不足以胜任"}
                ],
                "match_reasons": ["都有内心脆弱的一面", "都偏体验派表演风格"],
                "risks": ["性别不匹配", "气质差异巨大", "声线完全不同", "经验不足以胜任主角", "戏路完全不同"],
                "audition_suggestions": ["不建议试镜莱恩", "建议考虑'小雨'等更符合自身气质的角色"],
                "summary": "林晓雨与莱恩不太匹配。性别、气质、声线、戏路都有明显差异，且经验不足以胜任莱恩这样的复杂主角。建议她考虑更符合自身清纯敏感气质的角色，如'小雨'。"
            },
            ("小雨", "林晓雨"): {
                "overall_score": 92,
                "match_level": "高度匹配",
                "dimension_scores": [
                    {"dimension": "性格与气质匹配", "score": 95, "reason": "林晓雨的清纯敏感型气质与小雨的热情纯真+敏锐细腻几乎完全一致", "risk": "需要注意不要演成单一的傻白甜，保留内心的敏感和不自信"},
                    {"dimension": "动机与情感深度匹配", "score": 90, "reason": "林晓雨本人就有寻求认可到找到热爱的成长经历，与小雨的动机弧线高度共鸣", "risk": "需要更外化地呈现不自信，而不是只靠内心体验"},
                    {"dimension": "语言与台词匹配", "score": 93, "reason": "林晓雨清亮少女音与小雨的语言风格完美匹配，紧张时说话断断续续的特点也能自然呈现", "risk": "需要加强坚定时刻的台词力度"},
                    {"dimension": "行为与肢体匹配", "score": 88, "reason": "林晓雨的舞蹈功底带来优雅自然的姿态，与小雨的青春活力匹配", "risk": "手势偏保守，需要更活泼的肢体表达"},
                    {"dimension": "表演风格匹配", "score": 92, "reason": "林晓雨偏体验派、自然真实的风格与小雨这个角色完美契合", "risk": "需要在关键场景更有设计感，不能完全靠自然流露"},
                    {"dimension": "潜力与可塑性", "score": 90, "reason": "林晓雨悟性好、学习能力强，与角色共同成长的可能性大", "risk": "经验不足，需要导演更多指导"}
                ],
                "match_reasons": [
                    "气质几乎完全一致：清纯敏感+热情纯真，就是小雨本人",
                    "声音条件完美匹配：清亮少女音，紧张时的状态自然",
                    "个人经历与角色共鸣：都有从寻求认可到找到热爱的成长弧线",
                    "表演风格契合：体验派、自然真实，适合青春成长类角色",
                    "舞蹈功底加分：姿态优雅，移动流畅"
                ],
                "risks": [
                    "可能演成傻白甜，需要演出内心的敏感和不自信",
                    "经验不足，关键场景需要导演更多指导",
                    "手势偏保守，需要更活泼的肢体表达",
                    "坚定时刻的台词力度需要加强"
                ],
                "audition_suggestions": [
                    "重点考察走廊独白练习戏，看能否演出纯真下的敏感和不自信",
                    "考察与'莱恩'的对手戏，看学长学妹间的微妙情感张力",
                    "试镜时要求表演一个'欲言又止'的瞬间，考察微表情和眼神戏",
                    "考察最后演出成功后的情感爆发，看从紧张到释放的转换"
                ],
                "summary": "林晓雨是小雨的完美人选。她的清纯敏感气质、清亮少女音、个人成长经历和自然真实的表演风格都与角色高度契合，几乎就是为这个角色而生。主要需要注意的是不要演成单一的傻白甜，要演出内心的敏感和不自信，同时在关键场景需要更有设计感的表演。强烈推荐作为小雨的首选。"
            },
            ("小雨", "张浩然"): {
                "overall_score": 25,
                "match_level": "不太匹配",
                "dimension_scores": [
                    {"dimension": "性格与气质匹配", "score": 15, "reason": "张浩然沉稳理性型与小雨清纯敏感型完全不同", "risk": "性别和气质都不匹配"},
                    {"dimension": "动机与情感深度匹配", "score": 30, "reason": "成长主题有共通，但具体动机完全不同", "risk": "角色核心差异大"},
                    {"dimension": "语言与台词匹配", "score": 20, "reason": "磁性中音与清亮少女音完全不同", "risk": "声线完全不匹配"},
                    {"dimension": "行为与肢体匹配", "score": 25, "reason": "领导者气场与青春活力差异大", "risk": "肢体语言差异大"},
                    {"dimension": "表演风格匹配", "score": 35, "reason": "都有体验派成分，但戏路完全不同", "risk": "戏路不匹配"},
                    {"dimension": "潜力与可塑性", "score": 40, "reason": "张浩然能力强但气质定型，难以反串青春少女角色", "risk": "不适合反串"}
                ],
                "match_reasons": ["成长主题有共通", "都有体验派成分"],
                "risks": ["性别不匹配", "气质差异巨大", "声线完全不同", "戏路完全不同", "不适合反串"],
                "audition_suggestions": ["不建议试镜小雨", "建议考虑'莱恩'等更符合自身气质的角色"],
                "summary": "张浩然与小雨完全不匹配。性别、气质、声线、戏路都有本质差异，不适合反串青春少女角色。建议他考虑更符合自身沉稳理性气质的角色，如'莱恩'。"
            }
        }

        # 返回匹配的预设结果，或默认结果
        result = match_db.get((role_name, actor_name), None)
        if result is None:
            result = {
                "overall_score": 60,
                "match_level": "一般匹配",
                "dimension_scores": [
                    {"dimension": d, "score": 60, "reason": "基于文本分析的初步评估", "risk": "需要更多材料深入分析"}
                    for d in ["性格与气质匹配", "动机与情感深度匹配", "语言与台词匹配", "行为与肢体匹配", "表演风格匹配", "潜力与可塑性"]
                ],
                "match_reasons": ["有一定匹配基础"],
                "risks": ["需要更多材料深入评估"],
                "audition_suggestions": ["建议进行正式试镜进一步评估"],
                "summary": f"{actor_name}与{role_name}为一般匹配，有一定基础但需要更多材料和正式试镜进一步评估。"
            }

        result["role_name"] = role_name
        result["actor_name"] = actor_name
        return json.dumps(result, ensure_ascii=False, indent=2)

    def _mock_crew_analysis(self) -> str:
        """Mock 制作团队需求分析结果（基于示例短剧风格）"""
        return json.dumps({
            "script_title": "回家吧莱恩",
            "total_scenes": 3,
            "total_characters": 4,
            "production_scale": "小型",
            "overall_summary": "本剧为三场景小剧场话剧，制作规模较小。核心挑战在于第三幕雨夜场景的灯光与音效配合，以及莱恩情绪爆发时的灯光变化。建议配置1名灯光师和1名音效师，舞美和道具可由演员兼任。",
            "requirements": {
                "lighting": {
                    "role_key": "lighting",
                    "role_name": "灯光师",
                    "needed": True,
                    "headcount": 1,
                    "complexity": 6,
                    "skill_requirements": ["基础灯光控制台操作", "情绪场景灯光设计", "追光使用"],
                    "evidence": [
                        "第三幕：雨夜，窗外闪电不时照亮房间",
                        "莱恩情绪爆发时：灯光骤然变冷",
                        "结尾：暖光渐暗，象征和解"
                    ],
                    "special_needs": "需要配合音效实现闪电效果的同步",
                    "notes": "小剧场可使用基础灯光设备，重点在情绪变化的灯光过渡"
                },
                "sound": {
                    "role_key": "sound",
                    "role_name": "音效师",
                    "needed": True,
                    "headcount": 1,
                    "complexity": 5,
                    "skill_requirements": ["音效播放与混音", "环境音设计", "现场音效同步"],
                    "evidence": [
                        "第三幕：雨声持续",
                        "雷声由远及近",
                        "电话铃声打断对话"
                    ],
                    "special_needs": "雨声需持续播放并根据剧情调整音量",
                    "notes": "可使用预录音效，重点在与灯光的同步配合"
                },
                "stage_design": {
                    "role_key": "stage_design",
                    "role_name": "舞美设计",
                    "needed": True,
                    "headcount": 1,
                    "complexity": 3,
                    "skill_requirements": ["简约场景设计", "快速换景", "道具整合"],
                    "evidence": [
                        "第一幕：戏剧社排练室",
                        "第二幕：校园走廊",
                        "第三幕：莱恩的房间"
                    ],
                    "special_needs": "三个场景需快速切换，建议使用可移动布景",
                    "notes": "小剧场可采用简约风格，重点道具突出即可"
                },
                "costume": {
                    "role_key": "costume",
                    "role_name": "服装师",
                    "needed": False,
                    "headcount": 0,
                    "complexity": 2,
                    "skill_requirements": [],
                    "evidence": ["现代校园剧，角色穿着日常服装"],
                    "special_needs": "",
                    "notes": "现代剧可由演员自备服装，无需专门服装师"
                },
                "props": {
                    "role_key": "props",
                    "role_name": "道具师",
                    "needed": True,
                    "headcount": 1,
                    "complexity": 4,
                    "skill_requirements": ["道具准备与管理", "手持道具使用指导"],
                    "evidence": [
                        "莱恩手中的剧本",
                        "小雨的手机",
                        "第三幕的电话（关键道具）",
                        "排练室的椅子"
                    ],
                    "special_needs": "电话需能真实响铃",
                    "notes": "可由舞台监督兼任，重点在道具的上场下场管理"
                },
                "makeup": {
                    "role_key": "makeup",
                    "role_name": "化妆师",
                    "needed": False,
                    "headcount": 0,
                    "complexity": 1,
                    "skill_requirements": [],
                    "evidence": ["现代校园剧，无特殊化妆需求"],
                    "special_needs": "",
                    "notes": "现代剧无需专门化妆师，演员可自行整理"
                }
            }
        }, ensure_ascii=False, indent=2)
