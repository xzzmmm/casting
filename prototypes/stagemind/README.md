# StageMind 排练记录助手

StageMind 是排练记录助手原型，支持上传排练录音或视频、查看排练日志、台位和可检索时间轴。语音转写和姿态估计可通过可选依赖运行，自动日志结构化的模型调用接口仍待接入。

- 后端：FastAPI（Python）
- 前端：原生 HTML / CSS / JavaScript
- 存储：SQLite（开发）→ PostgreSQL（上线）
- AI：FunASR / SenseVoice（转写）、YOLOv8-pose（姿态估计）

## 目录结构

```text
stagemind/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口（路由 + 静态资源）
│   │   ├── config.py          # 集中配置（路径 / 数据库 / CORS）
│   │   ├── models.py          # SQLAlchemy ORM 模型
│   │   ├── api/               # 路由：上传、排练、日志、台位、看板、检索
│   │   ├── core/              # 数据库会话、Pydantic 请求响应模型
│   │   ├── services/          # AI 服务：asr / llm_struct / pose / tracker / pipeline
│   │   └── worker/            # 后台任务入口（当前进程内线程，后续可换 ARQ/Celery）
│   └── tests/                 # pytest 冒烟测试
├── frontend/                  # 静态前端（FastAPI 直接托管）
├── data/                      # 运行时数据：上传文件、SQLite（已 gitignore）
├── docs/
│   └── data_schema.md         # 结构化数据规范（与方案书一致）
├── requirements.txt
└── .gitignore
```

## 环境准备（Windows）

```powershell
# 1. 创建虚拟环境
py -3 -m venv .venv

# 2. 激活并安装依赖
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 3. 启动后端（自动托管前端页面）
cd backend
python -m uvicorn app.main:app --reload

# 4. 浏览器打开
#    http://127.0.0.1:8000
#    API 文档：http://127.0.0.1:8000/docs
```

服务启动时会创建 `data/`。上传媒体、数据库和模型权重都存放在本地。需要验证转写和台位检测时，从项目根目录安装相应依赖。

```powershell
python -m pip install -r requirements-asr.txt
python -m pip install -r requirements-cv.txt
```

## 运行测试

```powershell
cd backend
python -m pytest -q
```

基础测试不依赖真实媒体。可选的 AI 集成测试需要相应依赖，并在 `data/test_data/` 中放入自己的 `rehearsal_demo.wav` 和 `stage_demo.jpg`。

## 开发路线

| 周次 | 任务 | 对应代码位置 |
| --- | --- | --- |
| W1-W2 | 需求确认与技术验证（ASR / 姿态 demo） | services/ 接口占位 |
| W3-W5 | 模块 A：ASR + LLM 日志结构化 | services/asr.py、llm_struct.py |
| W6-W8 | 模块 B：台位检测与动线生成 | services/pose.py、tracker.py |
| W9-W11 | 前端 + 检索 + 系统集成 | frontend/、api/search.py |
| W12 | 真实排练试用 | 全局 |
| W13-W14 | 打磨、文档与答辩 | 全局 |

## W1 ASR 验证脚本

- 脚本：`scripts/asr_validate.py`，用法见文件头注释，示例：
  `& .venv\Scripts\python.exe scripts/asr_validate.py data\test_data\rehearsal_demo.wav --output data\test_data\asr_out.json`
- 依赖单独在 `requirements-asr.txt`（torch/funasr/modelscope），安装命令见文件注释；模型首次运行自动从 ModelScope 下载（约 1GB，缓存于用户目录）。
- 实测：11 秒中文示例音频，CPU 转写约 0.6 秒（rtf ≈ 0.1），输出句子级 + 词级秒级时间戳 JSON。
- 说明：SenseVoice 文本自带 `<|zh|>` 等标签属官方正常输出；后续 W3 接入 `services/asr.py` 时做标签清洗。

## W2 CV 台位检测验证脚本

- 脚本：`scripts/pose_validate.py`，用法见文件头注释，示例：
  `& .venv\Scripts\python.exe scripts\pose_validate.py data\test_data\stage_demo.jpg --output data\test_data\pose_out.json`
- 依赖单独在 `requirements-cv.txt`（ultralytics）；YOLOv8n-pose 权重首次运行自动下载（约 6MB）。
- 实测：多人测试图检出 4 人台位点，CPU 单帧约 0.5 秒；输出结构已对齐 `services/pose.py` 的 Detection（frame_ts / actor_id / x / y / confidence，归一化 0~1）。
- 说明：台位取人体框底部中心（站立地面点），actor_id 按画面从左到右编号；素材为通用多人示例图，非真实排练录像；低置信度检出点（如 conf<0.5）后续接入时建议过滤。

## W3 后端接入（已验证）

- `services/asr.py`：SenseVoiceTranscriber 已接入真实推理（W1 链路），输出清洗标签后的时间戳片段；模型类级单例懒加载。
- `services/pose.py`：YoloPoseDetector 已接入真实检测（W2 链路），台位取人体框底部中心，conf<0.5 过滤，视频按 0.5s 抽帧。
- `services/tracker.py`：BlockingTracker 已实现检测点到台位记录的映射（跨帧关联与平滑留待 W6-W8）。
- 回归：pytest 14 项全过（新增真实 ASR 转写、真实 YOLO 检测、tracker 映射、真实链路集成测试）。

## W2 视频动线验证

- 素材：`python scripts/make_demo_video.py --source path/to/your-image.jpg` 从自备多人图片合成 3 秒 24fps 演示视频，模拟镜头水平移动。
- 实测：`pose_validate.py` 对视频抽 6 帧，输出 15 个台位点（3 人），frame_ts 0~2.5s 逐帧变化，结果存 `data/test_data/pose_video_out.json`。
- 说明：合成素材仅为链路验证；真实排练视频接入后，低置信点（conf<0.5）与边缘进出场点需结合帧间关联做平滑。

## 日期变更提醒

- 任何人在系统里修改排练日期（`PATCH /api/rehearsals/{id}`，body 传 `{"date": "YYYY-MM-DD"}`）时，自动向全体发送提醒。
- 通知渠道：飞书群机器人 webhook，配置环境变量 `STAGEMIND_WEBHOOK_URL` 后生效；未配置或发送失败时只记录日志，不影响修改。
- 示例（PowerShell 启动前设置）：`$env:STAGEMIND_WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/..."`

## 说明

- LLM 结构化已内置「Schema 校验 → 失败重试（最多 2 次）→ 标记人工复核」逻辑：校验失败时原始转写落盘到 `data/review_queue/`，台位处理继续执行，不中断整条任务；`GET /api/rehearsals?review_pending=true` 可查询待复核清单。
- ASR 和姿态估计使用可选依赖与本地模型。`backend/app/services/llm_client.py` 的模型调用接口待接入，当前调用会将处理任务标记为失败。
- 效果指标（日志生成 ≤10 分钟等）为设计目标值，需在 W12 试用后实测回填。
