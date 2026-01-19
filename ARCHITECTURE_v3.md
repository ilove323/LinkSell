# LinkSell 架构重构说明 (v3.0)

## 概述

进行了代码分层重构，将**业务逻辑**和**UI展示层**完全分离，提高了代码的可维护性和可测试性。

## 新架构设计

### 1. **核心业务逻辑层** (`src/core/`)

#### `conversational_engine.py` (新)
- **职责**：处理所有对话流程和业务逻辑
- **不负责**：UI相关的任何事项
- **接口**：
  - `handle_get(content)` - 查看商机详情
  - `handle_list(content)` - 列表查询
  - `handle_create(project_name)` - 创建商机
  - `handle_update(content)` - 修改商机
  - `handle_delete(content)` - 删除商机
  - `handle_record(content)` - 记录笔记
  - `confirm_save()` / `discard_changes()` - 确认或放弃修改

**特点**：
- 返回**结构化的JSON结果**，统一格式
- 管理上下文状态（`current_opp_id`, `staged_data`等）
- 与`LinkSellController`交互完成实际业务操作

#### `controller.py` (保留)
- 保持不变，继续处理核心数据操作
- `get_all_opportunities()`, `get_opportunity_by_id()`, `update()`, `delete()` 等

### 2. **UI展示层** (`src/cli/`, `src/gui/`)

#### CLI 层 (`src/cli/cli.py`) (新)
- **职责**：与用户交互，调用引擎，展示结果
- **特点**：
  - 无业务逻辑，纯UI
  - 清晰的函数功能划分
  - 使用`rich`库美化输出

**主要函数**：
```python
main()                              # 主交互循环
display_opportunity_detail(data)    # 展示商机详情
display_opportunity_list(results)   # 展示列表
_handle_get_result(result)          # 处理GET结果
_handle_list_result(result)         # 处理LIST结果
```

#### GUI 层 (`src/gui/gui.py`) (新)
- **职责**：提供Streamlit图形界面，调用引擎，展示结果
- **特点**：
  - 无业务逻辑，纯UI
  - 使用Streamlit组件
  - 支持实时交互和确认对话

**主要函数**：
```python
process_user_input(user_input)      # 处理用户输入
display_report(data)                # 展示商机报告
_handle_get_result(result)          # 处理GET结果
```

### 3. **架构对比**

**之前**：
```
用户输入 → interface.py(混杂业务逻辑) → controller.py → 展示结果
```

**现在**：
```
用户输入 → CLI/GUI(纯UI) → ConversationalEngine(业务逻辑) → Controller → 返回结构化结果 → 展示
```

## 数据流示例

### GET 流程
```
用户: "查看中国投资咨询"
  ↓
classify_intent() → {"intent": "GET", "content": "中国投资咨询"}
  ↓
engine.handle_get("中国投资咨询")
  ↓
返回结果:
{
  "status": "success",
  "message": "已查看：...",
  "data": {...},
  "context_id": "1768794372"
}
  ↓
CLI/GUI 检查status，调用 display_opportunity_detail(data) 展示
```

### UPDATE 流程
```
用户: "把预算改为50万"
  ↓
classify_intent() → {"intent": "UPDATE", "content": "把预算改为50万"}
  ↓
engine.handle_update("把预算改为50万")
  ↓
返回结果:
{
  "status": "success",
  "data": {...},  # 修改后的数据（暂存）
  "missing_fields": {...}
}
  ↓
CLI/GUI 展示修改后的内容，等待确认
用户: "1"（确认保存）
  ↓
engine.confirm_save()
  ↓
数据保存到文件
```

## 使用新命令

### CLI (新)
```bash
python src/main.py chat
```
启动新的对话式CLI界面

### GUI (新)
```bash
python src/main.py
```
启动新的Streamlit界面（自动使用新的`gui.py`）

### 旧接口（保留兼容）
```bash
python src/main.py manage
python src/main.py analyze
```
仍然使用原来的`interface.py`实现（逐步迁移）

## 优势

1. **清晰的职责分离**
   - 业务逻辑集中在`ConversationalEngine`
   - UI层只负责展示和交互

2. **易于测试**
   - 可以独立测试引擎逻辑，无需启动UI
   - 可以mock引擎进行UI测试

3. **易于维护**
   - 修改业务逻辑无需改动UI
   - 修改UI风格无需改动业务逻辑

4. **易于扩展**
   - 可以轻松添加新的UI层（Web, API等）
   - 业务逻辑保持一致

5. **统一的数据格式**
   - 所有操作返回结构化JSON
   - CLI和GUI处理逻辑高度一致

## 迁移计划

- ✅ 创建`conversational_engine.py`
- ✅ 创建纯UI的`cli.py`
- ✅ 创建纯UI的`gui.py`
- ⏳ 逐步废弃`interface.py`中的业务逻辑部分
- ⏳ 完全迁移到新架构

## 注意事项

1. 旧的`interface.py`和`app.py`保持不动，确保向后兼容
2. 新的`cli.py`和`gui.py`是推荐使用的版本
3. 逐步迁移，不会影响现有功能
