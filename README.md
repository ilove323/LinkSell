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

## 🤝 参与开发
我们欢迎任何形式的贡献！请在提交 PR 前确保您已阅读并理解 `AI_README.md`。