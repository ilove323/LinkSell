import streamlit as st
import sys
import time
import json
from pathlib import Path

# Add project root to path so we can import src
root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from src.core.controller import LinkSellController

# --- Page Config ---
st.set_page_config(page_title="LinkSell 智能销售助手", page_icon="💼", layout="wide")

# --- Styles ---
st.markdown("""
<style>
    .report-container {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #dcdcdc;
    }
    .stChatMessage {
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- Init Controller & State ---
if "controller" not in st.session_state:
    try:
        st.session_state.controller = LinkSellController()
    except Exception as e:
        st.error(f"Failed to initialize system: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "你好！我是您的销售助手。请上传录音文件或直接粘贴对话文本，我来帮您整理。"}]

if "sales_data" not in st.session_state:
    st.session_state.sales_data = None

if "step" not in st.session_state:
    st.session_state.step = "input" # input, missing_fields, review

if "missing_fields_queue" not in st.session_state:
    st.session_state.missing_fields_queue = [] # List of (key, name) to ask

# --- Helper Functions ---
def display_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

def add_user_message(content):
    st.session_state.messages.append({"role": "user", "content": content})
    with st.chat_message("user"):
        st.markdown(content)

def add_ai_message(content):
    st.session_state.messages.append({"role": "assistant", "content": content})
    with st.chat_message("assistant"):
        st.markdown(content)

def render_report(data):
    """Renders the sales data nicely in Streamlit."""
    if not data: return
    
    with st.expander("📊 销售小纪 (点击展开/收起)", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**🗣️ 类型**: {data.get('record_type', 'N/A')}")
            st.markdown(f"**👨‍💼 销售**: {data.get('sales_rep', 'N/A')}")
        with col2:
            st.markdown(f"**😊 态度**: {data.get('sentiment', 'N/A')}")
        
        st.markdown("---")
        st.markdown(f"**📝 摘要**: {data.get('summary', '暂无')}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("👤 客户画像")
            cust = data.get("customer_info", {})
            st.write(cust)
        with c2:
            st.subheader("💰 商机详情")
            opp = data.get("project_opportunity", {})
            st.write(opp)
            
        st.subheader("📌 关键点 & ✅ 待办")
        kc1, kc2 = st.columns(2)
        with kc1:
            for p in data.get("key_points", []):
                st.markdown(f"- {p}")
        with kc2:
            for a in data.get("action_items", []):
                st.markdown(f"- {a}")

# --- Main Interaction Logic ---

# Sidebar for Audio Upload
with st.sidebar:
    st.title("🎙️ 录音上传")
    audio_file = st.file_uploader("上传 .wav, .mp3", type=["wav", "mp3"])
    if audio_file and st.session_state.step == "input":
        if st.button("开始识别音频"):
            # Save tmp file
            tmp_path = Path(f"data/tmp/{audio_file.name}")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, "wb") as f:
                f.write(audio_file.getbuffer())
            
            with st.spinner("正在听..."):
                try:
                    text = st.session_state.controller.transcribe(tmp_path)
                    if text:
                        add_user_message(f"【音频内容】: {text}")
                        # Proceed to analysis logic directly
                        st.session_state.processing_text = text
                        st.rerun()
                    else:
                        st.error("识别失败")
                except Exception as e:
                    st.error(f"Error: {e}")

# Chat Area
display_chat()

# Logic Processor (Runs on rerun or input)
if prompt := st.chat_input("输入对话内容..."):
    add_user_message(prompt)
    
    # CASE 1: INPUT STEP
    if st.session_state.step == "input":
        with st.spinner("正在润色并分析..."):
            # 1. Polish
            polished = st.session_state.controller.polish(prompt)
            # 2. Analyze
            data = st.session_state.controller.analyze(polished)
            st.session_state.sales_data = data
            
            # 3. Check Missing
            missing_map = st.session_state.controller.get_missing_fields(data)
            if missing_map:
                st.session_state.step = "missing_fields"
                st.session_state.missing_fields_queue = list(missing_map.items())
                
                # Ask first question
                key, (name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"我注意到 **{name}** 还没填，需要补充吗？(没有请回 '无')")
            else:
                st.session_state.step = "review"
                add_ai_message("分析完成！请查阅下方的销售小纪。有需要修改的吗？(无误请回复 '保存')")
        st.rerun()

    # CASE 2: MISSING FIELDS STEP
    elif st.session_state.step == "missing_fields":
        # Process answer for current missing field
        if st.session_state.missing_fields_queue:
            key, (name, _) = st.session_state.missing_fields_queue[0]
            
            if prompt.strip() not in ["无", "没有", "跳过"]:
                with st.spinner("正在整合补充信息..."):
                    # Refine data
                    st.session_state.sales_data = st.session_state.controller.refine(
                        st.session_state.sales_data, {key: prompt}
                    )
            
            # Pop queue
            st.session_state.missing_fields_queue.pop(0)
            
            # Ask next or Finish
            if st.session_state.missing_fields_queue:
                key, (name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"好的。那 **{name}** 呢？(没有请回 '无')")
            else:
                st.session_state.step = "review"
                add_ai_message("信息补全完毕！请查看最终报表。确认无误请回复 **'保存'**，或直接告诉我修改意见。")
        st.rerun()

    # CASE 3: REVIEW STEP
    elif st.session_state.step == "review":
        if prompt.strip() in ["保存", "save", "s", "确认", "没问题", "ok"]:
            with st.spinner("正在归档..."):
                rid, path = st.session_state.controller.save(st.session_state.sales_data)
                add_ai_message(f"✅ 保存成功！记录 ID: {rid}。文件已备份至 `{path}`。")
                st.session_state.step = "input" # Reset
                st.session_state.sales_data = None
        elif prompt.strip() in ["放弃", "取消", "d"]:
            add_ai_message("已放弃本次记录。")
            st.session_state.step = "input"
            st.session_state.sales_data = None
        else:
            # Assume modification instruction
            with st.spinner("正在根据您的指令修改..."):
                st.session_state.sales_data = st.session_state.controller.update(
                    st.session_state.sales_data, prompt
                )
                add_ai_message("修改已完成，请查看最新结果。")
        st.rerun()

# --- Render Report if Data Exists ---
if st.session_state.sales_data:
    render_report(st.session_state.sales_data)

# --- Handle "processing_text" trigger from Audio ---
if "processing_text" in st.session_state:
    text = st.session_state.pop("processing_text")
    # Simulate text input workflow
    with st.spinner("正在润色并分析..."):
        polished = st.session_state.controller.polish(text)
        data = st.session_state.controller.analyze(polished)
        st.session_state.sales_data = data
        
        missing_map = st.session_state.controller.get_missing_fields(data)
        if missing_map:
            st.session_state.step = "missing_fields"
            st.session_state.missing_fields_queue = list(missing_map.items())
            key, (name, _) = st.session_state.missing_fields_queue[0]
            add_ai_message(f"我注意到 **{name}** 还没填，需要补充吗？(没有请回 '无')")
        else:
            st.session_state.step = "review"
            add_ai_message("分析完成！请查阅下方的销售小纪。有需要修改的吗？(无误请回复 '保存')")
    st.rerun()
