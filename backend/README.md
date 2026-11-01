# 英语精读教练 · M1

Flask + SQLAlchemy 的 API 服务 + 零构建静态前端，供 Web / 未来的小程序共同使用。M1 只包含「分段 → 结构 → 逐句」的同步链路，任务化在 M2。

## 快速启动（Windows）

**最简单：在仓库根目录双击 `start.cmd`**（不需要 PowerShell，不受执行策略影响）。

首次会：创建 `.venv` → 安装依赖 → 建库 → 启动服务 → 打开浏览器。

等价的命令行方式：

```powershell
# 仓库根目录，首次执行
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\flask.exe --app wsgi db upgrade
..\.venv\Scripts\flask.exe --app wsgi import-exam-words ..\data\exam_words\zhongkao_sample.csv
cd ..

# 之后每次
.\scripts\dev.ps1        # 或 cd backend; ..\.venv\Scripts\flask.exe --app wsgi serve --port 5000
```

`flask serve` 会在端口绑定成功后打印地址并自动打开 **http://127.0.0.1:5000/**。
端口被占用时给出明确提示，而不是抛栈。

> 常见"打不开"：服务窗口被关掉了 / 直接双击了 `web/index.html`（`file://` 下脚本会被拦截）。
> 正确入口永远是 `http://127.0.0.1:5000/`。

命令行冒烟（不需要浏览器）：

```powershell
.\scripts\smoke.ps1                 # 默认用 data/samples/demo_page.png
.\scripts\smoke.ps1 -Image x.jpg    # 也可以指定图片
.\scripts\smoke.ps1 -Text           # 走纯文本接口
```

## 配置

复制 `backend/.env.example` 为 `backend/.env`。关键项：

| 变量 | 说明 |
|---|---|
| `LLM_API_KEY` | 阿里云百炼华北2（北京）地域创建的 API Key；不要使用其他服务商的 Key |
| `LLM_MODE` | `auto` / `openai` / `fake` |
| `LLM_BASE_URL` | 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`；也可按百炼控制台提供的 API Host 配置业务空间专属地址 |
| `LLM_MODEL_*` | 默认使用 `qwen3.8-max`；图片转写模型必须支持视觉输入 |
| `MAX_IMAGE_MB` / `MAX_IMAGE_COUNT` | 单张图片大小上限 / 单篇最多几张 |
| `TARGET_LEVEL` | 默认 `zhongkao` |
| `EXAM_TAG_SOURCE` | `table`（只认词表）/ `model`（信任模型自报）/ `off` |
| `ENABLE_SYNC_ANALYZE` | 同步分析接口，生产应设为 `0`（改走 M2 的任务接口） |

百炼 API Key 和接入地址按地域区分，需使用与北京地域匹配的 Key。模型名称可在百炼模型广场确认是否已开通。模型请求会显式设置 `enable_thinking=false`，关闭深度思考模式。

## 前端入口

| 路径 | 说明 |
|---|---|
| `GET /` | M1 控制台（`web/index.html`） |
| `GET /assets/*` | 静态资源（`web/css`、`web/js`） |

前端零构建，用原生 ES Modules，暗色赛博科技风。上传支持拖拽、点击选择、`Ctrl+V` 粘贴截图（`web/js/upload.js`）。

分析过程拆成四次调用（`vision` → `segment` → `structure` → `sentences`），
每完成一段就先渲染，不必等整篇跑完。

渲染约束：模型输出一律用 `textContent` / `createTextNode`，禁止 `innerHTML`；
词汇高亮按模型给的句内偏移 `slice` 出来包 `<mark>`。

## 接口（M1）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 运行模式、词表条数 |
| POST | `/api/v1/documents/from-image` | `multipart/form-data`，字段名 `file`（可重复，最多 5 张）→ 视觉模型转写 → id + 识别文本 |
| POST | `/api/v1/documents` | `{text, target_level}` → id + 成本预估（脚本/兜底用） |
| GET | `/api/v1/documents/{id}` | 元信息 + 结构分析 |
| GET | `/api/v1/documents/{id}/sentences` | 逐句精讲，分页 |
| POST | `/api/v1/documents/{id}/analyze` | 同步跑链路（仅开发），可传 `{"stages": ["segment","structure","sentences"]}` 只跑其中几段 |
| POST | `/api/v1/documents/{id}/segment` | 重新分段，需 `{"confirm": true}` |
| GET | `/api/v1/documents/{id}/runs` | 模型调用账本（token、成本、耗时、失败原因） |

分段失败时接口仍返回 200，`stages.segment.status = "failed"`、文档 `segment_status = "unsegmented"`，
此时结构分析照常执行、逐句阶段返回 `skipped` —— 对应计划里的「不分段只读模式」。

## 测试

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

测试全部走夹具，不产生模型费用。其中 `tests/integration/test_web.py` 专门守住「首页与静态资源必须可访问」，
避免再次出现"服务起来了但浏览器进不去"。

## 边界（重要）

- 所有文本处理（切句、断段、标点、词数统计）都由模型完成，本地不做任何规则处理。
- 本地只做：JSON 结构校验、偏移数值平移、查表回填考点标签、越界保护。
- 不比对模型输出与原文是否一致；保真度靠人工抽查（计划中的 G9）。

## M1 完成情况

| 计划任务 | 落点 |
|---|---|
| T1.1 应用工厂 / 配置 / 蓝图 / 迁移 | `app/__init__.py`、`app/config.py`、`migrations/` |
| T1.2 LLM 客户端 + 重试 + 用量账本 | `app/services/llm/client.py`、`AnalysisRun` |
| T1.3 分段 prompt + schema + 续跑 | `app/prompts/segment_v1.md`、`app/services/segmenter/run.py` |
| T1.4 不分段降级模式 | `pipeline.analyze_document` 的失败分支 + `segment_status` |
| T1.5 词表导入与查表 | `app/services/examdict/`、`flask import-exam-words` |
| T1.6 结构分析 | `app/prompts/structure_v1.md`、`analyst/structure.py` |
| T1.7 逐句精讲 | `app/prompts/sentences_v1.md`、`analyst/sentences.py` |
| T1.8 同步端点 + 冒烟脚本 | `api/v1/documents.py`、`scripts/smoke.py` |
| 补充：浏览器入口（原计划在 M2，提前） | `web/`、`scripts/dev.ps1`、`start.cmd`、`tests/integration/test_web.py` |
| 补充：图片输入（视觉模型转写，替代粘贴文本） | `app/prompts/vision_v1.md`、`services/vision/`、`tests/integration/test_image.py` |

**评审点尚未完成**：G2/G3/G9/G11/G13 需要用真实 Key 跑 3 篇常规 + 5 篇对抗样本并人工打分，
当前冒烟用的是夹具（`llm_mode=fake`），只能证明链路通、不能证明讲解质量。
