# LinkSell - 智能销售助手 (v2.5 工业级版本)

LinkSell 是一款专为销售人员打造的高效数据采集、分析与商机管理工具。它通过 **“语音输入 + AI 结构化 + 自动化建档”** 的闭环逻辑，将凌乱的沟通内容转化为极具商业价值的数字化资产。

---

## 💎 为什么选择 LinkSell？

在传统的销售工作中，记录客户需求和更新商机往往是一项沉重的负担。LinkSell 通过以下技术突破解决了这一痛点：
- **零负担录入**：支持 Seed ASR 语音识别，随口一说即可完成复杂的商机登记。
- **数据洁癖**：内置 **“四重输入规范化”** 体系，确保入库数据标准、统一、无噪音。
- **精准定位**：结合关键词与语义向量搜索，支持 **真实 ID 锁定**，拒绝模糊操作。
- **上下文记忆**：支持 **"查看(GET) -> 修改(UPDATE)"** 的连贯操作，系统自动记住当前商机，无需重复指令。
- **物理化隔离**：采用“一商机一文件”架构，确保数据安全、易于备份且支持大规模并发扩展。

---

## 🛠️ 核心架构 (MVC Pattern)

LinkSell 严格遵循 **MVC 架构设计**，确保了代码的可维护性与扩展性：

- **Model (数据层)**：存储于 `data/opportunities/` 下的独立 JSON 文件，及 `data/vector_db/` 中的向量索引。
- **View (视图层)**：
    - **CLI (`interface.py`)**：基于 Rich 库的交互式终端，支持上下文状态管理。
    - **GUI (`app.py`)**：基于 Streamlit 的响应式 Web 界面。
- **Controller (业务逻辑层)**：核心控制器 `controller.py`，封装了所有的 AI 调度、数据清洗与文件管理逻辑。

---

## 🧠 交互流程 (The Workflow)

LinkSell 2.5 采用了更加符合人类直觉的交互逻辑：

1.  **意图分流 (Intent Dispatcher)**：
    - **CREATE**: "录入沈阳机床厂的商机..." → 自动检测重复，支持直接 ID 关联或新建。
    - **GET**: "查看沈阳机床厂" → **静默锁定**当前商机 ID。
    - **UPDATE**: "把预算改成80万" → **自动识别**上下文，直接修改刚才锁定的商机。
    - **LIST**: "列出所有项目" 或 "查找轴承相关的" → 展示列表与真实 ID。
    - **DELETE**: "删除这个项目" → 需二次确认。

2.  **硬核 ID 系统**:
    - 废除模糊的 "序号选择 (1, 2, 3)"。
    - 全面采用 **真实 ID** (Timestamp) 进行精准锚定。
    - 列表展示直观，操作指哪打哪。

3.  **冲突检测与小记追加**:
    - **关键字段冲突**（如预算、阶段）：系统弹出对比提示，询问是否覆盖。
    - **日常小记**（Follow-up）：直接追加到历史记录，零干扰。

---

## 🚀 快速上手

### 1. 安装环境
```bash
git clone https://github.com/laurant/LinkSell.git
cd LinkSell
python3 -m venv .venv
source .venv/bin/activate
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
│   ├── core/controller.py # [核心] 业务逻辑控制器
│   ├── cli/interface.py   # [视图] 命令行交互逻辑 (含状态机)
│   ├── gui/app.py         # [视图] Web 图形界面
│   └── services/          # [服务] ASR、LLM、VectorDB 封装
└── main.py                # 入口程序
```

---

## 🤝 参与开发
我们欢迎任何形式的贡献！请在提交 PR 前确保您已阅读并理解 `AI_README.md`。