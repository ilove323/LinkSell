# LinkSell - 销售神器 CLI 版

LinkSell 是一个专为销售团队打造的命令行工具（CLI）。它集成了**火山引擎语音识别**和**豆包大模型**，旨在将碎片化的销售对话和正式的会议纪要，高效地转换为结构化销售数据，并自动存入本地数据库。

## ✨ 核心功能

*   **🧠 智能提炼 (已就绪)**：接入豆包大模型，自动识别内容类型，深度提取客户画像、项目商机、技术栈及待办事项。
*   **📂 本地安全存储 (已就绪)**：数据以 JSON 格式保存在本地，确保数据隐私与安全。
*   **⚙️ 灵活配置 (已就绪)**：通过标准化的 `config.ini` 文件管理 API 密钥与系统提示词（Prompts）。
*   **🎙️ 语音转写 (已实装)**：集成火山引擎 Seed ASR 大模型，支持录音文件及麦克风直接识别。
*   **✨ 文本润色 (已实装)**：在分析前自动去除口语冗余，将口述内容转化为规范的书面文本。
*   **🤖 秘书式交互 (已实装)**：内置可自定义的语料库，提供温婉、专业的“秘书”级操作反馈。

## 🚀 快速开始

### 1. 环境准备
# ... (same)

### 2. 配置密钥
# ... (same)

### 2.3 语音识别配置 (ASR)
本项目采用 **Seed ASR 大模型语音识别服务**。

在 `config/config.ini` 中填入 AppID 及 Access Token：
```ini
[asr]
app_id = 12345678
access_token = YOUR_ACCESS_TOKEN_HERE
resource_id = volc.seedasr.auc
```
*注意：`resource_id` 建议设置为 `volc.seedasr.auc` 以获得最佳的大模型识别效果。*

## 📁 核心配置文件
*   `config/config.ini`: 存放所有 API 密钥。
*   `config/prompts/*.txt`: 存放 AI 系统提示词（Prompt）。
*   `config/ui_templates.json`: 存放 CLI 界面交互的随机语料库，支持自定义“秘书”话术。

## 3. 使用指南 (Usage)

### 核心功能：销售分析 (Analyze)
分析流程：**输入 (语音/文本) -> 文本润色 -> AI 结构化提炼 -> 数据补全校验 -> 对话式修订 -> 归档保存。**

#### 方式一：语音分析 (麦克风/文件)
```bash
# 使用麦克风直接录音（按回车结束）
python src/main.py analyze --microphone

# 指定录音文件路径
python src/main.py analyze --audio "./data/tmp/test.wav"
```

#### 方式二：文本分析
```bash
python src/main.py analyze --content "今天跟王经理沟通了..."
```

### 对话式修订 (Interactive Modification)
分析完成后，系统将展示精美的结构化报表。若发现内容有误，您不再需要手动编辑复杂的 JSON：
1.  输入 `m`: 进入修改模式。
2.  直接输入自然语言指令，例如：
    *   “把预算改成 100 万”
    *   “客户姓名记错了，是李四”
    *   “增加一个竞争对手：赛立信”
3.  系统将通过 AI 自动理解并更新报表。

### 其他操作
*   输入 `s`: 确认并保存记录至本地。
*   输入 `d`: 丢弃本次分析结果。

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
