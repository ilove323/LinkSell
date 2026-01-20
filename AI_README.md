# 🤖 LinkSell AI 上下文文档 (LLM Context Only)

> **CRITICAL**: THIS DOCUMENT IS FOR ARTIFICIAL INTELLIGENCE AGENTS (LLMs) ONLY. 
> 如果你是人类开发者，请阅读 `README.md`。

本文档详细描述了 LinkSell v3.2 的内部逻辑、状态机模型及开发约束，斨在帮助后续 AI 协作专家快速理解系统深层逻辑。

---

## 1. 核心状态机 (The Core Dispatcher & State)

`src/core/conversational_engine.py` (`ConversationalEngine`) 是系统的**核心大脑**，它维护了会话的**全局状态**并负责所有意图的路由与处理。CLI 和 GUI 仅作为**无状态的渲染层 (Stateless Renderers)**。

### 1.1 全局变量 (In Engine)
- `current_opp_id`: (str|None) 存储当前上下文锁定的商机 ID。
    - **Set via GET/CREATE/REPLACE**: 当成功定位或创建目标时，引擎自动更新此变量。
    - **Used by UPDATE/RECORD**: 当检测到模糊指令（Vague Instruction）或追加笔记时，自动使用此 ID 作为目标。

### 1.2 路由逻辑 (Intent-Based Routing v3.2)
1.  **Unified Entry**: 所有用户输入通过 `engine.handle_user_input(text)` 进入。
2.  **Intent Identification**: 调用 `controller.identify_intent` 获取 `intent` 和 `content`。
3.  **Dispatching**:
    - **RECORD**: `handle_record` → `controller.add_to_note_buffer` (自动 polish) → 返回状态。
    - **CREATE**: `handle_create` → `controller.process_commit_request` (自动生成首条小记) → 自动保存 → 返回结果。
    - **GET**: `handle_get` → 更新 `current_opp_id` → 返回 `type: detail` 供 UI 渲染。
    - **REPLACE**: `handle_replace` → `controller.replace` → 自动保存 → 返回更新报告。
    - **SAVE/MERGE**: `handle_save` → `controller.merge` → `calculate_changes` (Diff) → 自动保存 → 返回变更报告。

---

## 2. 销售架构师流程 (The Architect Pipeline)

### 2.1 笔记处理 (RECORDing)
- `controller.add_to_note_buffer`: 
  - 第一步先调用 `llm_service.polish_text` (prompt: `polish_text.txt`) 进行润色。
  - 将润色后的文本存入 buffer。

### 2.2 结构化提取 (Extraction)
- **Prompt**: `config/prompts/sales_architect.txt`
- **Fields**: 
  - `action_items` (List[str]): 待办事项。
  - `customer_requirements` (List[str]): 客户技术/产品需求。
  - `sentiment` (str): 客户态度 + 理由。
  - `current_log_entry`: 本次沟通摘要。

### 2.3 智能合并 (Smart Merge)
- **Logic**: `src/core/controller.py` -> `merge`
- **Behavior**:
  - Top-level fields (budget, stage, etc.): Overwrite if new value exists.
  - List fields (action_items, requirements): Set-based Append (去重追加).
  - History: Buffer content is appended to `record_logs` with timestamp.

---

## 3. 向量引擎 (Vector Engine v3.2)

### 3.1 异步加载 (Async Loading)
- **File**: `src/services/vector_service.py`
- **Implementation**: Uses `threading.Thread` to load `SentenceTransformer` and `ChromaDB` in the background.
- **Lazy Wait**: `_ensure_initialized()` uses `threading.Event.wait()` to block only if a query arrives before initialization completes.

### 3.2 元数据过滤 (Metadata Filtering)
- **Storage**: Key fields (`sales_rep`, `project_name`, `stage`) are stored in ChromaDB `metadatas`.
- **Search**: `search` method accepts `where_filter` dict for precise SQL-like filtering.

---

## 4. UI 渲染规范 (Markdown Specs)

### 4.1 详情页布局 (`_format_report`)
- **Customer Info**: Multi-line block (Name / Company / Role / Contact).
- **Project Metrics**: Separate lines for Budget and Timeline.
- **Lists**: `customer_requirements` and `action_items` rendered as bullet points.
- **History**: "Sales Notes" section showing the last 3 entries (descending order).

### 4.2 换行处理
- All lines in list/blocks must end with two spaces (`  `) to ensure proper Markdown line breaks.

---

## 5. 开发红线 (Hard Rules for AI)

### 5.1 状态管理 (State Integrity)
- **Engine Owns State**: 所有的状态变更（ID 锁定、草稿暂存）必须在 `ConversationalEngine` 中完成。
- **Global ID Sync**: 任何成功解析出唯一目标的操作（GET, REPLACE, CREATE），都应更新 `engine.current_opp_id`。

### 5.2 交互规范
- **Render-Ready Responses**: Engine 返回的 `message` 字段应包含所有必要的提示信息。
- **Diff Feedback**: 所有的 UPDATE/MERGE 操作必须返回 `Diff` (变更报告) 给用户。

---
*End of Context.*
