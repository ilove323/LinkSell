# LinkSell AI 上下文文档 (LLM Context)

> **注意**：本文档是 AI 协作开发的核心依据，描述了系统的 MVC 架构、业务逻辑映射及开发规范。

## 1. 系统架构 (Architecture)

LinkSell 2.0 采用严格的 **MVC (Model-View-Controller)** 分层架构，确保业务逻辑与展示界面彻底分离。

### 1.1 核心层 (Controller)
*   **文件**: `src/core/controller.py`
*   **类**: `LinkSellController`
*   **职责**: 系统的“唯一大脑”。所有业务逻辑、API 调用、文件读写、配置加载**必须**在此完成。
*   **核心方法**:
    *   `transcribe(audio_path)`: 调用 ASR 服务。
    *   `polish(text)`: 调用 LLM 润色文本。
    *   `analyze(text)`: 调用 LLM 生成结构化数据。
    *   `get_missing_fields(data)`: 业务规则校验，识别缺失字段。
    *   `refine(data, supplements)`: 补充缺失信息。
    *   `update(data, instruction)`: 处理自然语言修改指令。
    *   `save(data)`: 持久化存储 (JSON + Backup)。

### 1.2 视图层 (View) - GUI (Web)
*   **文件**: `src/gui/app.py`
*   **框架**: Streamlit
*   **职责**: 负责 Web 端的界面渲染和用户事件捕获。**严禁**直接包含 API 调用或复杂的业务判断。

### 1.3 视图层 (View) - CLI (Terminal)
*   **目录**: `src/cli/`
*   **文件**: `src/cli/interface.py`
*   **框架**: Typer + Rich
*   **职责**: 负责终端环境下的交互实现。包含 Rich 表格渲染、CLI 专属交互循环以及命令行语料加载。

### 1.4 路由分流器 (Entry Point)
*   **文件**: `src/main.py`
*   **职责**: 程序的统一入口。根据 `--cli` 参数，决定将控制权移交给 `src/cli/interface.py` 还是启动 `src/gui/app.py`。

### 1.5 服务层 (Services)
*   **目录**: `src/services/`
*   **职责**: 无状态的底层 API 封装（ASR, LLM）。由 Controller 统一调用。

## 2. 核心工作流 (Workflow)

### 2.1 分析闭环 (The Analysis Loop)
1.  **输入**: 用户通过 UI 组件 (GUI) 或 命令行参数 (CLI) 提供音频/文本。
2.  **润色 (Polish)**: 调用 `Controller.polish()`。
3.  **分析 (Analyze)**: 调用 `Controller.analyze()`。
4.  **补全 (Completion)**:
    *   UI 层调用 `Controller.get_missing_fields()` 获取缺失列表。
    *   UI 层引导用户输入补充信息。
    *   UI 层调用 `Controller.refine()` 更新状态。
5.  **修订 (Modification)**:
    *   用户输入自然语言修改意见。
    *   UI 层调用 `Controller.update()` 并重新渲染。
6.  **归档 (Save)**:
    *   UI 层调用 `Controller.save()` 完成持久化。

## 3. 交互规范 (Interaction Guidelines)

### 3.1 智能秘书人格
*   **语料驱动**: 所有界面文本**必须**从 `config/ui_templates.json` 加载。
*   **称呼**: 严禁使用“老板”称呼，统一使用“您”或专业商务语境。

### 3.2 报表展示
*   **一致性**: 无论 GUI 还是 CLI，展示维度（基础信息、客户画像、商机概览、关键点/待办）必须保持一致。
*   **反馈**: 每次数据更新后，必须立刻向用户展示最新的报表（流式展示）。

## 4. 开发禁忌 (Dont's)
1.  **禁止** 在视图层 (`src/gui/` 或 `src/cli/`) 直接导入 `requests` 或 `volcengine` SDK。
2.  **禁止** 在业务逻辑中使用 UI 相关的 print 或 st.write（应通过返回值由 UI 层处理）。
3.  **禁止** 破坏 `LinkSellController` 作为唯一逻辑入口的原则。