# LinkSell - 智能销售助手

LinkSell 是一个全能的销售数据采集与分析系统。它集成了**火山引擎语音识别 (Seed ASR)** 和 **豆包大模型 (Doubao LLM)**，旨在将碎片化的销售对话、会议录音高效转换为结构化的商业洞察。

## ✨ 核心功能

*   **📂 商机聚合档案 (CRM)**：系统以“项目名”为唯一索引，自动聚合所有相关的销售小记。支持历史笔记追加，实现单一商机全生命周期的记录追踪。
*   **🧑‍💻 责任人记录志**：每一条存档记录均自动标记**录入时间**与**记录者**（默认：陈一骏），确保持久化数据的可追溯性。
*   **🔍 本地 RAG 语义搜索**：内置本地 Embedding 引擎与向量数据库（ChromaDB）。支持“张三去年谈了哪些项目？”等自然语言查询，数据隐私不出本地。
*   **🧠 智能意图识别**：自动分流“录音分析”与“历史查询”需求，甚至能读懂您的保存与修改意图。
*   **📝 智能摘要提炼**：针对长会议记录（>500字），系统自动触发 AI 提炼，确保商机档案精简高效，保留核心商业价值。
*   **📈 数字化阶段管理**：商机阶段采用 1-4 数字化管理，在 `config.ini` 中灵活映射为（P1 需求确认 ... P4 签订合同），支持强制查漏补缺。
*   **🎙️ 强化版 ASR 识别**：基于 Seed ASR，支持长语音轮询及静音/低音量异常提醒。

## 🚀 快速开始

### 1. 环境准备
```bash
cd LinkSell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置密钥
1. 将 `config/config.ini.template` 复制为 `config/config.ini`。
2. 填入您的火山引擎密钥及豆包模型参数。
3. **个性化配置**：在 `[global]` 中修改 `default_recorder` (默认记录者) 及 `hf_endpoint` (国内镜像站)。

## 3. 使用指南 (Usage)

### 模式一：图形化界面 (推荐)
```bash
python src/main.py analyze
```
系统将自动打开浏览器。您可以使用底栏的 **“➕”** 按钮进行语音输入，并直接在对话框中下达指令。确认无误后点击 **“✅ 确认保存”**。

### 模式二：命令行模式 (CLI)
```bash
# 启动交互式 CLI
python src/main.py analyze --cli

# 分析指定文本
python src/main.py analyze --cli --content "对话文本..."
```

## 📁 目录结构
```text
LinkSell/
├── config/             # 配置文件、Prompt 模板、UI 语料库
├── data/               # 本地数据库 (JSON)、向量库及附件存储
├── assets/             # 静态资源 (Icon等)
├── src/
│   ├── core/           # 核心控制器 (Controller) - 逻辑大脑
│   ├── cli/            # 终端界面实现 (View - CLI)
│   ├── gui/            # Web 界面实现 (View - GUI)
│   ├── services/       # API 接入层 (ASR, LLM, Vector)
│   └── main.py         # 路由分流入口
└── requirements.txt
```

## 💾 数据存储
*   **CRM 主库**: `data/sales_data.json` (商机聚合格式)
*   **向量索引**: `data/vector_db/` (ChromaDB 本地存储)
*   **归档备份**: `data/records/` (原始记录 JSON 备份)

## 🤝 贡献与支持
如有任何问题，欢迎提交 Issue。
