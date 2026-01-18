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
        *   `analyze`: 实现了 **"语音转录 -> 文本润色 -> AI 分析 -> 数据完整性校验 -> 对话式修订 (Modification Loop) -> 持久化"** 的闭环。
        *   `get_random_ui`: 实现了基于语料库的随机应答机制，通过 `config/ui_templates.json` 驱动。
*   **`src/services/llm_service.py` (AI 服务层)**
    *   **职责**: 对接火山引擎 Ark Runtime。
    *   **逻辑**: 
        *   `analyze_text`: 结构化分析原始文本。
        *   `polish_text`: 对口语进行润色，提升分析准确度。
        *   `update_sales_data`: **核心修订逻辑**。接收用户自然语言指令，结合原始 JSON 调用 LLM 生成修订后的版本。
        *   `refine_sales_data`: 针对缺失字段进行针对性补全。
*   **`src/services/asr_service.py` (语音服务层)**
    *   **逻辑**: 对接火山引擎 **Seed ASR** 大模型任务接口，采用异步轮询机制。
# ... (rest same)

### 2.2 配置文件
*   **`config/config.ini`**: 包含 API 密钥。
*   **`config/ui_templates.json`**: 定义了“秘书”人格的随机语料库。
*   **`config/prompts/`**: 存储 System Prompts。
    *   `analyze_sales.txt`: 初始结构化提取。
    *   `polish_text.txt`: 口语转书面。
    *   `update_sales.txt`: **对话式修改专用提示词**。
    *   `refine_sales.txt`: 字段缺失补全。

# ... (Schema same)

### 5. 关键工作流

#### 分析工作流 (`analyze` 命令)
1.  **输入阶段**: 
    *   **路径 A (语音)**: `asr_service` 转写。
    *   **路径 B (文本)**: 交互式输入。
2.  **文本润色**: `llm_service.polish_text` 预处理。
3.  **AI 初步分析**: `llm_service.analyze_text` 生成初始 JSON。
4.  **数据完整性校验 (Validation & Completion)**:
    *   系统自动扫描必填字段。
    *   **交互式补全**: 通过“秘书”语料引导用户补充。
5.  **交互修订循环 (Modification Loop)**:
    *   **展示**: 展示 Rich 报表。
    *   **决策**: 
        *   `s` (Save): 保存。
        *   `d` (Discard): 丢弃。
        *   `m` (Modify): **输入自然语言指令进行修改**。
    *   **修订**: 调用 `llm_service.update_sales_data`，刷新报表并回到展示步骤。
6.  **持久化**: 存入主库并生成独立备份。

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