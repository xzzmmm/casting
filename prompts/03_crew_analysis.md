# 03 · 制作团队需求分析提示词（Crew Analysis）

> 从剧本中的舞台指示、场景描述、灯光/音效/服装/道具提示，分析所需的后台岗位与人员配置。
> 支持 LLM 深度分析模式和启发式规则分析模式（无 API Key 时自动降级）。

---

## System Prompt（系统提示）

```
你是一位资深戏剧制作总监，拥有20年以上的舞台剧制作经验。
你的任务是根据剧本文本，分析制作团队（后台人员）的需求配置。

你需要从剧本中提取以下信息：
1. 场景描述与舞台指示（方括号内的内容、场景标题）
2. 灯光提示（灯光变化、追光、聚光、色彩、明暗等）
3. 音效提示（音乐、雷声、敲门声、环境音等）
4. 服装描述（角色穿着、换装、特殊服装）
5. 道具需求（手持道具、场景道具、特殊道具）
6. 化妆需求（特殊妆面、年龄妆、伤痕妆等）

分析原则：
- 只基于剧本中明确出现的信息进行分析，不虚构
- 每个岗位需求必须引用剧本中的具体依据
- 复杂度评分 0-10，基于该岗位的工作量和技术难度
- 建议人数基于制作规模和复杂度综合判断
- 如果剧本中没有某岗位的明确需求，标记为不需要

输出严格的 JSON 格式，不要任何解释文字。
```

---

## User Prompt（用户提示）

```
请分析以下剧本的制作团队需求。

剧本：
{script}

请输出以下 JSON 结构：
{
  "script_title": "剧本标题（如可从内容推断，否则留空）",
  "total_scenes": 场景总数（整数）,
  "total_characters": 角色总数（整数）,
  "production_scale": "制作规模评估（小型/中型/大型）",
  "overall_summary": "总体制作建议（2-3句话）",
  "requirements": {
    "lighting": {
      "role_key": "lighting",
      "role_name": "灯光师",
      "needed": true/false,
      "headcount": 建议人数（整数）,
      "complexity": 复杂度0-10（整数）,
      "skill_requirements": ["技能要求1", "技能要求2"],
      "evidence": ["剧本依据1（引用原文）", "剧本依据2"],
      "special_needs": "特殊需求说明（如无则留空）",
      "notes": "备注（如无则留空）"
    },
    "sound": {
      "role_key": "sound",
      "role_name": "音效师",
      "needed": true/false,
      "headcount": 整数,
      "complexity": 整数,
      "skill_requirements": [],
      "evidence": [],
      "special_needs": "",
      "notes": ""
    },
    "stage_design": {
      "role_key": "stage_design",
      "role_name": "舞美设计",
      "needed": true/false,
      "headcount": 整数,
      "complexity": 整数,
      "skill_requirements": [],
      "evidence": [],
      "special_needs": "",
      "notes": ""
    },
    "costume": {
      "role_key": "costume",
      "role_name": "服装师",
      "needed": true/false,
      "headcount": 整数,
      "complexity": 整数,
      "skill_requirements": [],
      "evidence": [],
      "special_needs": "",
      "notes": ""
    },
    "props": {
      "role_key": "props",
      "role_name": "道具师",
      "needed": true/false,
      "headcount": 整数,
      "complexity": 整数,
      "skill_requirements": [],
      "evidence": [],
      "special_needs": "",
      "notes": ""
    },
    "makeup": {
      "role_key": "makeup",
      "role_name": "化妆师",
      "needed": true/false,
      "headcount": 整数,
      "complexity": 整数,
      "skill_requirements": [],
      "evidence": [],
      "special_needs": "",
      "notes": ""
    }
  }
}

只输出纯 JSON，不要任何解释文字，不要 markdown 代码块标记。
```

---

## 启发式规则分析（无 API Key 时自动使用）

当未配置 `LLM_API_KEY` 时，`CrewAnalyzer` 自动降级为启发式规则分析，不调用 LLM：

### 分析流程
1. **提取舞台指示**：正则匹配方括号 `【...】` 内的内容
2. **关键词匹配**：6个岗位各有关键词库，统计匹配次数
3. **明确标记识别**：直接识别 `【灯光：xxx】`、`【音效：xxx】` 等格式
4. **误判过滤**：排除"自然光"、"沉默"等非需求词
5. **规模估算**：基于场景数、角色数、各岗位匹配总分判断制作规模

### 测试结果
- 测试套件：`test_crew_analyzer.py`（5个测试用例）
- 综合得分：**93%**，评级**优秀（A）**
- 测试用例：经典悲剧100%、荒诞剧94%、雷雨风格85%、纯对话100%、古装宫廷85%

---

## 代码对应

- 文件：`src/crew_prompts.py`
- 变量：`CREW_SYSTEM_PROMPT`、`CREW_USER_PROMPT_TEMPLATE`
- 调用：`src/crew_analyzer.py` → `CrewAnalyzer.analyze()`
- 启发式模式：`CrewAnalyzer._heuristic_analyze()`
- 测试：`test_crew_analyzer.py`
