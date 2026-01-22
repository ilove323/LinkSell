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
    - **MERGE**: `handle_save` → `controller.merge` → `calculate_changes` (Diff) → 自动保存 → 返回变更报告。

---

## 2. 大模型调用与提示词体系 (LLM & Prompt System)

LinkSell 采用**八层提示词体系**精确控制 AI 在各个业务环节的行为。以下是完整的 Prompt 清单和调用关系：

### 2.0 Prompt 文件总览

| 优先级 | Prompt 文件 | 调用入口 | 核心功能 |
|--------|-----------|--------|---------|
|  P1 | `classify_intent.txt` | `controller.identify_intent()` | 意图识别（RECORD/CREATE/GET/LIST/REPLACE/MERGE/DELETE/OTHER） |
|  P2 | `sales_architect.txt` | `llm_service.architect_analyze()` | 结构化提取 + 小记生成（**最核心**） |
|  P3 | `polish_text.txt` | `controller.polish()` | 文本润色（口语→书面语） |
|  P4 | `extract_search_term.txt` | `controller.extract_search_term()` | 关键词提取（模糊指令→精准搜索词） |
|  P5 | `query_sales.txt` | `llm_service.query_sales_data()` | RAG 问答（基于搜索结果回答） |
|  P6 | `summarize_note.txt` | `llm_service.summarize_text()` | 长文本摘要（>500 字时） |
|  P7 | `judge_save.txt` | `llm_service.judge_affirmative()` | 确认判断（是/否回答） |
|  P8 | `delete_confirmation.txt` | 预留调用 | 删除确认（当前未激活） |

### 2.1 完整的 LLM 调用链 (Call Chain)

```
engine.handle_user_input(text)
    ↓
    controller.identify_intent(text)  ← ① classify_intent.txt
    ↓
    分发到对应 handler：

    ├─ handle_record()
    │  ├─ controller.add_to_note_buffer(content)
    │  │  └─ controller.polish(content)  ← ③ polish_text.txt
    │  └─ 返回 {"type": "record", "message": "..."}
    │
    ├─ handle_create() 或 handle_save()
    │  ├─ controller.merge(data, note)
    │  │  ├─ architect_analyze(notes, original_data)  ← ② sales_architect.txt
    │  │  │  └─ 返回: {"current_log_entry": "...", "opportunity_stage": 1-4, ...}
    │  │  ├─ 检查是否需要摘要（>500字）
    │  │  │  └─ summarize_text()  ← ⑥ summarize_note.txt （可选）
    │  │  └─ 生成变更报告
    │  └─ controller.overwrite_opportunity(merged)  (保存到JSON)
    │  └─ 返回 {"type": "detail", "message": "...", "report_text": "..."}
    │
    ├─ handle_get() / handle_replace()
    │  ├─ controller.resolve_target_interactive(content, context_id)
    │  │  └─ controller.extract_search_term(content)  ← ④ extract_search_term.txt
    │  └─ 返回定位结果或候选列表
    │
    ├─ handle_list()
    │  ├─ controller.extract_search_term(content)  ← ④ extract_search_term.txt
    │  └─ 向量搜索 + 关键词过滤
    │  ├─ (可选) query_sales_data(query, results)  ← ⑤ query_sales.txt
    │  └─ 返回列表或问答结果
    │
    └─ handle_delete()
       ├─ (预留) judge_affirmative(user_confirm)  ← ⑦ judge_save.txt
       ├─ (预留) delete_confirmation(record)  ← ⑧ delete_confirmation.txt
       └─ controller.delete_opportunity(id)
```

### 2.2 笔记处理流程 (RECORDing Pipeline)

#### Step 1: 意图识别
```python
# 代码位置: controller.py:165
def identify_intent(self, text):
    system_prompt = load_prompt("classify_intent")  # ① classify_intent.txt
    result = classify_intent(text, api_key, endpoint_id)
    # 返回: {"intent": "RECORD", "content": "笔记内容"}
```

#### Step 2: 文本润色（RECORD 阶段）
```python
# 代码位置: controller.py:1069
def add_to_note_buffer(self, content):
    polished = self.polish(content)  # ③ polish_text.txt
    self.note_buffer.append(polished)
    return polished

# 代码位置: controller.py:157
def polish(self, text):
    system_prompt = load_prompt("polish_text")  # ③ polish_text.txt
    return polish_text(text, api_key, endpoint_id)
```

**示例**:
```
输入:   "那个，今天嗯，跟王总聊了一下那个轴承项目的事儿，预算大概50万左右吧..."
↓ (polish_text.txt)
输出:   "今天与王总沟通了轴承项目的相关事宜，预算初步估计在50万左右。"
↓ (存入 note_buffer)
缓存:   ["今天与王总沟通了轴承项目..."]
```

### 2.3 结构化提取流程 (Extraction Pipeline) - 核心

#### Step 3: 结构化分析（CREATE/MERGE 阶段）
```python
# 代码位置: controller.py:525
def merge(self, data: dict, note_content: str) -> dict:
    # ... 验证逻辑 ...

    # 调用 Architect 模型
    parsed_data = architect_analyze(
        self.note_buffer,  # ② sales_architect.txt
        self.api_key,
        self.endpoint_id,
        original_data=data,  # 原商机数据
        sales_rep=self.default_sales_rep
    )
    # 返回包含 current_log_entry 的完整结构
```

#### Step 4: 长文本摘要（可选）
```python
# 代码位置: controller.py:694
def save(self, record, raw_content=""):
    final_log_content = record.pop("current_log_entry", None)

    # 如果没有 current_log_entry 且原文 >500 字
    if not final_log_content:
        polished_text = raw_content or record.get("summary", "")
        if polished_text and len(polished_text) > 500:
            final_log_content = summarize_text(polished_text, ...)  # ⑥ summarize_note.txt
        else:
            final_log_content = polished_text
```

### 2.4 智能合并与保存 (Smart Merge & Save)

```python
# 代码位置: controller.py:596
# 在 merge() 函数中：

# Step 1: 更新字段（Overwrite Mode）
merge_fields = ["project_name", "summary", "customer_info", "sentiment"]
for field in merge_fields:
    if field in parsed_data:
        merged[field] = parsed_data[field]

# Step 2: 追加列表（Append Mode，去重）
list_fields = ["action_items", "key_points", "customer_requirements"]
for list_key in list_fields:
    existing_items = set(merged["project_opportunity"].get(list_key, []))
    for item in parsed_data["project_opportunity"][list_key]:
        if item not in existing_items:
            merged["project_opportunity"][list_key].append(item)

# Step 3: 追加日志（核心！）
new_log_entry = {
    "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "sales_rep": self.default_sales_rep,
    "content": note_content  # 最终保存的小记
}
merged["record_logs"].append(new_log_entry)
```

**最终保存位置**:
```json
{
  "id": "...",
  "project_name": "沈阳轴承厂",
  "record_logs": [
    {
      "time": "2026-01-20 17:01:38",
      "sales_rep": "陈一骏",
      "content": "这里是来自 current_log_entry 的小记"  ← sales_architect.txt 生成
    }
  ]
}
```

### 2.5 关键词提取流程 (Keyword Extraction)

#### Step 5: 搜索定位（GET/LIST/REPLACE）
```python
# 代码位置: controller.py:214
def extract_search_term(self, text):
    prompt_path = Path("config/prompts/extract_search_term.txt")  # ④ extract_search_term.txt
    # 读取 prompt 并调用 LLM
    # 返回：具体词或 "ALL" 或 "Unknown"
```

**规则示例**:
```
"有哪些商机？"              → ALL
"查看沈阳轴承厂的详情"      → 沈阳轴承厂
"最近那个50万的单子"        → 50万
"看一下那个"                → ALL （太泛指）
```

### 2.6 RAG 问答流程 (Knowledge Base Query)

#### Step 6: 基于搜索结果的问答
```python
# 代码位置: controller.py:466
def query_knowledge_base(self, query_text, current_context=None):
    # Step 1: 提取关键词
    search_term = self.extract_search_term(query_text)  # ④ extract_search_term.txt

    # Step 2: 向量搜索
    history = self.vector_service.search(search_term)

    # Step 3: LLM 分析
    result = query_sales_data(query_text, history, ...)  # ⑤ query_sales.txt

    return result
```

### 2.7 确认与删除流程 (Confirmation & Deletion)

```python
# 代码位置: llm_service.py:142
def judge_affirmative(text: str, api_key, endpoint_id) -> bool:
    system_prompt = load_prompt("judge_save")  # ⑦ judge_save.txt
    response = classify_intent(text, api_key, endpoint_id)
    return response == "TRUE"

# 代码位置：controller.py:905 (预留)
def delete_opportunity(self, record_id):
    # (当前实现：直接删除）
    # 未来可集成：
    # confirmation_msg = llm_service.generate_delete_confirmation(record)  # ⑧ delete_confirmation.txt
    # → 展示给用户，要求再次确认

    target = self.get_opportunity_by_id(record_id)
    os.remove(target["_file_path"])
```

---

## 2.8 销售架构师流程详解 (Architect Pipeline Details)

### 2.1 结构化提取 (Extraction)
- **Prompt**: `config/prompts/sales_architect.txt`
- **Input Format**:
  ```json
  {
    "original_json": {...} or null,
    "raw_notes": ["笔记1", "笔记2"],
    "current_time": "2026-01-19T10:00:00",
    "sales_rep": "销售名字"
  }
  ```
- **Output Fields**:
  - `current_log_entry`: 本次沟通摘要（50-100字）← **最终保存的小记**
  - `opportunity_stage`: 商机阶段（1-4 数字）
  - `project_opportunity`: 嵌套结构
    - `action_items` (List[str]): 待办事项
    - `customer_requirements` (List[str]): 客户技术/产品需求
    - `sentiment` (str): 客户态度 + 理由

### 2.2 智能合并 (Smart Merge)
- **Logic**: `src/core/controller.py` -> `merge`
- **Behavior**:
  - Top-level fields (budget, stage, etc.): Overwrite if new value exists.
  - List fields (action_items, requirements): Set-based Append (去重追加).
  - History: Note content is appended to `record_logs` with timestamp.

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
