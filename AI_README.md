# LinkSell AI 上下文文档 (LLM Context)

> **注意**：本文档是 AI 协作开发的核心依据，描述了系统的 MVC 架构、业务逻辑映射及开发规范。

## 1. 系统架构 (Architecture)

LinkSell 2.0 采用严格的 **MVC (Model-View-Controller)** 分层架构，确保逻辑与展示彻底分离。

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
*   **职责**: 仅负责渲染界面和捕获用户事件，**严禁**包含业务逻辑。
*   **交互模式**:
    *   **Popover**: 集成音频上传/录制入口，悬浮于输入框上方。
    *   **Interleaved Reporting**: 报表卡片随对话流动态插入，非置顶。
    *   **Action Buttons**: 归档操作通过“保存/放弃”按钮触发，而非自然语言。

### 1.3 视图层 (View) - CLI (Terminal)
*   **文件**: `src/main.py`
*   **框架**: Typer + Rich
*   **职责**: 程序的入口点 + 命令行交互实现。
*   **逻辑**: 初始化 `LinkSellController`，根据 `--cli` 参数决定启动 GUI 还是 CLI 循环。

### 1.4 服务层 (Services)
*   **目录**: `src/services/`
*   **职责**: 无状态的底层 API 封装。
    *   `asr_service.py`: 封装 Seed ASR V3 协议 (Submit/Query)。
    *   `llm_service.py`: 封装 Volcengine Ark Runtime。

## 2. 核心工作流 (Workflow)

### 2.1 分析闭环 (The Analysis Loop)
1.  **输入**: 用户通过 Popover (GUI) 或 参数 (CLI) 提供音频/文本。
2.  **润色 (Polish)**: `Controller.polish()` 将口语转化为书面语。
3.  **分析 (Analyze)**: `Controller.analyze()` 提取 JSON 结构。
4.  **补全 (Completion)**:
    *   `Controller.get_missing_fields()` 扫描空值。
    *   UI 层根据队列逐个询问用户。
    *   `Controller.refine()` 写入补充值。
5.  **修订 (Modification)**:
    *   用户输入自然语言指令（如“把预算改成50万”）。
    *   `Controller.update()` 调用 LLM 修改 JSON。
    *   UI 重新渲染新报表。
6.  **归档 (Save)**:
    *   GUI: 点击按钮 -> `Controller.save()`。
    *   CLI: 输入关键词 -> `Controller.save()`。

## 3. 交互规范 (Interaction Guidelines)

### 3.1 智能秘书人格
*   **语料库**: 所有界面提示语**必须**从 `config/ui_templates.json` 加载，严禁 Hardcode。
*   **称呼**: 严禁使用“老板”等江湖气称呼，统一使用“您”或无主语的专业表达。
*   **风格**: 温婉、专业、高效。

### 3.2 报表展示
*   **GUI**: 使用 `st.container(border=True)` 包裹，信息分栏展示（基础信息、客户/商机分栏、关键点/待办分栏）。
*   **CLI**: 使用 Rich `Table` 和 `Tree` 组件，保持相同的分栏逻辑。
*   **视觉流**: 报表应紧随用户的修改操作出现，形成“操作-反馈”闭环。

## 4. 关键配置 (Configuration)
*   **ASR 模型**: 必须锁定为 `volc.seedasr.auc` (Seed ASR 大模型)。
*   **LLM 模型**: 通过 `config.ini` 中的 `analyze_endpoint` 指定。
*   **数据路径**: 默认为 `data/sales_data.json`，自动生成 `data/records/` 备份。

## 5. 开发禁忌 (Dont's)
1.  **禁止** 在 `app.py` 或 `main.py` 中直接调用 `requests` 或 `volcengine` SDK。必须通过 `Controller`。
2.  **禁止** 在 GUI 中使用侧边栏 (`st.sidebar`) 放置核心功能（如录音）。
3.  **禁止** 混合使用“文本确认保存”和“按钮确认保存”——GUI 只认按钮。
