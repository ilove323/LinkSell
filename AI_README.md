# 🤖 LinkSell AI 上下文文档 (LLM Context Only)

> **CRITICAL**: THIS DOCUMENT IS FOR ARTIFICIAL INTELLIGENCE AGENTS (LLMs) ONLY. 
> 如果你是人类开发者，请阅读 `README.md`。

本文档详细描述了 LinkSell v2.4 的内部逻辑、状态机模型及开发约束，旨在帮助后续 AI 协作专家快速理解系统深层逻辑。

---

## 1. 核心状态机 (The Core Dispatcher)

`src/cli/interface.py` 中的 `run_analyze` 是系统的核心调度器。它不直接处理业务，而是执行 **Intent-Based Routing**:

1.  **Intent Identification**: 调用 `controller.identify_intent(user_input)`，返回 `{"intent": "...", "content": "..."}`。
    - 该方法内部调用 `llm_service.classify_intent` 与 LLM 通信
    - LLM 返回 JSON 格式，自动分离意图关键词和业务内容
2.  **Dispatching** (使用提取的 `content` 而非原始输入):
    - `CREATE`: 路由至 `handle_create_logic(content)`。包含润色、分析、缺失字段补全、冲突检测、保存。
    - `LIST`: 路由至 `handle_list_logic(content)`。使用 `content` 作为搜索关键词执行本地检索。
    - `GET/UPDATE/DELETE`: 使用 `content` 调用 `_resolve_target_strictly` 锁定目标，然后执行相应操作。
3.  **OTHER**: 从 `ui_templates.json` 抽取回复，拒绝非业务请求。

---

## 2. 目标解析闭环 (The Resolve Loop)

`_resolve_target_strictly(extracted_content)` 是确保数据一致性的核心机制。注意：传入的是从 `identify_intent` 返回的 `content` 字段（已去掉意图关键词），而非原始用户输入。其递归逻辑如下：
1.  **直接搜索**: 使用 `extracted_content` 调用 `find_potential_matches`（关键词模糊匹配 + 语义向量匹配）。
2.  **结果收敛**:
    - **0 结果**: 引导用户重新输入关键词或退出。
    - **1 结果**: 锁定目标并返回。
    - **N 结果**: 展示列表，要求输入 **[序号]**。若用户输入了 **[文字]**，则视为新的关键词搜索，重新开始循环。

---

## 3. 提示词与功能映射表 (Prompts Mapping)

| 文件名 | 调用方法 (Controller) | 业务逻辑 |
| :--- | :--- | :--- |
| `classify_intent.txt` | `identify_intent` → `classify_intent` (LLM) | **一步到位**：五大意图分流 + 内容提取，返回 JSON `{"intent": "...", "content": "..."}` |
| `extract_search_term.txt` | ~~`extract_search_term`~~ | **已废弃**：内容提取现已整合至 `classify_intent.txt` |
| `normalize_input.txt` | `normalize_input` | 填空题规范化 (处理 NULL、格式化金额/日期) |
| `judge_save.txt` | `judge_user_affirmative` | 全局布尔逻辑判决 |
| `analyze_sales.txt` | `analyze` | 销售对话结构化提取 |
| `update_sales.txt` | `update` | 自然语言驱动的 JSON 局部更新 |
| `polish_text.txt` | `polish` | 录音转写文本去燥润色 |

---

## 4. 开发红线 (Hard Rules for AI)

### 4.1 状态管理 (State Integrity)
- **Metadata Inheritance**: 在 `controller.update` 中，必须手动将 `original_data` 的元数据（`id`, `_file_path`, `_temp_id`, `created_at`, `record_logs`）拷贝至 LLM 返回的新对象中。**严禁丢失系统级字段。**
- **Atomic Operations**: `overwrite_opportunity` 必须确保文件变更与向量库更新同步。

### 4.2 交互规范
- **Intent + Content Pattern**: 所有与用户的意图识别必须使用 `controller.identify_intent(user_input)` 返回的 `content` 字段，而非原始 `user_input`。`content` 是经过 LLM 清洗过的、去掉了意图关键词的业务内容。
- **Randomized UI**: 严禁在 `interface.py` 或 `app.py` 中硬编码字符串。必须使用 `get_random_ui(key)` 从 `config/ui_templates.json` 获取语料。
- **Strict Normalization**: 所有 `typer.prompt` 的返回值，若涉及字段填空，必须经过 `controller.normalize_input` 过滤。

### 4.3 存储逻辑
- **File-per-Opp**: 严禁将所有商机存入同一个文件。数据必须以 `{project_name}.json` 形式分布存储。
- **Conflict Management**: `detect_data_conflicts` 用于检测新旧数据的结构性冲突，必须在 `CREATE` 流程中优先处理。

---

## 5. 常见 Debug 路径
- **NameError in CLI**: 检查 `interface.py` 的变量名拼写（注意 Unicode 字符干扰）。
- **Edit behaves like Copy**: 检查 `update` 方法是否丢失了 `_file_path`。
- **Intent classification errors**: 检查 `classify_intent.txt` 的提示词是否清晰、例子是否完整。若 LLM 返回非 JSON 格式，检查 `classify_intent()` 的 JSON 解析逻辑。
- **Wrong content extraction**: 验证 `content` 字段是否正确去掉了意图关键词。可在 `controller.identify_intent` 的返回值处打印调试。
- **Search not finding targets**: 确保传给 `_resolve_target_strictly` 的是从 `identify_intent` 返回的 `content`，而非原始输入。

---
*End of Context.*
