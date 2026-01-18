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
        *   `analyze_text`: 调用 LLM 分析原始文本，生成初始 JSON。
        *   `refine_sales_data`: 接收用户补充的碎片化信息，结合原始数据进行校验、格式化（如统一金额单位）与合并。
        *   **清洗逻辑**: 自动剥离 LLM 返回可能包含的 Markdown 标记 (```json)，确保返回纯净的字典对象。
*   **`src/services/asr_service.py` (语音服务层)**
    *   **职责**: 对接火山引擎语音识别 (ASR) 服务。
    *   **逻辑**:
        *   调用“一句话识别”接口 (Short Audio Recognition)。
        *   处理音频文件读取与 Base64 编码。
        *   **鉴权**: 依赖 `[volcengine]` 中的 AK/SK 和 `[asr]` 中的 AppID。
*   **`src/services/__init__.py`**
    *   **职责**: 暴露服务层接口，简化导入路径 (目前为空，作为包标识)。

### 2.2 配置文件
*   **`config/config.ini`**: 包含 API 密钥（Doubao, Volcengine, ASR）、Endpoint ID 和文件路径。**严禁提交至 Git**。
*   **`config/prompts/`**: 存储 System Prompts。
    *   `analyze_sales.txt`: 用于初始分析，定义了严格的 JSON 输出格式（含商机、客户画像、竞争对手等字段）。
    *   `refine_sales.txt`: 用于数据校验，处理用户补录的碎片化信息。

## 3. 数据结构 (Data Schema)
AI 分析后的数据结构（JSON）包含以下关键字段：
*   `record_type`: 记录类型 (meeting/chat)。
*   `sales_rep`: 我方销售负责人/记录人姓名。
*   `customer_info`: 客户画像 (姓名, 公司, 职位, 联系方式)。
*   `project_opportunity`: 商机详情 (项目名, 预算, 阶段, 技术栈, **时间节点**, **采购流程**, **付款方式**, **竞争对手**)。
*   `key_points`: 核心要点列表。
*   `action_items`: 待办事项/下一步计划。
*   `sentiment`: 客户情感分析。

## 4. 依赖管理
*   `requirements.txt`: 
    *   `typer`: 命令行界面。
    *   `rich`: 终端美化。
    *   `volcengine-python-sdk[ark]`: 火山引擎 SDK (含 Ark Runtime 扩展)。
    *   `requests`: HTTP 请求。
    *   `configparser`: 配置读取。

## 5. 关键工作流

### 分析工作流 (`analyze` 命令)
1.  **输入阶段**: 
    *   **路径 A (语音)**: 用户提供 `--audio` 参数。系统调用 `asr_service` 进行转写，若成功则将文本作为后续输入。
    *   **路径 B (文本)**: 用户通过 `--content` 参数或交互式粘贴输入文本。
2.  **AI 初步分析**: `llm_service.analyze_text` 调用大模型，返回初始 JSON 数据。
3.  **数据完整性校验 (Validation & Completion)**:
    *   系统自动检查 `project_opportunity` 中的关键字段（预算、时间节点、采购流程等）。
    *   **交互式补全**: 若发现缺失，CLI 提示用户输入补充信息。
    *   **AI 清洗**: 若用户提供了补充信息，系统调用 `llm_service.refine_sales_data`，利用专用 Prompt (`refine_sales.txt`) 对输入进行格式规范化（如将“三万”转换为数字）并合并至原数据。
4.  **交互循环 (The Interaction Loop)**:
    *   **展示**: 系统将 JSON 解析为人类可读的 Rich 表格和树状图。
    *   **决策**: 用户选择操作：
        *   `s` (Save): 确认无误，执行保存。
        *   `d` (Discard): 放弃本次结果。
        *   `e` (Edit): 调用系统默认编辑器打开 JSON 原文。
    *   **修正**: 用户在编辑器中修改并保存关闭后，系统重新解析 JSON 并回到“展示”步骤。
5.  **持久化**: 
    *   追加至 `sales_data.json`。
    *   生成独立备份文件至 `data/records/`。

## 6. 开发规范 (Development Standards)
**所有 AI 协作者必须严格遵守以下规范：**

*   **语言要求**: 项目中的所有文档 (`.md`)、代码注释、CLI 输出信息 (Print/Log) 必须使用**简体中文**。
*   **语气风格**:
    *   **工件 (Artifacts)**: 代码注释、文档、程序运行输出必须保持**专业、严谨、客观**的技术文档风格（Technical Writing Style）。严禁在这些位置使用“老大哥”、“东北话”或任何俚语。
    *   **交互 (Chat)**: 仅在与用户的对话（Chat Interface）中保持“东北虎哥”的人设。
*   **注释规范**: 
    *   函数必须包含 Docstring，说明 Args 和 Returns。
    *   复杂逻辑块必须添加行内注释。
*   **文档同步**: 任何功能变更必须同步更新 `README.md` 和 `AI_README.md`。