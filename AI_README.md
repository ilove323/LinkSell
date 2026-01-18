# LinkSell AI 上下文文档 (LLM Context)

本文档旨在为大型语言模型（LLM）提供 LinkSell 项目的技术概览、架构逻辑及业务规则，以便 AI 能够准确理解代码库并在后续开发中保持风格一致。

## 1. 项目概述
LinkSell 是一个基于命令行的客户关系管理（CRM）工具，利用生成式 AI 技术捕获、分析并存储销售互动数据。
*   **核心技术栈**: Python 3, Typer (CLI 框架), Rich (终端 UI), Volcengine SDK (LLM 服务)。
*   **数据存储**: 本地 JSON 文件 (`data/sales_data.json`)。
*   **现状说明**: 目前主要支持**文本输入**的分析与存储。ASR（语音转写）功能在 `record` 命令中仅为占位符，尚未完全实装。
*   **文档规范**: 所有文档（包括本文档）均应使用**中文**编写，并遵循标准技术文档格式。

## 2. 目录结构与关键文件

*   **`src/main.py`**: 应用程序入口点。
    *   定义 Typer 命令：`init` (初始化), `record` (记录 - 暂未实装核心逻辑), `analyze` (分析 - 核心功能)。
    *   处理 CLI 参数并通过 `rich` 库提供用户交互界面。
    *   管理数据持久化逻辑（读取/写入 JSON）。
*   **`src/services/llm_service.py`**:
    *   封装对豆包（火山引擎）大模型的调用逻辑。
    *   从 `config/prompts/` 目录动态加载系统提示词。
    *   将原始 LLM 响应解析为结构化的 Python 字典（JSON）。
*   **`config/prompts/analyze_sales.txt`**:
    *   用于销售内容分析的系统提示词（System Prompt）。
    *   定义了输出数据必须严格遵循的 JSON 模式（Schema）。
*   **`config/config.ini`**:
    *   存储敏感凭据（API Keys, Endpoint IDs）及文件路径配置。
    *   接入点按功能区分，如 `analyze_endpoint` 用于销售内容提炼。
    *   **安全提示**: 严禁在代码输出或日志中泄露此文件内的实际密钥。

## 3. 数据模式 (sales_data.json)
应用程序将记录存储为对象列表。每个记录对象严格遵循 `config/prompts/analyze_sales.txt` 定义的结构：

```json
{
  "id": 1,                       // 系统自动生成 ID
  "record_type": "chat|meeting", // 记录类型：chat (闲聊/口述), meeting (会议)
  "summary": "String",           // 内容摘要（100字以内）
  "customer_info": {             // 客户信息对象
      "name": "...",             // 姓名
      "company": "...",          // 公司
      "role": "...",             // [新增] 职位/角色
      "contact": "..."           // [新增] 联系方式
  },
  "project_opportunity": {       // 商机信息对象
      "is_new_project": bool,    // 是否新项目
      "project_name": "...",     // [新增] 项目名称/代号
      "budget": "...",           // 预算
      "tech_stack": ["..."],     // [新增] 技术栈/产品需求关键词列表
      "stage": "..."             // [新增] 项目阶段
  },
  "key_points": ["..."],         // 关键点列表
  "action_items": ["..."],       // 待办事项列表
  "sentiment": "String",         // 客户情感分析及理由
  "created_at": "ISO-8601 Timestamp" // 创建时间戳 (系统自动生成)
}
```

## 4. 数据存储详解
### 4.1 存储位置
*   默认路径：`data/sales_data.json`
*   配置方式：可在 `config/config.ini` 中的 `[storage]` 部分修改 `data_file` 路径。

### 4.2 存储格式
数据以 JSON 数组形式存储，每条记录为一个独立的对象。
*   **自增 ID**: 系统根据当前数组长度自动生成 (`len(current_data) + 1`)。
*   **时间戳**: 保存时自动追加 `created_at` 字段 (ISO-8601 格式)。
*   **示例**:
    ```json
    [
      {
        "id": 1,
        "record_type": "chat",
        "summary": "...",
        "created_at": "2026-01-18T10:30:00.123456",
        ... // 其他 AI 分析字段
      }
    ]
    ```

### 4.3 局限性说明
当前采用全量读写 JSON 文件的“小米加步枪”方案，适合单人使用或轻量级数据量（<10MB）。若数据量激增，需迁移至 SQLite 或其他数据库。

## 5. 关键工作流

### 分析工作流 (`analyze` 命令)
1.  用户通过 `--content` 参数输入文本内容，**若未提供参数，程序会提示用户进行交互式粘贴输入**。
2.  `main.py` 从配置文件加载 API 密钥。
3.  `llm_service.py` 读取 `config/prompts/analyze_sales.txt` 中的提示词。
4.  向豆包大模型发送请求（设置 temperature=0.1 以保证输出稳定性）。
5.  LLM 返回 JSON 字符串。
6.  服务层解析 JSON 并返回 Python 字典对象。
7.  `main.py` 使用 `rich` 面板展示分析结果。
8.  若用户确认保存，`main.py` 将记录追加至 `data/sales_data.json` 文件。

## 5. 开发与维护指南
*   **提示词工程 (Prompt Engineering)**: 修改 `config/prompts/*.txt` 文件以调整 AI 行为。**严禁**在 Python 代码文件中硬编码提示词。
*   **文档风格**: 保持 `README.md` 和 `AI_README.md` 为中文，并在更新代码逻辑时同步更新这两个文档。AI 读取本文档后，应能模仿此风格撰写新的文档或注释。
*   **错误处理**: 所有外部 API 调用必须包裹在 try-except 块中。
*   **依赖管理**: 保持 `requirements.txt` 精简，避免引入不必要的库。
