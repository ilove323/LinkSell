# LinkSell AI 上下文文档 (LLM Context)

本文档为 LinkSell 项目的技术架构、逻辑映射及开发规范，供 AI 协作者参考。

## 1. 系统架构
LinkSell 采用典型的 **MVC (Model-View-Controller)** 架构：
*   **Controller (`src/core/controller.py`)**: 系统的“大脑”，封装了 ASR、LLM、业务校验及持久化逻辑。
*   **View - GUI (`src/gui/app.py`)**: 基于 Streamlit 实现的现代化聊天界面。
*   **View - CLI (`src/main.py`)**: 基于 Typer 实现的经典命令行界面。
*   **Services (`src/services/`)**: 底层服务接入层，负责与火山引擎 API 通讯。

## 2. 核心工作流
1.  **输入层**: 支持音频（文件/麦克风）或纯文本。音频通过 `asr_service` 转录。
2.  **处理层**: 
    *   `polish_text`: LLM 预处理，口语转书面。
    *   `analyze_text`: LLM 结构化提取 7+ 维度信息。
    *   `get_missing_fields`: 自动扫描 `project_opportunity` 中的核心字段。
3.  **交互层**: 
    *   **补全**: 提示用户补充缺失信息。
    *   **修订**: 用户通过自然语言指令（如“修改预算为50万”）驱动 `update_sales_data`。
4.  **持久化**: 保存至本地 JSON。

## 3. 核心交互组件：智能秘书
系统通过 `config/ui_templates.json` 驱动。每次输出均从语料库中随机抽取，保持“秘书”人格的一致性。
**严禁** 在代码及语料库中使用“老板”称呼，应使用专业、温婉的商务用语。

## 4. 开发规范
*   **双模运行**: `main.py` 默认启动 GUI，带 `--cli` 参数启动 CLI。
*   **逻辑解耦**: 所有的业务逻辑 **必须** 写在 `LinkSellController` 中，界面层只负责展示与调用。
*   **语言**: 文档、注释、提示语统一使用简体中文。
*   **鉴权**: ASR 使用 Access Token，LLM 使用 API Key。

## 5. 关键配置
*   `ASR_RESOURCE_ID`: 锁定为 `volc.seedasr.auc`。
*   `DEBUG`: 通过 `--debug` 开启，显示底层 JSON 原文及任务 ID。
