# LinkSell - 智能销售助手

LinkSell 是一个全能的销售数据采集与分析系统。它集成了**火山引擎语音识别 (Seed ASR)** 和 **豆包大模型 (Doubao LLM)**，旨在将碎片化的销售对话、会议录音高效转换为结构化的商业洞察。

## ✨ 核心功能

*   **🖼️ 现代化图形界面 (GUI)**：默认提供基于 Streamlit 的聊天式网页界面，支持交互式补全、流式报表显示及一键保存。
*   **💻 极客命令行模式 (CLI)**：通过 `--cli` 参数，在终端享受极速的 Rich 文本交互。
*   **🎙️ 智能语音转写**：基于 Seed ASR 大模型，精准识别商务沟通，支持文件上传与录音。
*   **✨ 文本润色与格式化**：自动剔除口语赘余，生成专业书面记录。
*   **🤖 秘书级交互体验**：全语料库驱动，提供专业、温婉的智能助理反馈。
*   **📝 对话式修订**：支持用自然语言直接下达修改指令，彻底告别 JSON 手动编辑。

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
2. 填入您的火山引擎 AK/SK、ASR Token 以及豆包大模型的 API Key 与 Endpoint ID。

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
├── data/               # 本地数据库 (JSON) 及附件存储
├── src/
│   ├── core/           # 核心控制器 (Controller) - 逻辑大脑
│   ├── cli/            # 终端界面实现 (View - CLI)
│   ├── gui/            # Web 界面实现 (View - GUI)
│   ├── services/       # API 接入层 (ASR, LLM)
│   └── main.py         # 路由分流入口
└── requirements.txt
```

## 💾 数据存储
*   **主库**: `data/sales_data.json`
*   **独立记录**: `data/records/项目名-时间戳.json`

## 🤝 贡献与支持
如有任何问题，欢迎提交 Issue。