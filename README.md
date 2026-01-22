# LinkSell - AI 销售商机助手

LinkSell 是一个**本地优先 (Local-First)** 的智能销售管理工具。它不像传统的 CRM 那样只是个填表工具，而是一个能听懂人话、能帮你分析商机、能自动整理笔记的 **"AI 销售秘书"**。

## 🚀 核心功能
1. **🗣️ 语音/自然语言录入**: 
   - 就像发微信语音一样简单。
   - "刚刚跟王总聊完，他们打算下个月上系统，预算50万。" -> 系统自动提取字段。
2. **📂 自动归档与合并**: 
   - 自动判断是新商机还是老商机。
   - 自动将新笔记追加到老商机的历史记录中。
3. **🔍 语义搜索**: 
   - 甚至不记得项目名也没关系，搜 "上次那个预算50万的单子"，也能找到。
   - 采用 ChromaDB 本地向量库，精准命中。
4. **📊 结构化数据管理**:
   - 自动提取：项目名称、客户信息、预算、阶段、时间节点、竞争对手、待办事项等。
   - 本地 JSON 存储，数据完全掌握在你手里。

---

## 💎 为什么选择 LinkSell？

在传统的销售工作中，记录客户需求和更新商机往往是一项沉重的负担。LinkSell 通过以下技术突破解决了这一痛点：
- **零负担录入**：支持 Seed ASR 语音识别，随口一说即可完成复杂的商机登记。
- **数据洁癖**：内置 **“四重输入规范化”** 体系，确保入库数据标准、统一、无噪音。
- **精准定位**：结合关键词与语义向量搜索，支持 **真实 ID 锁定**，拒绝模糊操作。
- **上下文记忆**：支持 **"查看(GET) → 修改(REPLACE)"** 的连贯操作，系统自动记住当前商机，无需重复指令。
- **物理化隔离**：采用“一商机一文件”架构，确保数据安全、易于备份且支持大规模并发扩展。

---

## 🛠️ 核心架构 (MVC Pattern)

LinkSell 严格遵循 **MVC 架构设计**，确保了代码的可维护性与扩展性：

- **Model (数据层)**：存储于 `data/opportunities/` 下的独立 JSON 文件，及 `data/vector_db/` 中的向量索引。
- **View (视图层)**：
    - **GUI (`src/gui/gui.py`)**：基于 Streamlit 的无状态渲染层，只负责展示 Engine 返回的消息与数据。
    - **CLI (`src/cli/cli.py`)**：基于 Rich 库的交互式终端。
- **Controller (业务逻辑层)**：
    - **Conversational Engine (`conversational_engine.py`)**：**核心大脑**。维护会话状态（Context）、处理意图路由、生成最终回复话术。
    - **LinkSell Controller (`controller.py`)**：底层功能库。封装 AI 调用、文件 I/O、数据清洗等原子操作。

---

## 🧠 交互流程 (The Workflow v3.1)

LinkSell 3.1 引入了精确的语义操作（REPLACE/MERGE）区分机制：

1.  **意图分流 (Intent Dispatcher)**：
    - **RECORD**: "今天跟张总聊了沈阳机床项目，预算50万..." → **暂存笔记**。系统会自动对内容进行润色并存入暂存区，支持多次连续追加。
    - **CREATE**: "把刚才这些存入沈阳机床项目" → **正式建档/更新**。系统根据暂存笔记进行深度结构化分析，自动判别新旧项目，并生成最终草稿。
    - **GET**: "查看沈阳机床厂" → **静默锁定**当前商机 ID。
    - **REPLACE**: "把预算改成80万" → **字段级精准修改**。对已锁定的商机进行特定字段的自然语言修改（修改字段值）。
    - **MERGE**: "保存" → **追加笔记记录**。将暂存的笔记追加到商机的跟进记录（record_logs）中，不修改其他字段。
    - **LIST**: "列出所有项目" → 展示列表与真实 ID。
    - **DELETE**: "删除这个项目" → 需二次确认。

2.  **销售架构师 (Sales Architect Engine)**:
    - 采用融合版 AI 引擎，一次性完成“结构化提取 + 智能质检 + 新旧合并”。
    - 自动识别“口水话”，将其转化为工业级标准的销售数据。

3.  **保存确认**:
    - 草稿生成后，系统采用 **立即保存模式 (Auto-Save)**，数据将直接入库并实时反馈结果，无需繁琐的二次确认步骤，主打一个“快”字。

---

## 🚀 快速上手

### 1. 安装环境
```bash
git clone https://github.com/laurant/LinkSell.git
cd LinkSell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 初始化与配置
- 复制 `config/config.ini.template` 为 `config.ini` 并填写火山引擎 API 密钥。
- 执行初始化命令：`python src/main.py init`

### 3. 使用模式
- **智能分析/录入/查询 (CLI)**：`python src/main.py analyze --cli`
- **图形化操作 (GUI)**：`python src/main.py analyze`
- **后台管理 (Manage)**：`python src/main.py manage`

---

## 📁 目录结构说明

```text
LinkSell/
├── config/
│   ├── prompts/           # AI 的“灵魂”：所有的提示词模板
│   └── ui_templates.json  # 秘书的“口语”：随机化的交互语料
├── data/
│   ├── opportunities/     # [重要] 所有的商机 JSON 档案
│   └── vector_db/         # [重要] 向量索引库
├── src/
│   ├── core/
│   │   ├── conversational_engine.py # [核心] 会话状态机与路由引擎
│   │   └── controller.py            # [底层] 业务逻辑控制器
│   ├── cli/cli.py         # [视图] 命令行交互逻辑
│   ├── gui/gui.py         # [视图] Web 图形界面
│   └── services/          # [服务] ASR、LLM、VectorDB 封装
└── main.py                # 入口程序
```

---

## 🧠 AI 提示词体系 (Prompt Templates)

LinkSell 采用**八层结构化提示词体系**，精确控制 AI 在各个业务环节的行为。所有提示词存储在 `config/prompts/` 目录下：

### 📋 完整的 Prompt 使用清单

| # | 文件名 | 调用时机 | 调用函数 | 核心功能 |
|---|--------|--------|---------|---------|
| 1️⃣ | **classify_intent.txt** | 用户输入时 | `controller.identify_intent()` | 意图识别：RECORD/CREATE/LIST/GET/REPLACE/MERGE/DELETE/OTHER |
| 2️⃣ | **polish_text.txt** | RECORD 阶段 | `controller.polish()` | 文本润色：口语→书面语（去除"那个"、"嗯"等） |
| 3️⃣ | **sales_architect.txt** | CREATE/MERGE 阶段 | `llm_service.architect_analyze()` | 结构化解析：生成 JSON + 提炼小记（`current_log_entry`） |
| 4️⃣ | **extract_search_term.txt** | GET/LIST/REPLACE 阶段 | `controller.extract_search_term()` | 关键词提取：从模糊指令中精准抽取搜索词 |
| 5️⃣ | **query_sales.txt** | RAG 查询时 | `llm_service.query_sales_data()` | 知识库问答：基于向量搜索的结果进行专业分析 |
| 6️⃣ | **summarize_note.txt** | 长笔记备选方案 | `llm_service.summarize_text()` | 摘要提炼：将 >500 字长文本精炼为小记 |
| 7️⃣ | **judge_save.txt** | 确认操作时 | `llm_service.judge_affirmative()` | 意图判断：判断用户的"是/否"回答 |
| 8️⃣ | **delete_confirmation.txt** | DELETE 前 | 业务逻辑预留 | 删除确认：生成二次确认提示（当前未激活） |

### 🔄 完整的数据流向

```
用户输入 (文本/语音)
    ↓
① classify_intent.txt → 意图识别 (RECORD/CREATE/LIST/...)
    ↓
    ├─ RECORD 路径：
    │   ├─ ② polish_text.txt → 文本润色
    │   └─ 笔记缓存（暂存不保存）
    │
    ├─ CREATE/MERGE 路径：
    │   ├─ ③ sales_architect.txt → 结构化提取 + 小记生成
    │   ├─ ⑥ summarize_note.txt → 可选（笔记过长时）
    │   └─ JSON 保存到 data/opportunities/{项目名}.json
    │
    ├─ GET/LIST/REPLACE 路径：
    │   ├─ ④ extract_search_term.txt → 关键词提取
    │   └─ 调用向量库 + 模糊匹配
    │
    ├─ RAG 查询路径：
    │   ├─ ④ extract_search_term.txt → 关键词提取
    │   └─ ⑤ query_sales.txt → 基于搜索结果的问答
    │
    └─ DELETE 路径：
        ├─ ⑦ judge_save.txt → 确认删除
        └─ ⑧ delete_confirmation.txt → 生成确认提示

```

### 📍 各个阶段的 Prompt 调用

#### **阶段 1：意图识别** (`classify_intent.txt`)
```
使用场景：每次用户输入时立即调用
输入：用户原始输入文本
输出：{"intent": "RECORD/CREATE/...", "content": "处理后的内容"}
关键意图定义：
  - RECORD: 提供笔记（不保存）
  - CREATE: 明确要求保存/新建
  - GET: 查看单个商机详情
  - REPLACE: 修改商机信息
  - MERGE: "保存" - 追加笔记到商机
  - LIST: 列出多个商机
  - DELETE: 删除商机
  - OTHER: 闲聊
```

#### **阶段 2：文本润色** (`polish_text.txt`)
```
使用场景：当意图为 RECORD 时
调用链：handle_record() → controller.add_to_note_buffer() → controller.polish()
功能：口语转书面语（去除"那个"、"嗯"、"啊"）
输出：润色后的文本（直接存入 note_buffer）
示例：
  输入：  "那个，今天嗯，跟王总聊了一下那个轴承的事儿..."
  输出：  "今天与王总沟通了轴承项目的相关事宜。"
```

#### **阶段 3：结构化解析** (`sales_architect.txt`) ⭐ 核心
```
使用场景：CREATE/MERGE 时（笔记最终保存前）
调用链：handle_save() → controller.merge() → llm_service.architect_analyze()
功能：
  1. 解析笔记内容，提取商机结构化字段
  2. 生成 current_log_entry（50-100字小记）← 最终保存的小记！
  3. 识别商机阶段（1-4 数字）
  4. 提取客户信息、预算、竞争对手等
输出：完整的结构化 JSON
关键字段：
  - current_log_entry: "本次沟通精华摘要（这个会被保存到 record_logs）"
  - opportunity_stage: 1-4 数字
  - project_opportunity: {...} (内层结构)
```

#### **阶段 4：关键词提取** (`extract_search_term.txt`)
```
使用场景：GET/LIST/REPLACE 时需要定位商机
调用链：controller.resolve_target_interactive() → controller.extract_search_term()
功能：从模糊指令中精准抽取搜索关键词
规则：
  - 具体名称 → 提取（如"沈阳轴承厂"）
  - 泛指（"看看有什么"） → 返回 "ALL"
  - 听不懂 → 返回 "Unknown"
示例：
  "有哪些商机？" → ALL
  "看看沈阳轴承项目" → 沈阳轴承
  "最近那个50万的单子" → 50万
```

#### **阶段 5：RAG 问答** (`query_sales.txt`)
```
使用场景：用户提出与历史商机相关的问题
调用链：controller.query_knowledge_base() → llm_service.query_sales_data()
功能：基于向量搜索的历史数据进行专业问答
输入：
  - context: 向量搜索相关的商机历史记录
  - query: 用户的问题
输出：基于现有数据的专业分析回答
示例：
  用户问："最近的轴承订单进度如何？"
  系统：搜索 → query_sales.txt → 结合历史数据生成回答
```

#### **阶段 6：长文本摘要** (`summarize_note.txt`)
```
使用场景：笔记 >500 字且未生成 current_log_entry 时
调用链：controller.save() → llm_service.summarize_text()
功能：将冗长的会议记录精炼为 ≤500 字小记
触发条件：final_log_content 为 None 且原文 >500 字
示例：
  输入：完整的 3000 字会议记录
  输出：精炼的 300 字小记
```

#### **阶段 7：确认判断** (`judge_save.txt`)
```
使用场景：系统向用户提出是非题时
调用链：（交互式操作中）→ llm_service.judge_affirmative()
功能：判断用户的 "是/否" 回答是否表示同意
规则：
  肯定：好、可以、没问题、嗯、妥、是、OK → TRUE
  否定：不、否、别、取消、No、算了 → FALSE
输出：TRUE 或 FALSE
```

#### **阶段 8：删除确认** (`delete_confirmation.txt`)
```
使用场景：DELETE 操作前（当前预留）
功能：生成友好但严肃的删除确认提示
输入：要删除的商机 JSON
输出：中文的确认提示语
状态：功能完成但未在 CLI/GUI 中激活，可在后续需要时启用
```

### 🔗 调用关系速查表

```
classify_intent.txt
  ├─→ RECORD → polish_text.txt
  ├─→ CREATE/MERGE → sales_architect.txt
  │                  └─→ (可选) summarize_note.txt
  ├─→ GET/LIST/REPLACE → extract_search_term.txt
  │                        └─→ (RAG) query_sales.txt
  ├─→ MERGE → sales_architect.txt
  ├─→ DELETE → (预留) delete_confirmation.txt
  └─→ OTHER → （无额外 Prompt）
```

### 💡 Prompt 优化建议

1. **sales_architect.txt** 是系统的核心，决定了数据结构化的质量。后续可针对特定行业（房产、IT 等）定制专项版本。
2. **polish_text.txt** 可扩展支持多语言（英文、日文）。
3. **extract_search_term.txt** 的规则库可动态加载，支持自定义关键词映射。
4. **query_sales.txt** 可增加 Few-Shot 学习，基于历史问答对进行精准调优。

---

## 🤝 参与开发
我们欢迎任何形式的贡献！请在提交 PR 前确保您已阅读并理解 `AI_README.md`。