"""
LinkSell GUI 主程序 (Streamlit)

职责：
- 提供 Web 图形交互界面 (Streamlit)
- 处理用户输入 (文本/语音) 与结果展示
- 管理会话级状态 (Session State)

特点：
- **Pure UI**: 纯 UI 层，不包含业务逻辑，仅负责渲染 Engine 的输出
- **Immediate Mode**: 采用立即渲染模式，每次交互重新运行脚本
- **Hot Reload**: 包含模块热重载机制，确保底层服务修改即时生效
"""

import streamlit as st
import sys
import time
import json
import importlib
from pathlib import Path

# [环境配置] 将项目根目录加入 Python 搜索路径
# 确保在任意目录下运行 `streamlit run src/gui/gui.py` 都能找到包
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

# [热重载机制] (Hot Reload) - 关键技巧！
# Streamlit 默认会缓存导入的模块。当我们修改底层逻辑 (ASR/Controller) 时，
# 必须显式 reload，否则 UI 还会跑旧代码。
import src.services.asr_service
importlib.reload(src.services.asr_service) # 确保 ASR 修复立即生效
import src.core.controller
importlib.reload(src.core.controller)
import src.core.conversational_engine
importlib.reload(src.core.conversational_engine)

from src.core.conversational_engine import ConversationalEngine

# [页面配置] 设置浏览器标签页标题和图标
st.set_page_config(page_title="LinkSell 智能销售助手", page_icon="💼", layout="wide")

# ==================== 状态管理 (Session State) ====================
# Streamlit 每次刷新都会重置变量，必须把持久化数据存在 session_state 里

# 1. 初始化对话引擎 (单例模式)
if "engine" not in st.session_state:
    st.session_state.engine = ConversationalEngine()

# 2. 初始化聊天记录列表
if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "有什么需要帮忙的么？您可以查看、创建或修改商机。"
    }]

# ==================== 辅助函数 (Helpers) ====================

def add_ai_message(content: str):
    """[UI组件] 向聊天历史添加 AI 的纯文本回复"""
    st.session_state.messages.append({"role": "assistant", "content": content})


def add_user_message(content: str):
    """[UI组件] 向聊天历史添加用户的指令"""
    st.session_state.messages.append({"role": "user", "content": content})


def display_report(report_text: str):
    """
    [UI组件] 渲染复杂的商机详情报告
    使用 Expander (折叠面板) 避免占用过多垂直空间
    """
    if report_text:
        with st.expander("📄 详情报告", expanded=True):
            st.markdown(report_text)


def process_user_input(user_input: str):
    """
    [核心逻辑] 处理用户的一次完整交互
    流程: 显示用户输入 -> 调用引擎 -> 处理返回结果 -> 刷新页面
    """
    if not user_input.strip():
        return
    
    # 1. 立即在界面展示用户输入
    add_user_message(user_input)
    with st.chat_message("user", avatar="👤"):
        st.write(user_input)
    
    # 2. 调用后端大脑处理 (显示加载转圈圈)
    with st.spinner("🤔 正在处理..."):
        result = st.session_state.engine.handle_user_input(user_input)
    
    # 3. 解析并存储返回结果
    
    # (A) 核心文本回复
    if result.get("message"):
        add_ai_message(result["message"])
    
    # (B) 自动匹配提示 (Context Lock)
    if result.get("auto_matched"):
        add_ai_message("💡 (系统已根据上下文自动锁定当前商机)")

    # (C) 结构化详情报告 (Markdown)
    # 将报告作为特殊类型的消息存入历史，以便后续重新渲染
    if result.get("report_text"):
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "report", 
            "report_text": result["report_text"]
        })
    
    # 4. 强制刷新页面 (Rerun)
    # 这一步是 Streamlit 的精髓：刷新后，代码从头运行，利用 session_state 中的新数据渲染界面
    st.rerun()


def handle_voice_input(audio_data):
    """
    [核心逻辑] 处理语音录入
    流程: 保存临时文件 -> 调用 ASR 识别 -> 转给 process_user_input
    """
    if not audio_data: return
    
    # 生成临时文件路径 (带时间戳防冲突)
    tmp_path = Path(f"data/tmp/voice_{int(time.time())}.wav")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 保存录音数据
    with open(tmp_path, "wb") as f:
        f.write(audio_data.getbuffer())
    
    with st.spinner("🎙️ 正在识别语音..."):
        try:
            # 调用 ASR 服务 (已通过 Engine 封装)
            res = st.session_state.engine.handle_voice_input(str(tmp_path))
            
            if res.get("status") == "success":
                # 识别成功，直接把识别出的文本丢给文本处理流程
                process_user_input(res.get("text", ""))
        except Exception as e:
            st.error(f"语音识别失败: {e}")


# ==================== 主界面布局 (Main Layout) ====================

# [区域 1] 顶部标题栏
# 使用 columns 实现 Logo 和 Title 并排
logo_path = Path("assets/icon/comlan.png")
col_logo, col_title = st.columns([1, 6])

with col_logo:
    if logo_path.exists(): st.image(str(logo_path), width=100)
with col_title:
    st.title("LinkSell 智能销售助手")

st.divider() # 分割线

# [区域 2] 聊天历史回放区
# Streamlit 每次刷新都会清空屏幕，必须遍历 session_state 重绘所有消息
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.write(message["content"])
    else:
        # 特殊消息类型：报告
        if message["content"] == "report":
            with st.chat_message("assistant", avatar="📊"):
                display_report(message.get("report_text"))
        # 普通文本消息
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(message["content"])

# [区域 3] 底部输入区
# 聊天输入框 (chat_input) 固定在底部
st.chat_input("请输入您的指令 (例如: 查看沈阳项目, 预算改为50万...)", key="chat_input", on_submit=lambda: process_user_input(st.session_state.chat_input))

# [区域 4] 辅助工具栏 (录音/上传)
# 放在输入框下方，提供多模态输入
col_mic, col_upload, _ = st.columns([1, 1.2, 10])

with col_mic:
    # 录音按钮 (Audio Input)
    voice_audio = st.audio_input("🎙️", label_visibility="collapsed", key="mic_btn")
    if voice_audio: handle_voice_input(voice_audio)

with col_upload:
    # 文件上传按钮
    uploaded_file = st.file_uploader("📁", type=["wav", "mp3"], label_visibility="collapsed")
    if uploaded_file:
        # [防抖动] 避免每次刷新重复处理同一个文件
        file_key = f"processed_{uploaded_file.name}_{uploaded_file.size}"
        if file_key not in st.session_state:
            handle_voice_input(uploaded_file)
            st.session_state[file_key] = True # 标记为已处理
