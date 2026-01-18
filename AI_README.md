# LinkSell AI 上下文文档 (LLM Context)

> **注意**：本文档是 AI 协作开发的核心依据，描述了系统的 MVC 架构、业务逻辑映射及开发规范。

## 1. 系统架构 (Architecture)

LinkSell 2.0 采用严格的 **MVC (Model-View-Controller)** 分层架构，确保业务逻辑与展示界面彻底分离。

### 1.1 核心层 (Controller)
*   **文件**: `src/core/controller.py`
*   **类**: `LinkSellController`
*   **职责**: 系统的“唯一大脑”。所有业务逻辑、API 调用、文件读写、配置加载**必须**在此完成。
*   **核心方法**:
    *   `get_intent(text)`: **(新增)** 识别用户意图：`ANALYZE` (录入), `QUERY` (查询), `OTHER` (闲聊)。
    *   `handle_query(query_text)`: **(新增)** 语义搜索 RAG 流程。先从向量库检索上下文，再调 LLM 生成专业回答。
    *   `search_opportunities(keyword)`: **(新增)** 按关键字模糊匹配已有商机名，防止重复建档。
    *   `save(record, raw_content)`: **(重构)** CRM 级存储逻辑。按 `project_name` 聚合，支持追加 `notes` 数组。
    *   `transcribe(audio_path)`: 调用 ASR 服务，支持异步轮询。
    *   `get_missing_fields(data)`: 业务规则校验。**新增**对 `opportunity_stage` (数字化阶段) 的强制检查。
    *   `summarize_text(content)`: **(内部逻辑)** 对超过 500 字的小记自动进行 AI 提炼。

### 1.2 视图层 (View) - GUI (Web)
*   **文件**: `src/gui/app.py`
*   **框架**: Streamlit
*   **职责**: 负责 Web 端的界面渲染。
*   **交互规范**: 必须使用 `get_ui_text()` 从 `ui_templates.json` 获取语料。所有保存动作需经过“转商机”与“项目匹配”两次确认。

### 1.3 视图层 (View) - CLI (Terminal)
*   **目录**: `src/cli/`
*   **文件**: `src/cli/interface.py`
*   **职责**: 终端交互实现。支持 `console.clear()` 驱动的沉浸式循环界面。

### 1.4 路由分流器 (Entry Point)
*   **文件**: `src/main.py`
*   **职责**: 程序入口。**新增**在启动前根据 `config.ini` 全局配置设置 `HF_ENDPOINT` 环境变量。

### 1.5 服务层 (Services)
*   **目录**: `src/services/`
*   **职责**: 无状态底层 API 封装。
    *   **VectorService**: **(新增)** 本地 Embedding 引擎。使用 `Sentence-Transformer` 实现语义向量化，由 `ChromaDB` 负责持久化。
    *   **LLM Service**: 封装豆包 API。**新增** `classify_intent` (意图分类)、`query_sales_data` (RAG查询)、`summarize_note` (长文摘要)。
    *   **ASR Service**: 采用“提交任务 -> 定时轮询”模式，支持静音检测 (Status 20000003)。

## 2. 核心工作流 (Workflow)

### 2.1 分析与存量归档 (CRM Loop)
1.  **输入与意图识别**: 识别为 `ANALYZE` 意图。
2.  **提炼小记**: 执行 `polish` -> `analyze` 生成初稿。
3.  **商机判定**: 询问用户是否转为“商机”。
4.  **关联搜索**: 如果转商机，通过 `search_opportunities` 搜索已存在项目。
5.  **匹配与补全**: 锁定唯一项目名或新建，随后补全缺失字段（如商机阶段 1-4）。
6.  **聚合存档**: 执行 `save`。系统自动对长文本做 `summarize`，并双写至 JSON 与向量库。

### 2.2 语义查询 (Query Loop)
1.  **输入与意图识别**: 识别为 `QUERY` 意图。
2.  **语义检索**: `VectorService` 在本地库检索最相关的 Top-5 历史记录。
3.  **生成回答**: LLM 结合历史记录上下文回答用户问题。

## 3. 业务规则规范

### 3.1 数字化商机阶段
*   **规范**: 存储时 `opportunity_stage` 必须为数字 (1, 2, 3, 4)。
*   **映射**: 1:需求确认, 2:沟通交流, 3:商务谈判, 4:签订合同。映射关系在 `config.ini` 中定义。

### 3.2 摘要阈值
*   **阈值**: 500 字。超过此长度的原始记录必须提炼摘要存入 `notes`。

## 4. 开发禁忌 (Dont's)
1.  **禁止** 在 Controller 以外的任何地方处理 `data/` 下的 JSON 文件。
2.  **禁止** 在 View 层硬编码任何提示文本（统一使用 `ui_templates.json`）。
3.  **禁止** 破坏 `project_name` 作为商机唯一聚合主键的原则。
