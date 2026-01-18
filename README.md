# LinkSell - 销售神器 CLI 版

LinkSell 是一个专为销售团队打造的命令行工具（CLI）。它集成了**火山引擎语音识别**和**豆包大模型**，旨在将碎片化的销售对话和正式的会议纪要，高效地转换为结构化销售数据，并自动存入本地数据库。

## ✨ 核心功能

*   **🎙️ 多场景记录**：支持会议记录 (`meeting`) 和随手闲聊 (`chat`) 的灵活录入。
*   **🧠 智能提炼**：接入豆包大模型，自动识别内容类型，提取客户信息、商机详情及待办事项。
*   **📂 本地安全存储**：数据以 JSON 格式保存在本地，确保数据隐私与安全。
*   **⚙️ 灵活配置**：通过标准化的 `config.ini` 文件管理 API 密钥与系统提示词（Prompts）。

## 🚀 快速开始

### 1. 环境准备
请确保您的环境已安装 Python 3.8 或更高版本。

```bash
# 克隆项目（假设您已完成克隆）
cd LinkSell

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows 用户请使用 .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置密钥
请将 `config/config.ini.template` 复制为 `config/config.ini`，并填入您的火山引擎 Access Key (AK)、Secret Key (SK) 及豆包大模型 API Key 和 Endpoint ID。

### 3. 初始化项目
运行以下命令以初始化数据文件及检查配置：
```bash
python src/main.py init
```

### 4. 功能演示
**提炼一段销售对话：**
```bash
python src/main.py analyze --content "今天跟张总聊了个50万的大单子..."
```

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

## 🤝 贡献与支持
如有任何问题或建议，欢迎提交 Issue 或联系项目维护者。
