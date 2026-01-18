# LinkSell AI 上下文文档 (LLM Context)

本文档旨在为大型语言模型（LLM）提供 LinkSell 项目的技术概览、架构逻辑及业务规则，以便 AI 能够准确理解代码库并在后续开发中保持风格一致。

## 1. 项目概述
LinkSell 是一个基于命令行的客户关系管理（CRM）工具，利用生成式 AI 技术捕获、分析并存储销售互动数据。
*   **核心技术栈**: Python 3, Typer (CLI 框架), Rich (终端 UI), Volcengine SDK (LLM 服务)。
*   **数据存储**: 本地 JSON 文件 (`data/sales_data.json`)。
*   **现状说明**: 目前主要支持**文本输入**的分析与存储。ASR（语音转写）功能在 `record` 命令中仅为占位符，尚未完全实装。
*   **文档规范**: 所有文档（包括本文档）均应使用**中文**编写，并遵循标准技术文档格式。

## 2. 代码库深度解析 (Codebase Deep Dive)

### 2.1 文件功能与逻辑映射
*   **`src/main.py` (CLI 入口)**
    *   **职责**: 整个程序的指挥官。负责参数解析 (Typer)、界面渲染 (Rich) 和流程控制。
    *   **核心逻辑**:
        *   `init`: 创建 `data/sales_data.json` 和 `data/records/` 目录。
        *   `analyze`: 实现了 **"AI 分析 -> 人话展示 -> 交互式编辑 (Edit Loop) -> 双重存储"** 的完整闭环。
        *   `sanitize_filename`: 确保生成的独立文件名在任何操作系统上都合法。
    *   **交互细节**: 使用 `typer.edit()` 调用系统编辑器，允许用户在保存前修正 AI 的 JSON 结果。
*   **`src/services/llm_service.py` (AI 服务层)**
    *   **职责**: 对接火山引擎 Ark Runtime。
    *   **逻辑**: 
        *   从 `config/prompts/` 加载 System Prompt。
        *   调用 LLM 并处理 `temperature` 等参数。
        *   **清洗逻辑**: 自动剥离 LLM 返回可能包含的 Markdown 标记 (```json)，确保返回纯净的字典对象。
*   **`src/services/__init__.py`**
    *   **职责**: 暴露服务层接口，简化导入路径 (目前为空，作为包标识)。
*   **`config/prompts/analyze_sales.txt` (核心资产)**
    *   **职责**: 定义 AI 的人设（销售助理）和输出 Schema。所有字段定义（如 `project_opportunity`, `sentiment`）均源于此。
*   **`config/config.ini.template`**
    *   **职责**: 配置文件的模版。

### 2.2 配置文件指南 (`config/config.ini`)
*   **`[volcengine]`**:
    *   预留给语音识别 (ASR) 服务使用。目前 `main.py` 尚未调用此部分，但未来集成 ASR 时将依赖 `access_key` 和 `secret_key`。
*   **`[doubao]`**:
    *   **`api_key`**: 豆包大模型推理专用的 API Key。
    *   **`analyze_endpoint`**: 对应火山引擎控制台部署的推理接入点 ID (Endpoint ID)。
*   **`[storage]`**:
    *   **`data_file`**: 指定主数据库文件的路径。

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
### 4.1 双重存储机制 (Dual Storage)
为保证数据完整性与便携性，系统采用“总账 + 详单”的双备份策略：
1.  **总账文件 (Database)**:
    *   默认路径：`data/sales_data.json`
    *   用途：存储所有历史记录，用于后续统计与批量分析。
2.  **独立详单 (Individual Records)**:
    *   存储路径：`data/records/`
    *   命名规则：`{项目名}_{YYYYMMDD_HHMMSS}.json` (文件名会自动清洗非法字符)
    *   用途：便于单次分享、存档或人工查阅。

### 4.2 存储格式
数据以 JSON 格式存储。
*   **自增 ID**: 系统根据当前总账数组长度自动生成。
*   **时间戳**: 保存时自动追加 `created_at` 字段 (ISO-8601 格式)。

### 4.3 局限性说明
当前采用全量读写 JSON 文件的“小米加步枪”方案，适合单人使用或轻量级数据量（<10MB）。若数据量激增，需迁移至 SQLite 或其他数据库。

## 5. 关键工作流

### 分析工作流 (`analyze` 命令)
1.  **输入阶段**: 用户通过 `--content` 参数或交互式粘贴输入文本。
2.  **AI 处理**: `llm_service` 调用大模型，返回 JSON 数据。
3.  **交互循环 (The Interaction Loop)**:
    *   **展示**: 系统将 JSON 解析为人类可读的 Rich 表格和树状图。
    *   **决策**: 用户选择操作：
        *   `s` (Save): 确认无误，执行保存。
        *   `d` (Discard): 放弃本次结果。
        *   `e` (Edit): 调用系统默认编辑器打开 JSON 原文。
    *   **修正**: 用户在编辑器中修改并保存关闭后，系统重新解析 JSON 并回到“展示”步骤。
4.  **持久化**: 
    *   追加至 `sales_data.json`。
    *   生成独立备份文件至 `data/records/`。

## 6. 开发与维护指南
*   **提示词工程 (Prompt Engineering)**: 修改 `config/prompts/*.txt` 文件以调整 AI 行为。**严禁**在 Python 代码文件中硬编码提示词。
*   **文档风格**: 保持 `README.md` 和 `AI_README.md` 为中文，并在更新代码逻辑时同步更新这两个文档。AI 读取本文档后，应能模仿此风格撰写新的文档或注释。
*   **错误处理**: 所有外部 API 调用必须包裹在 try-except 块中。
*   **依赖管理**: 保持 `requirements.txt` 精简，避免引入不必要的库。
