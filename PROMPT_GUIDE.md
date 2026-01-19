# LinkSell Prompt 使用指南 (v3.1)

本文档详细记录所有 prompt 文件的功能、使用场景、调用方式和参数说明。

---

## 📊 总览表

| Action | Prompt 文件 | 核心功能 | 调用地点 | 返回类型 |
|--------|----------|--------|--------|---------|
| **CREATE** | `create_sales.txt` | 从文本生成结构化 JSON 商机数据 | `controller.analyze()` | JSON 对象 |
| **GET** | `query_sales.txt` | 根据现有 JSON 回答具体查询 | `controller.query()` | 纯文本答案 |
| **LIST** | `query_sales.txt` | 根据 JSON 列表回答列表查询 | `controller.query()` | 纯文本答案 |
| **REPLACE** | `sales_architect.txt` | 根据自然语言修改 JSON 字段 | `controller.replace()` | JSON 对象 |
| **MERGE** | (无) | 直接追加笔记到 record_logs | `controller.merge()` | JSON 对象（含新 log） |
| **CONTEXT**| `extract_search_term.txt`| 判断指令中的实体指向 | `controller.extract_search_term()`| 实体名称/空 |
| **DELETE** | `delete_confirmation.txt` | 删除前生成二次确认提示 | `controller.generate_delete_warning()` | 纯文本提示 |
| **OTHER** | (无) | 返回秘书语气拒绝 | CLI/GUI | 随机语料 |

---

## 🔧 详细说明

### 1. CREATE - `create_sales.txt` (原 analyze_sales.txt)

**功能**: 将用户的口述/文本转换为结构化的销售商机 JSON

**调用方式**:
```python
# controller.py
polished_text = self.polish(user_input)
sales_data = self.analyze(polished_text)  # 内部调用 create_sales.txt
```

**输入**:
- 用户的文本/口述内容（已经过 `polish_text.txt` 润色）

**输出**:
```json
{
  "record_type": "chat|meeting",
  "sales_rep": "销售名字",
  "summary": "摘要",
  "customer_info": {...},
  "project_opportunity": {...},
  "key_points": [...],
  "action_items": [...],
  "sentiment": "..."
}
```

---

### 2. REPLACE - `sales_architect.txt`

**功能**: 理解用户的自然语言修改指令，返回更新后的 JSON。支持模糊指令与上下文结合。

**调用方式**:
```python
# controller.py
updated_data = self.replace(original_data, user_instruction)
```

**特殊逻辑**:
- **原子重命名**: 若 Prompt 修改了 `project_name`，Controller 层会自动处理文件重命名和向量库更新。
- **格式规范化**: 内置了对金额、日期、阶段的标准化处理。

---

### 3. MERGE - (无专用 Prompt)

**功能**: 将笔记直接追加到商机的 record_logs，无需修改其他字段。

**调用方式**:
```python
# controller.py
merged_data = self.merge(opportunity_data, note_content)
```

**特点**:
- 纯追加逻辑，不修改商机任何其他字段
- 用于 SAVE 意图：将暂存笔记追加到当前商机的跟进记录
- 新增 log 条目包含：`time`, `recorder`, `content`

---

### 4. CONTEXT - `extract_search_term.txt`

**功能**: 从用户输入中提取核心实体（项目名/客户名）。

**重要性 (v3.1)**: 
- 此 Prompt 在 **REPLACE** 流程中起关键作用。
- 用于判断用户的指令是 **"针对特定项目"** (如 "修改沈阳机床的预算") 还是 **"针对当前上下文"** (如 "把预算改了")。
- 若此 Prompt 提取结果为空或不明确，Controller 将尝试使用全局 `current_opp_id`。

---

### 5. GET/LIST - `query_sales.txt`

---

### 4. GET/LIST - `query_sales.txt`

**功能**: 基于现有的商机 JSON，专业地回答用户的查询问题

**输入**:
- `sales_data`: 单个商机 JSON 或商机列表
- `query_text`: 用户的查询问题

---

## 🔄 辅助 Prompt (预处理和后处理)

| 文件名 | 用途 | 调用位置 |
|--------|------|--------|
| `classify_intent.txt` | 意图分类 + 内容提取 | `controller.identify_intent()` |
| `polish_text.txt` | 文本润色 | CREATE 流程的第一步 |
| `normalize_input.txt` | 输入规范化 | 用户手动补充字段时清洗 |
| `judge_save.txt` | 布尔判定 | 判断用户肯定/否定 |
| `delete_confirmation.txt` | 删除警告 | DELETE 流程 |

---

## ⚠️ 重要约定

1. **JSON 完整性**: 所有返回 JSON 的 prompt 必须返回完整、有效的 JSON，包括 `null` 值
2. **不返回 Markdown**: prompt 明确要求"仅返回 JSON，不要 Markdown 标记"
3. **Template 变量**: 使用 `{{variable}}` 格式，由 Python 代码负责替换
4. **内容提取**: 所有 ACTION handler 必须优先使用 `identify_intent` 返回的 `content` 字段。

---

*最后更新: 2026-01-19*