# 🤖 LinkSell AI 上下文文档 (LLM Context Only)

> **CRITICAL**: THIS DOCUMENT IS FOR ARTIFICIAL INTELLIGENCE AGENTS (LLMs) ONLY. 
> 如果你是人类开发者，请阅读 `README.md`。

本文档详细描述了 LinkSell v2.5 的内部逻辑、状态机模型及开发约束，旨在帮助后续 AI 协作专家快速理解系统深层逻辑。

---

## 1. 核心状态机 (The Core Dispatcher & State)

`src/cli/interface.py` 不仅是视图层，还维护了会话的**全局状态**：

### 1.1 全局变量
- `current_opp_id`: (str|None) 存储当前用户正在查看或操作的商机 ID。
    - **Set via GET**: 当 `handle_get_logic` 成功解析目标时，**静默更新**此变量。
    - **Used by UPDATE**: 当 `handle_update_logic` 检测到模糊指令（Vague Instruction）时，自动使用此 ID 作为目标。

### 1.2 路由逻辑 (Intent-Based Routing v3.0)
1.  **Intent Identification**: 调用 `controller.identify_intent` 获取 `intent` 和 `content`。
2.  **Dispatching**:
    - **RECORD**: 路由至 `handle_record_logic` -> 调用 `controller.add_to_note_buffer`。
    - **CREATE**: 路由至 `handle_create_logic` -> 调用 `controller.process_commit_request` (触发 Architect 引擎)。
    - **GET**: 路由至 `handle_get_logic` -> 更新 `current_opp_id` -> 静默展示。
    - **UPDATE**: 路由至 `handle_update_logic` -> 字段级精准修正。
    - **LIST/DELETE**: 标准路由。

---

## 2. 销售架构师流程 (The Architect Pipeline)

### 2.1 笔记暂存 (RECORDing)
- 用户的原始输入被视为“笔记”。
- `controller` 维护一个 `note_buffer` 列表。
- 每条笔记都会先经过 `polish_text` 润色后再入库。

### 2.2 提交与合并 (CREATing)
- 当意图为 `CREATE` 时，触发 Commit 逻辑。
- **Entity Lookup**: 优先搜索笔记中提及的项目名，或使用 `project_name_hint`。
- **Merging**: 使用 `sales_architect.txt` 提示词。如果有 `original_json`，执行字段覆盖与 Log 追加；否则执行新建。
- **Stateless Confirmation**: 生成 `staged_data`，用户必须通过物理按钮或序号确认后才正式入库。


---

## 3. 提示词与功能映射表 (Prompts Mapping)

| 文件名 | 调用方法 (Controller) | 业务逻辑 |
| :--- | :--- | :--- |
| `classify_intent.txt` | `identify_intent` | 意图分流 + 内容提取。返回 JSON。 |
| `extract_search_term.txt` | `extract_search_term` | **辅助工具**：用于 UPDATE 流程中判断用户是否指明了具体项目（Vague Check）。 |
| `normalize_input.txt` | `normalize_input` | 填空题规范化 (处理 NULL、格式化金额/日期)。 |
| `judge_save.txt` | `judge_user_affirmative` | 全局布尔逻辑判决。 |
| `analyze_sales.txt` | `analyze` | 销售对话结构化提取。 |
| `update_sales.txt` | `update` | 自然语言驱动的 JSON 局部更新。 |
| `polish_text.txt` | `polish` | 录音转写文本去燥润色。 |

---

## 4. 开发红线 (Hard Rules for AI)

### 4.1 状态管理 (State Integrity)
- **Silent GET**: `handle_get_logic` **严禁**包含任何阻塞式交互（如 "按 E 编辑"），也不应打印 "已锁定 ID" 等调试信息。它只负责展示数据和更新变量。
- **Global ID Sync**: 任何成功解析出唯一目标的操作（GET, UPDATE, CREATE-Associate），都应更新 `current_opp_id`。

### 4.2 交互规范
- **Real IDs**: 所有的列表展示、选择逻辑必须基于真实 ID（字符串/时间戳）。严禁引入临时的 `enumerate` 索引。
- **Vague Check**: UPDATE 逻辑必须优先检查用户输入是否包含具体实体。只有在“未提取到实体”且“有全局 ID”时，才自动关联。

### 4.3 存储逻辑
- **Atomic Rename**: 修改项目名称时，必须保证文件重命名与向量库更新的一致性（已在 `controller.update` 实现）。

---

## 5. 常见 Debug 路径
- **"KeyError: 'id'"**: 检查列表展示逻辑是否使用了旧的 `_temp_id`。现在应直接使用 `id`。
- **Context Lost**: 检查 `handle_get_logic` 是否正确声明了 `global current_opp_id` 并赋值。
- **Infinite Loop in Create**: 检查 `choice` 判断逻辑，确保 `N` (新建) 和 `ID` (关联) 都有明确的退出路径。

---
*End of Context.*