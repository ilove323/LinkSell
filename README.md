# LinkSell - 智能销售助手

LinkSell 是一个全能的销售数据采集与分析系统。它集成了**火山引擎语音识别 (Seed ASR)** 和 **豆包大模型 (Doubao LLM)**，旨在将碎片化的销售对话、会议录音高效转换为结构化的商业洞察。

## ✨ 核心功能

*   **🖼️ 现代化图形界面 (GUI)**：默认提供基于 Streamlit 的聊天式网页界面，支持**对话式整理**、**实时报表反馈**及**一键归档**。
*   **💻 极客命令行模式 (CLI)**：通过 `--cli` 参数，可在终端执行高效的分析与批处理。
*   **🎙️ 智能语音转写**：采用大模型 ASR 技术，精准识别口语，支持麦克风录制或文件上传。
*   **✨ 文本润色与格式化**：在分析前自动去除赘余口语，将内容转化为标准、专业的商务书面文本。
*   **🤖 秘书级交互体验**：内置丰富的随机语料库，系统反馈更具“人情味”，告别冰冷的机器指令。
*   **📝 对话式修订**：支持使用自然语言直接修改分析结果，无需手动调整 JSON 数据。

## 🚀 快速开始

### 1. 环境准备
请确保您的环境已安装 Python 3.8 或更高版本。

```bash
# 克隆项目
cd LinkSell

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置密钥
1. 将 `config/config.ini.template` 复制为 `config/config.ini`。
2. 填入您的火山引擎 AK/SK、ASR Token 以及豆包大模型的 API Key 与 Endpoint ID。

## 3. 使用指南 (Usage)

### 模式一：启动图形化界面 (推荐)
直接运行以下命令，系统将在浏览器中打开一个“智能秘书”聊天窗口：
```bash
python src/main.py analyze
```
*   **交互流程**：
    1.  点击输入框上方的 **“➕ 语音/文件”** 按钮上传录音或直接说话。
    2.  或直接在对话框输入文字。
    3.  系统会自动分析并生成 **“销售小纪”** 报表。
    4.  若有缺失信息，秘书会追问补充，报表实时更新。
    5.  确认无误后，点击 **“✅ 确认保存”** 按钮一键归档。

### 模式二：命令行模式 (CLI)
适合在终端快速操作或进行脚本集成：
```bash
# 启动交互式 CLI
python src/main.py analyze --cli

# 直接分析指定文本
python src/main.py analyze --cli --content "今天聊了个大单子..."
```

## 📁 目录结构
```text
LinkSell/
├── config/             # 配置文件、系统 Prompt 及 UI 语料库
├── data/               # 本地 JSON 数据库及录音备份
├── src/
│   ├── core/           # 核心控制器 (Controller) - 业务逻辑大脑
│   ├── gui/            # Streamlit 界面实现 - 现代化交互层
│   ├── services/       # ASR 与 LLM 底层服务 - API 接入层
│   └── main.py         # 系统入口
└── requirements.txt    # 依赖清单
```

## 💾 数据存储
LinkSell 坚持**本地优先**原则：
*   **数据库**: `data/sales_data.json`。
*   **独立备份**: 每次保存均会在 `data/records/` 生成以项目名命名的独立 JSON 文件。

## 🤝 贡献与支持
如有任何问题或建议，欢迎提交 Issue。
