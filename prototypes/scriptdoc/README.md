# ScriptDoc / SerialDoc

ScriptDoc 的原型为中文剧本提供台词风格诊断。规则引擎标记夸张措辞和句式，结合角色与场景校准得分，并返回命中依据和修改建议。调用方可以提供额外的语义分数。SerialDoc 是面向连续剧的诊断方案。

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

本地接口文档为 `http://127.0.0.1:8000/docs`，诊断接口为 `POST /api/analysis/chuuni`。词表、权重和情境校准参数位于 `scriptdoc_engine/config/chuuni_config.json`。
