# 英语精读教练 · 项目计划

> 一句话定位：**上传一篇英语文章，AI 像英语老师一样逐句精讲 —— 讲句式、讲考点，重点对标近三年中高考高频词，并把同一个词在不同句子里的不同意思摆在一起对比。**

| 项 | 内容 |
|---|---|
| 文档版本 | v1.5（中考优先 + 词表分阶段建设） |
| 更新日期 | 2026-10-20 |
| 形态 | **Flask 后端 API 服务 + 纯静态 Web 前端**，预留微信小程序等多客户端 |
| 分析引擎 | 大模型 API（OpenAI 兼容协议） |
| 目标用户 | **中考备考学生为主**（高考同结构，词表后补）；次要：英语教师备课 |
| 本地文本处理 | **零**（不切句、不断段、不改标点、不统计、不校验） |
| 预计周期 | 5 周 / 约 11.5 人日（每晚 2–3 小时 + 周末） |

### 变更记录

| 版本 | 变更 |
|---|---|
| v1.5 | **默认学段定为中考**（`TARGET_LEVEL=zhongkao`，考纲词表约 1600 词）；**词表分阶段建设**：v1 只导公开考纲词表，近三年真题词表后补；真题标签缺失时的 UI 与接口行为已定义 |
| v1.4 | **产品定位改为"备考精读教练"**：新增考纲/真题词表资产、考点标注、教师口吻讲解规范；**新增"多语境对比"阶段**（同一词在不同句中的义项对照）；测验题型对齐中高考（词义辨析/语法填空/完形） |
| v1.3 | 取消本地分段校验；分段失败降级为不分段只读模式；词汇高亮改用句内相对偏移 |
| v1.2 | 取消所有本地文本处理（删归一化、`pysbd`、本地词数）；新增 LLM 分段阶段 |
| v1.1 | 由 Next.js 全栈改为 Flask API + 纯静态前端；进度改轮询；认证改 Bearer；加成本护栏 |
| v1.0 | 初版（Next.js + SQLite + FSRS） |

---

## 1. 产品定义

### 1.1 一句话说明它和"翻译工具"的区别

翻译工具回答"这句什么意思"；**这个程序回答"这句为什么这么写、这个词考过几次、它在另一句里为什么是另一个意思"**。

四件事构成完整闭环：

1. **全文骨架** —— 体裁、段落作用、论证链（先看整体，避免陷进细节）。
2. **逐句精讲** —— 骨架、语法点、考点，像老师当面讲。
3. **考点词对照** —— 每个词标注是否考纲词/近三年真题词，并给出**同一词的多语境对比**。
4. **复习与测验** —— 生词进 FSRS 队列，测验题型对齐中高考。

### 1.2 核心差异化：多语境对比

这是本产品最该做扎实的功能。学生在真实考试里丢分，常常不是"不认识这个词"，而是"认识的是另一个意思"。

**产品行为**：文章分析完成后，系统找出本文中被重复使用、或存在多义/多词性的词，生成一张对照卡：

```
address  高考高频 · 2024 全国乙卷 · 2023 新课标 I 卷

① 本文第 12 句   v. 处理；应对
   "The report fails to address the root cause."
   搭配：address a problem / address concerns
   辨析：此处必须理解为动词，后接抽象名词作宾语

② 本文第 31 句   n. 地址；演讲
   "He delivered the opening address."
   搭配：deliver an address / opening address

对比：同一个词在两处的词性不同，判断依据是"后面接什么" ——
      接名词短语多为动词，前面有冠词/形容词多为名词。
易错：多数学生只记"地址"，读到时自动套用，导致整句理解偏移。
```

**判定"哪些词值得对比"也交给模型**（不让本地做词频统计）：在专门的阶段里，让模型输出"本文中重复出现且语义/词性有变化的词"，以及"考纲内但本文用法特殊"的词。

> 上面示例用的是高考高频词。**中考版机制完全相同**，只是词表范围换成约 1600 词的初中考纲，且"真题标签"在 v1 可能暂时为空（显示为"中考考纲·高频"）。

### 1.3 目标词表：考纲 + 近三年真题

"对标近三年中高考重点单词"必须有**可查的数据**，不能靠模型自报（模型会编造"这是 2024 年高考词"）。因此需要一份词表资产：

| 数据 | 内容 | 来源 | v1 是否就绪 |
|---|---|---|---|
| 考纲词表（**中考，默认**） | 约 1600 词，含词性与基本义项 | 公开的义务教育英语课程标准词汇表 | ✅ 先做 |
| 考纲词表（高考） | 约 3500 词 | 公开的普通高中英语课程标准词汇表 | ⏳ 后补，表结构一致 |
| 真题高频词 | 近三个考试年度真题中出现过的词，含年份、卷别、词频 | 从真题整理（人工或用模型抽取后人工校核） | ⏳ 后补，v1 允许为空 |
| 分级 | `高频 / 中频 / 低频`，用于决定讲解优先级 | 按出现频次与考纲权重划分 | ✅ 考纲表自带 |

**v1 在"真题词表为空"时的行为**（必须先定死，否则前端会显示空白或报错）：

- `exam_words.years_json` / `papers_json` 为空数组 → 前端**只显示"中考考纲 · 高频"**，不显示年份卷别，也不显示"真题"字样。
- 标签取值统一走 `exam_label` 字段：`"中考考纲·高频"` / `"中考考纲·高频·2025 北京卷"`，由服务端拼好，客户端不做字符串拼接。
- 词表补齐后无需改代码，重新导入即可让历史文章显示更完整的标签（读取时实时查表，不回写 `sentences`）。

**版权说明**：词表只保存"词 + 统计 + 出处标注"，**不保存真题原文**。系统里呈现的是"address 出现在 2024 全国乙卷"，不是试卷内容。

**词表怎么用**（这一步不算文本处理，是查表）：

```
模型输出：本句的重点词 + lemma + "疑似考纲/真题词"
        ↓
服务端查 exam_words 表 → 回填 level / band / years / papers
        ↓
查不到 → 不显示真题标签（避免编造），仍保留模型给的"考纲词"判断
```

可用 `EXAM_TAG_SOURCE = table | model | off` 控制。默认 `table`：**年份和卷别只认表里的数据**。

### 1.4 教师口吻：讲解规范

"像英语老师"是可以落成规则的东西，写进 prompt：

| 规则 | 反例（不要） | 正例（要） |
|---|---|---|
| 先给结论再给理由 | "本句的意思是……" | "这句主干是 X，难点在后面那个分词短语 —— 它修饰的是 Y 不是 Z。" |
| 讲"为什么"，不只讲"是什么" | "which 引导定语从句" | "这里用 which 不用 that，是因为前面有逗号，属非限制性定语从句，去掉后句子仍成立。" |
| 指出考法 | "address 意为处理" | "address 高考常考'处理问题'这个动词义，尤其完形里和 solve/tackle 一起辨析。" |
| 点出学生易错 | — | "别按'地址'理解，否则后半句逻辑不通。" |
| 禁止模板套话 | "本句结构清晰，值得学习" | — |

### 1.5 成功标准（可验收）

| 编号 | 标准 | 验证方式 |
|---|---|---|
| G1 | 1500 词文章端到端出结果 ≤ 3 分钟 | 计时 3 篇样文 |
| G2 | 结构分析能说清"体裁 + 段落作用 + 论证链" | 3 篇样文人评 ≥ 4/5 |
| G3 | 每句有译文 + ≤4 个重点词 + ≤2 个语法点，且词能高亮 | 人工抽查 30 句 |
| G4 | 生词一键入库，按 FSRS 排下次复习 | 单测 + 手动 |
| G5 | 测验每题有答案 + 原文依据句 | 人工抽查全部题目 |
| G6 | 分析中断可续跑，不重复扣费 | 手动杀进程重试 |
| G7 | 单篇成本 ≤ ¥0.25（含分段与多语境阶段） | 记录 token 账单 |
| G8 | 客户端只依赖 JSON + Bearer + 轮询即可跑通 | curl 全流程脚本 |
| G9 | 分段保真度：全句拼接与原文一致 | **人工抽查**（3 篇 × 20 句，不自动化） |
| G10 | 分段失败时应用不崩，进入不分段只读模式 | 构造非法返回验证 |
| **G11** | **考点词召回 ≥ 90%**：人工标注的考纲/真题词，模型识别出九成以上 | 3 篇样文人工标注对照 |
| **G12** | **多语境对比 ≥ 3 组/篇**，且每个义项与所在句匹配 | 人评 ≥ 4/5 |
| **G13** | **讲解"老师感" ≥ 4/5**，无模板套话 | 盲评 10 段讲解 |
| **G14** | 测验题型覆盖词义辨析 + 语法填空 + 完形 | 人工检查题库 |

### 1.6 非目标（v1 不做）

- 不做完整题库/真题练习系统（只做"针对本文"的测验）。
- 不做作文批改、听力、口语。
- 不做微信小程序本体（v1 只保证 API 契约可用，P1 再做）。
- 不做 PDF/EPUB 解析（P1）。
- 不做多租户/团队协作。
- **不做任何本地文本校验与修补**（沿用 v1.3 决定）。

---

## 2. 技术选型

### 2.1 决策与理由

| 层 | 选择 | 理由 |
|---|---|---|
| Web 框架 | **Flask 3.x + 应用工厂 + 蓝图** | 轻、易部署；按 `/api/v1/<domain>` 切分，适配多端 |
| 跨域 | 开发期同源（Flask 托管静态）；生产 Nginx 同源 | 避开 CORS 与预检 |
| ORM | **SQLAlchemy 2.0 + Alembic** | 开发 SQLite，生产 PostgreSQL，代码不变 |
| 数据校验 | **Pydantic v2** | 只校验 JSON 结构，不校验内容与原文是否一致 |
| 切句/断段/标点 | **大模型** | 所有文本处理交模型，本地零规则 |
| 文本正确性 | **信任模型，不做自动校验** | 按需求；保真度靠人工抽查 + 重新分段 |
| **考纲/真题标签** | **`exam_words` 词表查表回填** | 避免模型编造年份/卷别；查表不是文本处理 |
| 模型调用 | `openai` SDK + `base_url` 覆盖 | 可切 DeepSeek / 通义 / 智谱 / Ollama |
| 重试 | `tenacity` | 429/5xx 指数退避 |
| 复习算法 | `fsrs`（py-fsrs） | 比 SM-2 准 |
| 限流/配额 | `flask-limiter` | 公网部署控成本 |
| 生产运行 | gunicorn + Nginx + systemd（或 Docker） | Windows 本地用 `flask run` / `waitress` |
| 前端 | 原生 HTML + CSS + ES Modules，零构建 | 静态托管；小程序复用同一套 API |
| 测试 | `pytest` + `pytest-flask` + `vcrpy` | 离线跑，不花模型钱 |

**不引入**：`pysbd`、`tiktoken`、任何分词/NLP 库、前端框架。

### 2.2 "查词表"为什么不违反"零本地处理"

| 说法 | 判定 |
|---|---|
| 把文章切句、改标点、统计词频 | ❌ 文本处理，交给模型 |
| 拿模型给的 `lemma` 去 `exam_words` 查有没有这条记录 | ✅ 数据库查询，不产生文本、不改变文本 |
| 用查到的记录覆盖模型自报的年份 | ✅ 事实回填，属于数据校正而非语言分析 |

如果你希望连查表都不要（完全信模型），把 `EXAM_TAG_SOURCE` 设为 `model` 即可，代价是可能出现"模型编造出处"。

### 2.3 这个决定的代价（知情并接受）

| 代价 | 表现 | 应对 |
|---|---|---|
| 非确定性 | 同一篇两次切法可能不同 | 分段结果固化，不重算 |
| 可能篡改原文 | 合并句子、改标点、补全省略 | 提示词强约束 + `complete` + 人工抽查 G9 + 重新分段 |
| 偏移可能错位 | 模型给的全文偏移未必准 | 正文用 `sentences.text` 渲染，偏移只用于定位 |
| 异常文本可能永不通过 | 无标点长句、代码块 | 降级不分段只读模式 + 可反复重试 |
| 多一次调用（分段）+ 一次调用（多语境） | 成本上升 | 分段/多语境用便宜模型；单篇仍 ≤ ¥0.25 |

---

## 3. 系统架构

```
┌──── 客户端层 ────────────────────────────────────────────────┐
│  Web（HTML/CSS/JS，静态托管）   │  微信小程序（P1）  │ 未来 App │
└──────────────┬───────────────────────────────┬───────────────┘
               │  HTTPS + JSON + Bearer Token  │
┌──────────────▼───────────────────────────────▼───────────────┐
│  Nginx（TLS 终止 / 静态文件 / 反向代理 /api）                  │
└──────────────┬───────────────────────────────────────────────┘
┌──────────────▼───────────────────────────────────────────────┐
│  Flask (gunicorn, /api/v1)                                    │
│  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌────────┐ ┌─────────┐  │
│  │ auth     │ │ documents│ │ jobs   │ │ review │ │ quiz    │  │
│  │ words    │ │ sentences│ │ events │ │        │ │         │  │
│  └────┬─────┘ └────┬─────┘ └───┬────┘ └───┬────┘ └────┬────┘  │
│       └────────────┴───────────┴──────────┴───────────┘       │
│                    ┌──────────────────────┐                   │
│                    │ Service 层            │                   │
│                    │ segmenter/  ← LLM     │                   │
│                    │ analyst/    ← LLM     │                   │
│                    │ polysemy/   ← LLM     │                   │
│                    │ examdict/   ← 查表    │                   │
│                    │ review/ quiz/         │                   │
│                    └──────────┬───────────┘                   │
└───────────────────────────────┼───────────────────────────────┘
        ┌───────────────────────┼───────────────────────┐
┌───────▼────────┐   ┌──────────▼─────────┐   ┌─────────▼──────┐
│ PostgreSQL     │   │ 后台任务执行器       │   │ LLM API        │
│ (生产)         │   │ 线程池 → Redis 队列  │   │ OpenAI 兼容     │
│ SQLite(开发)    │   │ (MVP → 生产演进)     │   └────────────────┘
└────────────────┘   └────────────────────┘
        ▲
   exam_words 词表（CSV 导入）
```

**阶段依赖**：

```
POST /analyses {kind:"full"}
   └─ stage: segment       1 次（未 complete 则续跑，max 3）
        ├─ stage: structure   1 次 ┐ 并行
        └─ stage: sentences   N 批 ┘
             └─ stage: polysemy  1 次（依赖全部逐句结果，做跨句对比）
```

`polysemy` 放在 sentences 之后而不是并行，是因为它需要复用逐句阶段已经产出的"该句单词在此处的释义"，避免两次判断不一致。代价是多约 20 秒，换来对比卡与句子讲解的口径统一。

**任务执行演进**（对外契约不变）：

| 阶段 | 实现 | 适用 |
|---|---|---|
| MVP | 进程内 `ThreadPoolExecutor(3)`，状态存 `jobs`/`job_batches` | 本地/单用户 |
| 上线 | 独立 worker + Redis 队列（`rq`） | 多 gunicorn worker、重启不丢任务 |

> 进程内线程池必须配 `gunicorn -w 1`，否则任务会被重复领取。

---

## 4. 数据模型

```sql
users(id, client_type, device_id, token_hash, wechat_openid, created_at)

documents(id, user_id, title, raw_text, content_hash, source, created_at,
          target_level,               -- zhongkao（默认） | gaokao
          source_meta_json,           -- 图片：{pages, complete, notes, page_chars}
          extraction_model, extraction_prompt_version,
          segment_status, segment_model, segment_prompt_version)
-- source: paste | image
-- segment_status: pending | segmented | unsegmented | failed
-- raw_text: 图片上传时为视觉模型转写结果，之后只存不改

jobs(id, user_id, document_id, kind, status, current_stage,
     error_code, error_message, usage_json, created_at, started_at, finished_at)
-- kind: full | segment | structure | sentences | polysemy | quiz

job_batches(id, job_id, stage, batch_index, sentence_from, sentence_to,
            status, attempts, error_code, finished_at)

sentences(id, document_id, idx, para_idx, text, char_start, char_end,
          translation, difficulty, structure_hint, note, seq)
-- text: 模型返回的句子原文（渲染唯一依据）
-- char_start/char_end: 全文偏移，仅用于定位，不校验

sentence_grammar(id, sentence_id, label, span_start, span_end,
                 explain_cn, exam_tip)          -- exam_tip: 该语法点怎么考
sentence_vocab(id, sentence_id, surface, span_start, span_end,
               sense_cn, collocations_json, pitfall_cn)

vocab(id, user_id, lemma, surface, pos, phonetic, meaning_cn,
      in_context_cn, document_id, sentence_id, created_at,
      exam_level, exam_band, exam_years_json, exam_papers_json, exam_source)
-- exam_source: table | model  —— 标明标签来自查表还是模型自报
-- UNIQUE(user_id, lemma)

-- ★ 多语境对比（新增）
word_profiles(id, document_id, lemma, pos, exam_level, exam_band,
              exam_years_json, exam_papers_json, contrast_cn,
              pitfall_cn, occurrence_count)
word_senses(id, word_profile_id, sense_cn, pos, sentence_id,
            span_start, span_end, surface, nuance_cn,
            collocations_json, example_cn)

-- ★ 考点词表（新增，全局共享，不随用户）
exam_words(id, lemma, pos, level, band, syllabus, years_json,
           papers_json, senses_json, updated_at)
-- level: zhongkao | gaokao | beyond
-- band: high | mid | low
-- UNIQUE(lemma, pos, level)

review_cards(vocab_id PK, state, due_at, stability, difficulty,
             reps, lapses, last_review_at)
review_logs(id, vocab_id, rating, reviewed_at)

quizzes(id, document_id, questions_json, created_at)
-- questions: [{type: 'sense_discrimination'|'grammar_cloze'|'cloze'|'translation', ...}]
quiz_attempts(id, quiz_id, answers_json, score, created_at)

settings(user_id, key, value)
```

设计要点：

- **`word_profiles` / `word_senses` 是新的核心表**：一个词在一篇文章里对应一张 profile，下面挂 N 个义项（每个义项指向具体句子）。这是"多语境对比"的数据基础。
- **`exam_words` 是全局资产**，与用户数据分离，便于独立更新词表版本。
- **`vocab` 仍保留**（用户生词本条目），通过 `lemma` 与 `word_profiles` 关联；复习卡挂 `vocab`。
- **正文渲染只依赖 `sentences.text`**，偏移错了不影响显示。

---

## 5. 分析流水线（核心）

### 5.1 五个阶段

```
① 图像识别  [LLM-视觉] 图片[] → 正文文本（逐字符转写，不翻译不改写）+ 标题 + 缺页/看不清说明
② 分段切句  [LLM] 原文 → 段落[] → 句子[]（原文 + 偏移 + 标题 + 统计 + complete）
③ 结构分析  [LLM] 段落划分 → 体裁/主旨/段落作用/论证链/阅读建议
④ 逐句精讲  [LLM] 每 4–6 句 → 译文/骨架/语法点/考点词（含句内偏移、搭配、易错点）
⑤ 多语境对比 [LLM] 全文 → 重复/多义词的义项对照 + 辨析
   入库     句子、词汇、word_profiles 落库；查 exam_words 回填标签；生成 FSRS 卡
```

**没有本地预处理**：不 trim、不去页眉、不合并连字符断行、不统一引号。原文进，原文出。
**图片也不用本地 OCR**：不用 Tesseract / PaddleOCR，图片直接交给视觉模型转写，
本地只做 base64 编码（传输格式，不是文本分析）。

**为什么用视觉模型而不是本地 OCR**：教材照片常有阴影、倾斜、双栏、水印，
传统 OCR 需要预处理（去噪、纠偏、二值化）——那些全是本地文本/图像处理，与"本地零处理"的约束冲突；
视觉模型天然能处理这些情况，并且能顺带完成"跳过页眉页码、只取正文"的判断。

### 5.2 分段切句（同 v1.3）

```jsonc
{
  "title": "The Case Against Remote Work",
  "complete": true,
  "paragraphs": [
    { "index": 1,
      "sentences": [
        { "index": 1, "text": "It was the best of times...", "char_start": 0, "char_end": 58 }
      ] }
  ],
  "stats": { "sentence_count": 68, "word_count": 1523, "language": "en" }
}
```

**硬约束**：逐字符照抄（不改标点/拼写/大小写/引号）、不合并不拆分、不增删、偏移自洽、顺序单调、标题单独返回、`complete` 如实汇报。

**截断续跑**：`complete == false` 或 `finish_reason == "length"` 时，用最后一句的 `char_end` 作起点再发一次（附前句作锚点），最多 3 次。

### 5.3 逐句精讲（新增考点字段）

**选词规则**（写进 prompt，优先级从上到下）：

1. **考纲内 + 近三年真题出现过的词** —— 必讲，即使很简单（如 `address`、`matter` 这类多义词）。中考版以初中考纲（约 1600 词）为范围。
2. **考纲内但本文用法特殊** —— 必讲（如熟词僻义）。
3. **超纲但影响理解** —— 讲，并标 `超纲，了解即可`。
4. **考纲内基础词且用法常规**（`because`、`important`）—— **不讲**。

每句最多 4 个词、2 个语法点。

```jsonc
{
  "sentences": [
    {
      "id": 17,
      "translation": "……",
      "structure_hint": "主干 + 两个定语从句",
      "difficulty": 3,
      "key_vocab": [
        {
          "surface": "addresses",
          "span_start": 36, "span_end": 45,        // 相对本句 text
          "lemma": "address",
          "pos": "v.",
          "sense_cn": "处理；应对",                  // 本句中的具体义项
          "collocations": ["address a problem", "address concerns"],
          "pitfall_cn": "别按'地址'理解，否则后半句逻辑不通",
          "exam_hint": "高考常与 solve / tackle 在完形中辨析",
          "syllabus_guess": "gaokao"                // 模型自评，服务端查表回填
        }
      ],
      "grammar": [
        {
          "label": "非谓语-分词",
          "span_start": 0, "span_end": 9,
          "span": "Faced with",
          "explain_cn": "过去分词作状语，逻辑主语是主句主语",
          "exam_tip": "语法填空常考：此处只能用过去分词，因为主语是被动承受"
        }
      ]
    }
  ]
}
```

**固定语法标签表**（枚举）：
时态 · 被动语态 · 情态动词 · 虚拟语气 · 定语从句 · 状语从句 · 名词性从句 · 非谓语-不定式 · 非谓语-分词 · 非谓语-动名词 · 倒装 · 强调句 · 比较结构 · 平行结构 · 插入语 · 省略 · 词类活用

### 5.4 多语境对比（新增核心阶段）

**输入**：全部分段句子 + 逐句阶段的 `key_vocab`（含本句义项）。

**模型要找出三类词**：

1. **重复出现且语义/词性不同的词**（重点）
2. **考纲高频多义词**（即使只出现一次，也说明其常见义项与本文义项的差异）
3. **熟词僻义**（如 `address` 作动词、`last` 作动词）

```jsonc
{
  "words": [
    {
      "lemma": "address",
      "pos": "v./n.",
      "occurrence_count": 2,
      "contrast_cn": "两处词性不同。判断依据是后面接什么：接名词短语多为动词，前面有冠词/形容词多为名词。",
      "pitfall_cn": "多数学生只记'地址'，读到时自动套用，导致整句理解偏移。",
      "exam_hint": "近三年高考完形与阅读中，address 的动词义出现频次高于名词义。",
      "syllabus_guess": "gaokao",
      "senses": [
        {
          "sentence_id": 12,
          "surface": "addresses",
          "span_start": 36, "span_end": 45,
          "pos": "v.",
          "sense_cn": "处理；应对",
          "nuance_cn": "此处后接 the root cause，是'着手解决'的意思，不表示'对……讲话'",
          "collocations": ["address a problem", "address concerns"],
          "example_cn": "政府必须解决住房短缺问题。"
        },
        {
          "sentence_id": 31,
          "surface": "address",
          "span_start": 12, "span_end": 19,
          "pos": "n.",
          "sense_cn": "演讲；致辞",
          "nuance_cn": "前面有 opening 修饰，且与 deliver 搭配，可确定是名词",
          "collocations": ["deliver an address", "opening address"],
          "example_cn": "校长作了开学致辞。"
        }
      ]
    }
  ]
}
```

**质量要求**：

- 每篇至少 3 组；不足 3 组时如实返回（不要硬凑，避免把简单词强行解释成多义）。
- 每个义项必须指向**具体句子**并给句内偏移，前端才能点回原文。
- `nuance_cn` 必须解释"**凭什么判断是这个义项**"（搭配、词性、上下文逻辑），这是教师价值的核心。
- 不重复逐句阶段已经说过的内容，只做"对比"这一件新增的事。

### 5.5 结构分析

```jsonc
{
  "genre": "argumentative",
  "topic": "远程办公的生产力争议",
  "difficulty": { "level": "B1", "exam": "中考", "reason": "长难句较少，但抽象名词与被动语态密集" },
  "thesis": "作者认为远程办公的收益被高估",
  "sections": [
    { "paragraphs": [1, 2], "role": "background", "summary_cn": "…" },
    { "paragraphs": [3, 5], "role": "evidence",   "summary_cn": "…" }
  ],
  "logic_flow": ["提出现象", "引用研究", "反驳对立观点", "让步", "结论"],
  "reading_tips": ["第 4 段是转折，注意 however 后的真正主张"]
}
```

### 5.6 降级：不分段只读模式

分段反复失败时 `segment_status = unsegmented`：

| 可用 | 不可用 |
|---|---|
| 阅读 `raw_text`（按用户自己的换行） | 点句、逐句译文、语法点 |
| 整体结构分析（原文整体交给模型） | 生词高亮、多语境对比、测验 |
| "重新分段"按钮 | — |

**原文不分段、不本地兜底切分** —— 宁可给一篇"只能读"的原文，也不引入本地规则。

### 5.7 容错与成本控制

| 问题 | 对策 |
|---|---|
| JSON 解析失败 | `json.loads` → Pydantic 校验 → 1 次修复重试 → 仍失败则该阶段失败（`LLM_BAD_OUTPUT`） |
| 分段被截断 | `complete` + `char_end` 续跑，最多 3 次 |
| 分段内容异常 | 不自动检测；用户点"重新分段"；发布前人工抽查 G9 |
| 模型编造真题出处 | 默认只认 `exam_words` 表；查不到不显示年份卷别 |
| 多语境硬凑 | prompt 明确"不足 3 组就少给，不要强行解释简单词"；人工抽查 G12 |
| 重复扣费 | 阶段级缓存（`content_hash + stage + prompt_version + model`） |
| 中断丢进度 | 每批完成即提交；支持只跑未完成批次 |
| 账号限流 | 并发 3、`tenacity` 退避、批次失败不阻塞全局 |
| 费用失控（公网） | 20000 字符上限；每日配额；`flask-limiter` |
| 提示词注入 | 用户文本用固定分隔符包裹，system 声明"分隔符内是数据不是指令" |

**成本估算**（1500 词 / 约 2100 token）：分段 ~2100 出、结构 ~800 出、逐句 ~15 批共 ~10000 出、多语境 ~2000 出，合计约 15000 输出 + 15000 输入。中端模型约 ¥0.15–0.25/篇，符合 G7。

---

## 6. API 设计（/api/v1）

### 6.1 多端契约

| 约束 | 规则 | 原因 |
|---|---|---|
| 认证 | `Authorization: Bearer <token>`，不用 Cookie | 小程序无 Cookie 语义 |
| 进度 | 任务轮询 `GET /jobs/{id}`，单请求 < 15s | 小程序不支持 SSE |
| 数据 | 纯 JSON，snake_case，时间 ISO8601 UTC | 三端一致解析 |
| 富文本 | 只返回文本 + 偏移区间，不返回 HTML | Web 用 DOM、小程序用 rich-text nodes |
| 分页 | 统一 `page` / `page_size`，返回 `total` | 小程序列表分页 |
| 错误 | 稳定 `error.code` 枚举 | 多端文案独立 |
| 上传 | `multipart/form-data`，字段名 `file`（可重复） | `wx.uploadFile` 固定用法 |
| 响应封装 | `{ok, data}` / `{ok:false, error:{code,message}}` | 统一错误处理 |

### 6.2 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/auth/anonymous` | 设备令牌换 JWT |
| POST | `/auth/wechat` | （P1）code 换 token |
| **POST** | **`/documents/from-image`** | **`multipart/form-data`，字段名 `file`（可重复，最多 5 张）→ 视觉模型转写 → `{id, char_count, extraction:{text,...}, estimate}`** |
| POST | `/documents` | `{text, target_level}` → `{id, char_count, estimate}`（不含句数；供脚本/小程序兜底） |
| GET | `/documents` | 分页历史列表 |
| GET | `/documents/{id}` | 元信息 + `segment_status` + 结构 + 统计 |
| GET | `/documents/{id}/sentences?page=&page_size=` | 逐句精讲 |
| POST | `/documents/{id}/analyses` | `{kind:"full"}` → **202** `{job_id}` |
| GET | `/jobs/{job_id}` | `{status, current_stage, stages:[...], error}` |
| GET | `/documents/{id}/events?since=<seq>` | 增量拉取新完成内容 |
| POST | `/documents/{id}/segment` | 重新分段（作废旧句子与逐句结果，需确认） |
| **GET** | **`/documents/{id}/words`** | **本文考点词清单**（可按 band/出现次数排序） |
| **GET** | **`/documents/{id}/words/{lemma}`** | **多语境对比卡**（profile + senses + 真题标签） |
| GET | `/vocab?filter=&page=` | 生词本 |
| POST | `/vocab` | 加入生词（可带 `sense_cn`，支持"同词不同义"各建一张卡） |
| GET | `/review/queue?limit=20` | 今日到期卡片 |
| POST | `/review/{vocab_id}/grade` | `{rating: 1..4}` → 下次 `due_at` |
| POST | `/documents/{id}/quiz` | `{types:["sense_discrimination","grammar_cloze","cloze"]}` → `{job_id}` |
| POST | `/quizzes/{id}/attempts` | 提交作答，返回得分与解析 |
| GET/PUT | `/me/settings` | 目标等级（中考/高考）、模型偏好 |

**契约细节**：

- `POST /documents` 的 `target_level` 影响选词阈值（中考/高考考纲范围不同），必须在建文档时确定。**默认 `zhongkao`**，前端导入页把中考设为默认选项。
- `POST /vocab` 支持 `lemma + sense_cn` 组合去重：`address(v.处理)` 与 `address(n.地址)` 是两张不同的复习卡 —— 这正是"多语境"落到复习环节的方式。
- 错误码：`SEGMENT_INCOMPLETE`、`LLM_BAD_OUTPUT`、`QUOTA_EXCEEDED`、`LLM_UNAVAILABLE`、`DOC_TOO_LARGE`。无 `SEGMENT_MISMATCH`（不做一致性判断）。

**轮询节奏**：1.5s 起，无进展退避到 3s、5s；`document.hidden` 暂停。

---

## 7. 前端设计（原生 HTML/CSS/JS）

### 7.1 页面

| 文件 | 职责 |
|---|---|
| `index.html` | 导入：**拖拽/点击/粘贴上传文章图片**（最多 5 张）、**选目标等级（中考/高考）**、预估、开始 |
| `read.html?id=` | 阅读页（核心） |
| `words.html?id=` | 本文考点词清单 + 多语境对比 |
| `vocab.html` | 生词本 |
| `review.html` | 复习翻卡 |
| `quiz.html?id=` | 测验 |
| `settings.html` | 模型/等级/主题 |

共享：`js/api.js`、`js/poller.js`、`js/dom.js`、`js/store.js`。

### 7.2 四段式进度

```
[上传] → [图像识别中…（N 张）]        ← 1，不确定进度条
       → [AI 正在分段与切句…]        ← 2
       → [正在分析结构 / 逐句精讲 9/15]  ← 3+4，可先读
       → [正在整理多语境对比…]        ← 5
       → [完成]
```

阶段 4 一到就先渲染，边读边等；阶段 5 完成后"词汇"Tab 出现对比卡。
识别完成后提供「查看识别出的原文」折叠区 —— 因为本地不做保真校验，用户必须能自己核对 OCR 结果。

### 7.3 阅读页

- 左栏：按段落排版，每句 `<span data-idx>`，正文取 `sentences.text`。
- 考点词高亮：用 `span_start/span_end` 在句内切片；**考纲高频词加底部虚点**，超纲词加浅灰底（视觉上区分优先级）。
- 右栏 Tab：
  - **结构**：体裁、主旨、段落作用色条、论证链、阅读建议。
  - **逐句**：译文、句法骨架、语法点（含"这一处怎么考"）、词汇（搭配 + 易错）。
  - **词汇**：本文考点词列表（按考纲级别/出现次数），点开进对比卡。
  - **笔记**。
- 词卡浮层：点词 → 显示本句义项 + "本文共出现 N 次" → 一键跳到对比卡。

### 7.4 多语境对比卡（新）

```
┌──────────────────────────────────────────────┐
│ address   高考高频 · 2024 全国乙卷 · 2023 新课标 │
├──────────────────────────────────────────────┤
│ ① 第 12 句  v. 处理；应对                     │
│    "The report fails to address the root..." │
│    搭配 address a problem / address concerns │
│    为什么是动词：后接 the root cause          │
├──────────────────────────────────────────────┤
│ ② 第 31 句  n. 演讲；致辞                     │
│    "He delivered the opening address."       │
│    搭配 deliver an address                   │
├──────────────────────────────────────────────┤
│ 对比：靠"后接什么"判断词性……                  │
│ 易错：只记"地址"……                            │
│                        [加入生词本] [加入复习] │
└──────────────────────────────────────────────┘
```

加入生词本时默认带上**当前义项**，这样复习时不会出现"认识但记错义项"。

### 7.5 复习与测验

- 复习卡正面：句子挖空（目标词位置用 `span_start/span_end` 打码）+ "此处是什么意思"；背面：义项、搭配、易错点、其他语境。
- 测验三类：
  1. **词义辨析**：同一词在本文两个语境中的义项，选正确对应。
  2. **语法填空**：从本文挑语法点改造成填空。
  3. **完形**：从本文挖 5 空，选项含本文中的近义/易混词。

### 7.6 渲染安全

```js
// ✗ 禁止
el.innerHTML = sentence.translation;
// ✓ textContent 逐块构建；高亮按句内偏移切分
```
`slice` 越界返回空串，不抛异常，因此无需为"模型偏移错误"加本地判断。

---

## 8. 里程碑与任务拆解

> 策略：先用 curl 验证"分段 + 逐句讲解 + 多语境对比"的质量（风险最高），再做任务化与界面。

### M1 · 后端垂直切片（第 1 周，约 3 人日）

| ID | 任务 | 估时 | 依赖 |
|---|---|---|---|
| T1.1 | Flask 应用工厂 + config + `/api/v1` 蓝图 + SQLAlchemy/Alembic | 2h | — |
| T1.2 | LLM 客户端：openai SDK + base_url + tenacity + usage/费用记录（含视觉入参） | 3h | T1.1 |
| **T1.2b** | **图片上传接口 + 视觉转写 prompt（`vision_v1`）+ 格式/大小/数量校验** | **3h** | T1.2 |
| T1.3 | **分段 prompt + schema（`complete`）+ 截断续跑** | 5h | T1.2b |
| T1.4 | 不分段降级模式（只读原文 + 结构可跑 + 重新分段入口） | 3h | T1.3 |
| T1.5 | **`exam_words` 表 + CSV 导入（先导中考考纲表）+ 查表回填服务** | 3h | T1.1 |
| T1.6 | 结构分析 prompt + schema | 3h | T1.3 |
| T1.7 | **逐句 prompt（考点字段 + 教师口吻规范）+ schema** | 5h | T1.3, T1.5 |
| T1.8 | dev 同步端点 + `scripts/smoke.sh` | 1h | T1.6, T1.7 |
| 评审点 | 3 篇常规 + 5 篇对抗样本；人工过 G9/G2/G3/G11/G13 | — | T1.8 |

### M2 · 任务化 + 阅读体验（第 2 周，约 3.5 人日）

| ID | 任务 | 估时 | 依赖 |
|---|---|---|---|
| T2.1 | `jobs`/`job_batches` + 执行器（阶段依赖、并发、续跑、失败批重跑） | 5h | T1.8 |
| T2.2 | `POST /analyses`(202) + `GET /jobs/{id}`（含 stages）+ `/events?since=` | 3h | T2.1 |
| T2.3 | 阶段级缓存 | 2h | T2.1 |
| T2.4 | JSON 修复重试 + 单句降级 + 错误码归一 | 2h | T1.8 |
| T2.5 | 静态站骨架 + 导入页（选等级、预估） | 3h | T2.2 |
| T2.6 | 阅读页：句子渲染、选中联动、考点词高亮（分级样式） | 5h | T2.5 |
| T2.7 | 四段式进度 + 结构面板 + 逐句面板 + 增量填充 | 5h | T2.6 |
| T2.8 | 历史列表 + 不分段模式 UI | 2h | T2.5 |

### M3 · 多语境对比 + 学习闭环（第 3–4 周，约 4 人日）

| ID | 任务 | 估时 | 依赖 |
|---|---|---|---|
| T3.1 | **多语境 prompt + schema + `word_profiles`/`word_senses` 落库** | 6h | T2.7 |
| T3.2 | **对比卡 UI + 词汇 Tab + 词卡浮层联动** | 5h | T3.1 |
| T3.3 | 生词入库（`lemma + sense_cn` 去重、来源句、批量加入） | 3h | T3.2 |
| T3.4 | py-fsrs 接入（初始卡、到期查询、评分更新） | 3h | T3.3 |
| T3.5 | 复习页（挖空、义项提示、四档评分） | 4h | T3.4 |
| T3.6 | 生词本列表（按词/义项、筛选、标记已掌握） | 2h | T3.4 |
| T3.7 | 测验生成 prompt + schema（三类题型） | 4h | T3.2 |
| T3.8 | 测验页（作答、判分、解析跳回原句） | 4h | T3.7 |
| T3.9 | 空/错/加载态、`←/→` 切句、暗色主题 | 3h | M2+M3 |

### M4 · 部署与多端准备（第 5 周，约 1.75 人日）

| ID | 任务 | 估时 | 依赖 |
|---|---|---|---|
| T4.1 | 认证 + 配额 + flask-limiter + 请求体限制 | 4h | M2 |
| T4.2 | 生产部署：gunicorn + Nginx + HTTPS + systemd（附 Dockerfile） | 2h | T2.8 |
| T4.3 | SQLite → PostgreSQL 迁移验证 + 词表导入脚本 | 2h | T4.2 |
| T4.4 | 验收 G1–G14，记录 `docs/ACCEPTANCE.md` | 3h | 全部 |
| T4.5 | `docs/API.md` + 小程序适配清单 | 3h | T4.1 |

**合计约 11.5 人日**。

### 每周节奏

- 周一/二写代码；周三跑真实文章看效果（优先用真题同源文章）；周四改 prompt；周五补测试；周末收尾。
- **改 prompt 必须 bump `prompt_version`**；分段 prompt 单独版本号。
- **每次改讲解类 prompt，必须重跑 G13 盲评**（否则"老师感"会悄悄退化）。

---

## 9. 目录结构

```
reading/
├─ docs/{PROJECT-PLAN.md, API.md, ACCEPTANCE.md, quality-log.md}
├─ data/
│  ├─ exam_words/
│  │  ├─ zhongkao_syllabus.csv    # 中考考纲约 1600 词（v1 先做）
│  │  ├─ gaokao_syllabus.csv      # 高考考纲 3500 词（后补）
│  │  └─ recent_exams.csv         # 近三年真题词频（可空，后补）
│  └─ app.db
├─ backend/
│  ├─ app/
│  │  ├─ __init__.py  config.py  extensions.py
│  │  ├─ api/v1/
│  │  │  ├─ auth.py  documents.py  jobs.py  sentences.py
│  │  │  ├─ words.py  vocab.py  review.py  quiz.py  settings.py
│  │  │  └─ errors.py
│  │  ├─ models/
│  │  ├─ schemas/
│  │  │  ├─ api.py
│  │  │  └─ llm/{segment.py, structure.py, sentence.py, polysemy.py, quiz.py}
│  │  ├─ services/
│  │  │  ├─ segmenter/{prompt.py, run.py}
│  │  │  ├─ analyst/{structure.py, sentences.py}
│  │  │  ├─ polysemy/{prompt.py, run.py}
│  │  │  ├─ examdict/{importer.py, lookup.py}
│  │  │  ├─ llm/{client.py, repair.py, cost.py}
│  │  │  ├─ jobs/{runner.py, cache.py}
│  │  │  ├─ review/fsrs.py
│  │  │  └─ quiz/generator.py
│  │  └─ prompts/{segment_v1.md, structure_v1.md, sentences_v1.md,
│  │              polysemy_v1.md, quiz_v1.md}
│  ├─ migrations/  tests/  wsgi.py  requirements.txt  .env.example
├─ web/
│  ├─ index.html read.html words.html vocab.html review.html quiz.html settings.html
│  ├─ css/{base.css, reader.css, wordcard.css, theme.css}
│  └─ js/{api.js, poller.js, dom.js, store.js, reader.js, words.js, review.js, quiz.js}
├─ scripts/{import_exam_words.py, smoke.sh, dev.ps1, deploy.sh}
```

`requirements.txt`：

```
flask
flask-limiter
sqlalchemy
alembic
psycopg[binary]
pydantic>=2
openai
tenacity
python-dotenv
fsrs
gunicorn
pytest  pytest-flask  vcrpy
```

`.env.example`（默认值即 v1 中考优先的配置）：

```
FLASK_ENV=development
SECRET_KEY=change-me
JWT_SECRET=change-me

DATABASE_URL=sqlite:///../data/app.db          # 生产: postgresql+psycopg://...
LLM_BASE_URL=https://api.openai.com/v1        # 可换 DeepSeek / 智谱 / Ollama
LLM_API_KEY=sk-...
LLM_MODEL_SEGMENT=gpt-4o-mini                 # 分段用便宜模型
LLM_MODEL_ANALYSIS=gpt-4o-mini
LLM_MODEL_VISION=gpt-4o-mini                  # 图片转写，必须是支持视觉的模型
LLM_MODEL_POLYSEMY=gpt-4o-mini
LLM_CONCURRENCY=3

TARGET_LEVEL=zhongkao                         # 默认中考；可选 gaokao
EXAM_TAG_SOURCE=table                         # table | model | off
MAX_DOC_CHARS=20000
MAX_IMAGE_MB=10                               # 单张图片大小上限
MAX_IMAGE_COUNT=5                             # 单篇最多几张图
DAILY_ANALYSIS_QUOTA=20
```

> `TARGET_LEVEL` 只是新建文档的默认值，用户在前端仍可切换；切换后选词阈值按对应考纲走。
> `EXAM_TAG_SOURCE=table` 时，若 `exam_words` 里查不到该词，**不显示任何真题/考纲标签**（宁缺勿假）。

---

## 10. 测试策略

| 层级 | 范围 | 手段 |
|---|---|---|
| 单元 | 词表查表回填（命中/未命中/多条）、费用换算、批次划分、`complete` 续跑循环 | `pytest`，纯函数，秒级 |
| 契约 | 各 Pydantic schema 对坏输出（缺字段/类型错/枚举越界）必须拒绝 | 固定非法样例表 |
| 集成 | 执行器：阶段依赖、并发、重试、续跑、失败批重跑、缓存命中 | `vcrpy` 离线跑 |
| 降级 | 非法返回 / `complete` 恒 false → 进入 `unsegmented`，不抛 500 | 构造假响应 |
| API 契约 | 端点状态码、`ok/data` 封装、`error.code` 稳定 | 防破坏小程序端 |
| **词表一致性** | 模型自报 `syllabus_guess` 与表回填冲突时，以表为准；记录冲突日志 | 单测 + 抽查 |
| **质量回归（人工）** | 3 篇 × 20 句逐字比对（G9）；考点词召回（G11）；对比卡准确度（G12）；讲解盲评（G13） | 记入 `docs/quality-log.md`，改 prompt 必做 |

**不做**：原文一致性自动校验、偏移合法性自动校验（沿用 v1.3 决定）。

---

## 11. 风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| **模型编造真题出处** | 用户误信"2024 考过"，备考被误导 | 默认只认 `exam_words` 表；查不到不显示年份；`exam_source` 字段可追溯 |
| **词表本身不权威** | 整个"对标真题"卖点失信 | 考纲词表用公开大纲；真题词表由人工整理并标注来源；词表版本化 |
| 模型改标点/漏句（系统无感知） | 文章残缺、偏移错位 | prompt 强约束 + 人工抽查 G9 + 一键重新分段 |
| 偏移错位 | 高亮偏、定位错 | 正文用 `sentences.text`；高亮只用句内偏移 |
| **多语境硬凑** | 把简单词解释成"多义"，误导学生 | prompt 要求"不足 3 组就少给"；G12 人工评审 |
| **讲解写成模板套话** | 产品失去"老师感" | prompt 给正反例；G13 盲评；每次改 prompt 必复评 |
| 异常文本永不通过 | 该文章无法精读 | 降级只读模式 + 反复重试；P1 加手动分段 |
| **图片识别错误（漏句/错词/串行）且系统无感知** | 用户对着一篇错文学习，比不做更糟 | 视觉 prompt 要求逐字符转写并如实报告 `complete`；**界面提供「查看识别出的原文」**；多页按顺序拼接；识别质量差时引导重拍 |
| 同文两次切法不同 | 复习卡指向错位 | 分段结果固化；重分段需确认 |
| Flask 同步请求超时 | 长文必失败 | 全部任务化，接口只回 `job_id` |
| 进程内线程池 + 多 worker | 任务重复执行 | 生产 `-w 1` 或上 Redis 队列 |
| 公网费用失控 | 真实损失 | 配额 + 限流 + 字符上限 + 预算告警 |
| 静态站 XSS | 安全漏洞 | 禁止 `innerHTML`；必须时 DOMPurify |
| 域名/HTTPS/备案 | 小程序无法上线 | P1 前置确认 |

---

## 12. 后续迭代

### P1 · 微信小程序（约 4–6 人日）

| 事项 | 说明 |
|---|---|
| 登录 | `wx.login` → `POST /auth/wechat`（`code2session` 换 openid） |
| 渲染 | `<rich-text nodes>`：用句内偏移把 `text` 切成 `text`/`span` 节点 |
| 进度 | 复用 `/jobs/{id}` 轮询（2s，15s 超时内） |
| 存储 | `wx.setStorageSync('token')`，401 静默续期 |
| 上传 | `wx.chooseMessageFile` + `wx.uploadFile` |
| 域名 | 微信后台配置合法域名，必须 HTTPS |

**上线自查**：无 Cookie、无 SSE、返回体不含 HTML、静态资源为绝对 HTTPS URL。

### P1 · 备考增强
- **词表维护台**：后台导入/编辑 `exam_words`，支持按年份、卷别筛选。
- **错题本**：测验错题自动归集，按语法点/词汇类型统计薄弱项。
- **学习报告**：每周统计"新学词数 / 复习留存率 / 各类题型正确率"。
- 手动分段粘贴（极端文本兜底）、PDF/DOCX 解析、朗读、**拍照自动裁边与纠偏（交给模型/前端，不做本地图像处理）**。

### P2
- 跨文章词频："这个词你在 3 篇文章里见过"。
- 按考纲生成专项练习（不规则动词、虚拟语气等）。
- 导出 Anki / 欧路词典（带义项）。

---

## 13. 立刻可执行的第一步

1. **先解决数据（只做中考这一份）**：整理 `zhongkao_syllabus.csv`（约 1600 词，列：`lemma,pos,level,band,senses`）。公开的义务教育课程标准词汇表可直接作为初始数据，`band` 先按"课标要求掌握/理解"两档粗分即可。
   - 真题词表 `recent_exams.csv` **v1 允许为空**，接口与 UI 已按"无年份标签"设计，补齐后重新导入即生效。
   - **词表是"对标真题"的根**：没有它，这个定位就是空的；但也别为了凑数据编造年份卷别。
2. 建 venv：`pip install flask sqlalchemy alembic pydantic openai tenacity python-dotenv`
3. 写 `segment_v1.md`，3 篇常规 + 5 篇对抗样本人工比对（G9）。
4. 写 `sentences_v1.md`，重点打磨**教师口吻**与**考点字段**；拿 10 句做 G13 盲评。
5. 写 `polysemy_v1.md`，拿一篇含明显多义词的文章验证 G12。
6. 最后才做任务化与前端。

**顺序不能反**：词表 → 讲解质量 → 多语境质量 → 工程。前三步不达标，界面做得再好也不是"老师"。
