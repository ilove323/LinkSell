# LinkSell - 智能销售助手 (v2.4 工业级版本)

LinkSell 是一款专为销售人员打造的高效数据采集、分析与商机管理工具。它通过 **“语音输入 + AI 结构化 + 自动化建档”** 的闭环逻辑，将凌乱的沟通内容转化为极具商业价值的数字化资产。

---

## 💎 为什么选择 LinkSell？

在传统的销售工作中，记录客户需求和更新商机往往是一项沉重的负担。LinkSell 通过以下技术突破解决了这一痛点：
- **零负担录入**：支持 Seed ASR 语音识别，随口一说即可完成复杂的商机登记。
- **数据洁癖**：内置 **“四重输入规范化”** 体系，确保入库数据标准、统一、无噪音。
- **精准定位**：结合关键词与语义向量搜索，无论数据量多大，都能瞬间找到目标商机。
- **物理化隔离**：采用“一商机一文件”架构，确保数据安全、易于备份且支持大规模并发扩展。

---

## 🛠️ 核心架构 (MVC Pattern)

LinkSell 严格遵循 **MVC 架构设计**，确保了代码的可维护性与扩展性：

- **Model (数据层)**：存储于 `data/opportunities/` 下的独立 JSON 文件，及 `data/vector_db/` 中的向量索引。
- **View (视图层)**：
    - **CLI (`interface.py`)**：基于 Rich 库的交互式终端。
    - **GUI (`app.py`)**：基于 Streamlit 的响应式 Web 界面。
- **Controller (业务逻辑层)**：核心控制器 `controller.py`，封装了所有的 AI 调度、数据清洗与文件管理逻辑。

---

## 🧠 输入规范化体系 (The Processing Pipeline)

这是 LinkSell 2.4 的核心灵魂，通过专门调教的 Prompt 确保人机交互的严丝合缝：

1.  **意图分流与内容提取 (Intent Classifier + Content Extractor)**：
    - **关键词**: `classify_intent.txt`
    - **作用**: **一步到位**判断用户是想 **CREATE**(新建), **LIST**(列表), **GET**(详情), **UPDATE**(修改), **DELETE**(删除)，同时从输入中提取业务相关内容。
    - **输出格式**: JSON 格式 `{"intent": "CREATE", "content": "具体的业务内容"}`，内容已去掉意图关键词
    - **例子**: "把轴承厂的预算改成80万" → `{"intent": "UPDATE", "content": "轴承厂的预算改成80万"}`
2.  **填空规范化 (Input Formatter)**：
    - **关键词**: `normalize_input.txt`
    - **作用**: 将"五十个达不溜"转化为"50万"，并识别"不知道/跳过"等无效意图并转为 `NULL`。
3.  **布尔判官 (Boolean Judge)**：
    - **关键词**: `judge_save.txt`
    - **作用**: 听懂一切肯定或否定的潜台词（如"改了吧"、"算了"、"确认"）。
4.  **补充分析 (Analysis & Enhancement)**：
    - **关键词**: `analyze_sales.txt`, `update_sales.txt`, `polish_text.txt`
    - **作用**: 对结构化数据进行深度分析、自然语言驱动更新和文本润色。

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
│   ├── cli/interface.py   # [视图] 命令行交互逻辑
│   ├── gui/app.py         # [视图] Web 图形界面
│   └── services/          # [服务] ASR、LLM、VectorDB 封装
└── main.py                # 入口程序
```

---

## 💾 数据存储规范

- **单文件逻辑**：每个商机对应一个文件，如 `data/opportunities/沈阳轴承厂.json`。
- **元数据继承**：在修改商机时，系统会自动继承 `id`, `created_at`, `record_logs` 等元数据，确保记录的连续性。
- **文件重命名**：若在编辑时修改了项目名称，系统会自动执行 **“新建新文件 + 迁移数据 + 删除旧文件”** 的原子操作。

---

## 🤝 参与开发
我们欢迎任何形式的贡献！请在提交 PR 前确保您已阅读并理解 `AI_README.md`。
