# ScriptDoc / SerialDoc

ScriptDoc 为中文剧本提供台词风格诊断。读剧页面按幕、场、角色和原文行组织对白，显示前后接话、附近的舞台提示、规则依据和排练建议。规则得分反映措辞与句式信号，可按说话人和场景校准，供人工复核。SerialDoc 是面向连续剧的诊断方案。

- [ScriptDoc 项目方案](ScriptDoc_剧本诊断项目方案.html)
- [SerialDoc 项目方案](SerialDoc_剧集剧本诊断项目方案.html)

## 运行原型

需要 Python 3.10 或更新版本。规则引擎使用 Python 标准库，可直接运行命令行演示和规则测试。

```sh
python scriptdoc_engine/cli.py
python scriptdoc_engine/test_engine.py
```

安装依赖后可以启动 HTTP 接口，测试脚本也会运行接口检查。

```sh
python -m pip install -r requirements.txt
python -m uvicorn api:app --app-dir scriptdoc_engine --host 127.0.0.1 --port 8000
```

启动后访问 `http://127.0.0.1:8000/`，可粘贴带有 `角色：台词` 标记的剧本文本。下载仓库后双击 [`share/index.html`](share/index.html) 可以查看离线示例。

`POST /api/analysis/script` 接收 `text`、可选的 `scene_type` 和按角色名索引的 `role_types`。遇到未识别的说话人，页面会保留原文行号并标为待核对。舞台提示和待核对行不计入场景均分。结构化输入仍使用 `POST /api/analysis/chuuni`，也可提供额外语义分数。完整接口文档位于 `http://127.0.0.1:8000/docs`。

读剧流程参考 [Curtain Up](https://curtainup.app/en) 的场景和角色组织方式。ScriptDoc 的语气和排练建议来自可复核的文字规则。词表、权重和校准参数位于 `scriptdoc_engine/config/chuuni_config.json`。
