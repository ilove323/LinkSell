"""
LinkSell GUI 主程序 (Streamlit)

职责：
- 提供用户界面
- 接收用户输入  
- 调用对话引擎处理逻辑
- 展示对话引擎返回的结果 (纯文本/Markdown 渲染)

特点：
- 纯UI层，不包含业务逻辑
- 无状态渲染：仅展示 Engine 给出的 message 和 report_text
"""

import streamlit as st
import sys
import time
import json
import importlib
from pathlib import Path

# Add project root to path
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

# 强制重载核心模块（确保代码更新即时生效）
import src.core.controller
importlib.reload(src.core.controller)
import src.core.conversational_engine
importlib.reload(src.core.conversational_engine)

from src.core.conversational_engine import ConversationalEngine

# ==================== Page Config ====================
st.set_page_config(page_title="LinkSell 智能销售助手", page_icon="💼", layout="wide")

# ==================== Init Session State ====================
if "engine" not in st.session_state:
    st.session_state.engine = ConversationalEngine()

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "有什么需要帮忙的么？您可以查看、创建或修改商机。"
    }]

# ==================== Helper Functions ====================

def add_ai_message(content: str):
    """添加AI消息到历史"""
    st.session_state.messages.append({"role": "assistant", "content": content})


def add_user_message(content: str):
    """添加用户消息到历史"""
    st.session_state.messages.append({"role": "user", "content": content})


def display_report(report_text: str):
    """渲染商机详情报告"""
    if report_text:
        with st.expander("📄 详情报告", expanded=True):
            st.markdown(report_text)


def process_user_input(user_input: str):
    """处理用户输入的主流程"""
    if not user_input.strip():
        return
    
    # 1. 立即展示用户输入
    add_user_message(user_input)
    with st.chat_message("user", avatar="👤"):
        st.write(user_input)
    
    # 2. 调用大脑处理
    with st.spinner("🤔 正在处理..."):
        result = st.session_state.engine.handle_user_input(user_input)
    
    # 3. 处理返回结果
    # 核心文本消息
    if result.get("message"):
        add_ai_message(result["message"])
    
    # 自动匹配提醒
    if result.get("auto_matched"):
        add_ai_message("💡 (系统已根据上下文自动锁定当前商机)")

    # 结构化报告
    if result.get("report_text"):
        st.session_state.messages.append({
            "role": "assistant", 
            "content": "report", 
            "report_text": result["report_text"]
        })
    
    # 4. 刷新页面同步历史
    st.rerun()


def handle_voice_input(audio_data):
    """处理语音录入"""
    if not audio_data: return
    
    # 保存临时文件
    tmp_path = Path(f"data/tmp/voice_{int(time.time())}.wav")
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(audio_data.getbuffer())
    
    with st.spinner("🎙️ 正在识别语音..."):
        try:
            res = st.session_state.engine.handle_voice_input(str(tmp_path))
            if res.get("status") == "success":
                process_user_input(res.get("text", ""))
        except Exception as e:
            st.error(f"语音识别失败: {e}")


# ==================== Main UI Layout ====================

# 1. 标题栏
logo_path = Path("assets/icon/comlan.png")
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if logo_path.exists(): st.image(str(logo_path), width=100)
with col_title:
    st.title("LinkSell 智能销售助手")

st.divider()

# 2. 聊天历史展示
for message in st.session_state.messages:
    if message["role"] == "user":
        with st.chat_message("user", avatar="👤"):
            st.write(message["content"])
    else:
        if message["content"] == "report":
            with st.chat_message("assistant", avatar="📊"):
                display_report(message.get("report_text"))
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(message["content"])

# 3. 输入区域
st.chat_input("请输入您的指令 (例如: 查看沈阳项目, 预算改为50万...)", key="chat_input", on_submit=lambda: process_user_input(st.session_state.chat_input))

# 4. 辅助工具栏 (录音/上传)
col_mic, col_upload, _ = st.columns([1, 1.2, 10])
with col_mic:
    voice_audio = st.audio_input("🎙️", label_visibility="collapsed", key="mic_btn")
    if voice_audio: handle_voice_input(voice_audio)

with col_upload:
    uploaded_file = st.file_uploader("📁", type=["wav", "mp3"], label_visibility="collapsed")
    if uploaded_file:
        # 简单避免重复处理
        file_key = f"processed_{uploaded_file.name}_{uploaded_file.size}"
        if file_key not in st.session_state:
            handle_voice_input(uploaded_file)
            st.session_state[file_key] = True