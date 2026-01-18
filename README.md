# LinkSell - 销售神器 CLI 版

LinkSell 是一个专为销售团队打造的命令行工具（CLI）。它集成了**火山引擎语音识别**和**豆包大模型**，旨在将碎片化的销售对话和正式的会议纪要，高效地转换为结构化销售数据，并自动存入本地数据库。

## ✨ 核心功能

*   **🧠 智能提炼 (已就绪)**：接入豆包大模型，自动识别内容类型，深度提取客户画像、项目商机、技术栈及待办事项。
*   **📂 本地安全存储 (已就绪)**：数据以 JSON 格式保存在本地，确保数据隐私与安全。
*   **⚙️ 灵活配置 (已就绪)**：通过标准化的 `config.ini` 文件管理 API 密钥与系统提示词（Prompts）。
*   **🎙️ 语音转写 (开发中)**：计划集成火山引擎 ASR，未来支持录音文件直接转文字（目前 `record` 命令仅为占位符）。

## 🚀 快速开始

### 1. 环境准备
请确保您的环境已安装 Python 3.8 或更高版本。

```bash
# 克隆项目（假设您已完成克隆）
cd LinkSell

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows 用户请使用 .venv\Scripts\activate

# 安装依赖 (已包含 pydantic)
pip install -r requirements.txt
```

### 2. 配置密钥
请将 `config/config.ini.template` 复制为 `config/config.ini`，并填入您的火山引擎 Access Key (AK)、Secret Key (SK) 及豆包大模型 API Key 和 Endpoint ID。

### 2.3 语音识别配置 (ASR)
若需使用语音转写功能，需在火山引擎控制台开通语音技术服务（ASR）。
本项目采用 **大模型语音识别服务 (Big Model ASR)**，需配置 Access Token 而非 AK/SK。

在 `config/config.ini` 中填入 AppID 及 Access Token：
```ini
[volcengine]
access_key = AK...
secret_key = SK...

[asr]
app_id = 12345678
access_token = YOUR_ACCESS_TOKEN_HERE
resource_id = volc.bigasr.auc
cluster = volcengine_input_common
```
*注意：`resource_id` 必须为 `volc.bigasr.auc`，请勿修改。**   `config/prompts/*.txt`: 存放 AI 系统提示词（Prompt）。
*   `config/ui_templates.json`: 存放 CLI 界面交互的文本模板（如“秘书”风格的提示语），支持自定义。

## 3. 使用指南 (Usage)

### 初始化
首次运行前，请执行初始化命令以创建必要的数据文件：
```bash
python src/main.py init
```

### 核心功能：销售分析 (Analyze)
支持**文本粘贴**和**语音文件**两种输入方式。

#### 方式一：文本分析
直接分析文本内容，支持交互式输入或命令行参数：
```bash
# 交互式输入（推荐）
python src/main.py analyze

# 命令行直接输入
python src/main.py analyze --content "今天跟张总聊了一下，他对我们的SaaS平台很感兴趣，预算大概50万..."
```

#### 方式二：语音分析 (新增)
指定录音文件路径，系统将自动转写并进行分析：
```bash
python src/main.py analyze --audio "/Users/laurant/Downloads/meeting_recording.mp3"
```
*注：目前支持 wav, mp3 等常见音频格式，建议使用时长在 60 秒以内的短语音进行测试。*

#### 方式三：麦克风直接录音 (Direct Microphone)
直接通过麦克风录制语音，按回车键停止录音并立即开始分析：
```bash
python src/main.py analyze --microphone
```
*注：需确保终端具有麦克风访问权限。*

### 智能数据补全 (Smart Completion)
系统在分析过程中会自动检测商机关键信息（如预算、时间节点、竞争对手等）是否缺失。
若检测到缺失，系统将启动交互式补全流程，引导用户补充相关信息。用户输入的非结构化补充信息将通过 AI 再次清洗并合并至最终记录中，确保数据的完整性与规范性。

### 交互式编辑
分析完成后，系统将展示结构化报表。您可以：
*   输入 `s`: 确认并保存。
*   输入 `e`: 调用系统默认编辑器（如 Vim, Notepad）手动修正 AI 提取的结果。
*   输入 `d`: 丢弃本次结果。

## 📁 目录结构说明
```text
LinkSell/
├── config/             # 配置文件 (ini) 和 AI 提示词 (txt)
├── data/               # 数据存储目录（JSON 数据文件及录音文件）
├── src/                # 源代码目录
│   ├── services/       # 业务逻辑服务层 (AI 处理, ASR 识别)
│   └── main.py         # CLI 应用程序入口
└── .venv/              # Python 虚拟环境目录
```

## 💾 数据存储说明
LinkSell 目前采用**本地 JSON 文件**作为轻量级数据库。
*   **默认位置**: `data/sales_data.json`（可在 `config.ini` 中修改）。
*   **数据安全**: 所有数据均存储在您的本地磁盘，不上传至任何第三方云端（除 AI 分析过程中的临时传输）。
*   **格式**: 这是一个标准的 JSON 数组，您可以随时使用文本编辑器查看或备份。

## 🤝 贡献与支持
如有任何问题或建议，欢迎提交 Issue 或联系项目维护者。
