import streamlit as st
import sys
import time
import json
import copy
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
        margin-bottom: 20px;
    }
    .stChatMessage {
        padding: 10px;
    }
    /* Hide the default chat input padding if any */
    [data-testid="stChatInput"] {
        display: none;
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
    st.session_state.missing_fields_queue = []

if "text_input_val" not in st.session_state:
    st.session_state.text_input_val = ""

# --- Helper Functions ---

def render_report(data):
    """Renders the sales data nicely in Streamlit."""
    if not data: return
    with st.container(border=True):
        st.markdown("### 📊 销售小纪")
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1: st.markdown(f"**🗣️ 类型**: {data.get('record_type', 'N/A')}")
        with c2: st.markdown(f"**👨‍💼 销售**: {data.get('sales_rep', 'N/A')}")
        with c3:
            sentiment = data.get('sentiment', '未知')
            color = "green" if "积极" in str(sentiment) else "red" if "消极" in str(sentiment) else "orange"
            st.markdown(f"**😊 态度**: :{color}[{sentiment}]")
        st.info(f"**📝 核心摘要**: {data.get('summary', '暂无')}", icon="ℹ️")
        st.divider()
        col_cust, col_opp = st.columns(2)
        with col_cust:
            st.markdown("#### 👤 客户画像")
            cust = data.get("customer_info", {})
            if cust:
                st.markdown(f"- **姓名**: {cust.get('name', 'N/A')}")
                st.markdown(f"- **公司**: {cust.get('company', 'N/A')}")
                st.markdown(f"- **职位**: {cust.get('role', 'N/A')}")
                st.markdown(f"- **联系**: {cust.get('contact', 'N/A')}")
            else: st.caption("未提取到有效信息")
        with col_opp:
            st.markdown("#### 💰 商机概览")
            opp = data.get("project_opportunity", {})
            if opp:
                proj_name = opp.get("project_name", "未命名项目")
                is_new = "✨ 新项目" if opp.get("is_new_project") else "🔄 既有项目"
                st.markdown(f"**{proj_name}** ({is_new})")
                st.markdown(f"- **阶段**: {opp.get('stage', '未知')}")
                st.markdown(f"- **预算**: :green[{opp.get('budget', '未知')}]")
                st.markdown(f"- **时间**: {opp.get('timeline', '未知')}")
                st.markdown(f"- **流程**: {opp.get('procurement_process', '未知')}")
                st.markdown(f"- **付款**: {opp.get('payment_terms', '未知')}")
                st.markdown("**⚔️ 竞争对手**")
                comps = opp.get("competitors", [])
                if comps:
                    for c in comps: st.markdown(f"  - {c}")
                else: st.caption("  无明确竞争对手")
                st.markdown("**🛠️ 我方参与技术**")
                techs = opp.get("tech_stack", [])
                if techs:
                    for t in techs: st.markdown(f"  - {t}")
                else: st.caption("  未指定")
            else: st.caption("暂未发现明确商机")
        st.divider()
        c_kp, c_act = st.columns(2)
        with c_kp:
            st.markdown("#### 📌 关键点")
            kp = data.get("key_points", [])
            if kp:
                for idx, p in enumerate(kp, 1): st.markdown(f"{idx}. {p}")
            else: st.caption("无")
        with c_act:
            st.markdown("#### ✅ 待办事项")
            act = data.get("action_items", [])
            if act:
                for idx, a in enumerate(act, 1): st.markdown(f"{idx}. {a}")
            else: st.caption("无")

def display_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("type") == "report": render_report(msg["data"])
            else: st.markdown(msg["content"])

def add_user_message(content):
    st.session_state.messages.append({"role": "user", "content": content})

def add_ai_message(content):
    st.session_state.messages.append({"role": "assistant", "content": content})

def add_report_message(data):
    snapshot = copy.deepcopy(data)
    st.session_state.messages.append({"role": "assistant", "type": "report", "data": snapshot})

def reset_state():
    """Resets the app to initial state."""
    st.session_state.sales_data = None
    st.session_state.step = "input"
    st.session_state.missing_fields_queue = []
    st.session_state.messages = [{"role": "assistant", "content": "你好！我是您的销售助手。请上传录音文件或直接粘贴对话文本，我来帮您整理。"}]
    st.rerun()

def handle_logic(prompt):
    """Unified logic handler for user input."""
    if not prompt or not prompt.strip(): return

    if st.session_state.step == "input":
        with st.spinner("正在润色并分析..."):
            polished = st.session_state.controller.polish(prompt)
            data = st.session_state.controller.analyze(polished)
            st.session_state.sales_data = data
            add_report_message(data)
            missing_map = st.session_state.controller.get_missing_fields(data)
            if missing_map:
                st.session_state.step = "missing_fields"
                st.session_state.missing_fields_queue = list(missing_map.items())
                key, (name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"我注意到 **{name}** 还没填，需要补充吗？(没有请回 '无')")
            else:
                st.session_state.step = "review"
                add_ai_message("分析完成！请查阅上方的销售小纪。有需要修改的吗？(无误请点击下方按钮保存)")

    elif st.session_state.step == "missing_fields":
        if st.session_state.missing_fields_queue:
            curr_key, (curr_name, _) = st.session_state.missing_fields_queue[0]
            user_input = prompt.strip()
            is_skip = user_input in ["无", "没有", "跳过", "不知", "不知道"]
            if not is_skip:
                with st.spinner(f"正在写入 {curr_name}..."):
                    st.session_state.sales_data = st.session_state.controller.refine(st.session_state.sales_data, {curr_key: prompt})
                feedback_prefix = f"✅ 已补充 **{curr_name}**。"
                add_report_message(st.session_state.sales_data)
            else: feedback_prefix = "👌 已跳过。"
            st.session_state.missing_fields_queue.pop(0)
            if st.session_state.missing_fields_queue:
                next_key, (next_name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"{feedback_prefix} 另外，我注意到 **{next_name}** 也没填，需要补充吗？(没有请回 '无')")
            else:
                st.session_state.step = "review"
                add_ai_message(f"{feedback_prefix} 核对完毕！请查看报表。确认无误请点击 **'确认保存'**，或告诉我修改意见。")

    elif st.session_state.step == "review":
        with st.spinner("正在修改..."):
            st.session_state.sales_data = st.session_state.controller.update(st.session_state.sales_data, prompt)
            add_report_message(st.session_state.sales_data)
            add_ai_message("修改完成，请查看结果。确认无误请点击 **'确认保存'**。")

# --- Header ---
logo_path = Path("assents/icon/comlan.png")
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if logo_path.exists(): st.image(str(logo_path), width=120)
with col_title: st.title("LinkSell 智能销售助手")

# --- Chat History ---
display_chat()

# --- BOTTOM UI: Save Buttons (Conditional) ---
if st.session_state.step == "review":
    with st.container():
        b1, b2, b3 = st.columns([1, 1, 4])
        with b1:
            if st.button("✅ 确认保存", type="primary", use_container_width=True):
                with st.spinner("存档中..."):
                    rid, _ = st.session_state.controller.save(st.session_state.sales_data)
                    st.toast(f"保存成功！ID: {rid}")
                    time.sleep(1)
                    reset_state()
        with b2:
            if st.button("❌ 放弃", use_container_width=True):
                reset_state()
        with b3: st.caption("👆 请确认保存，或在下方输入修改意见")

# --- BOTTOM UI: Unified Input Bar ---
with st.container():
    # Adjusted widths to give audio_input enough room [Upload, Text, Mic, Send]
    col_plus, col_input, col_mic, col_send = st.columns([0.8, 6.0, 2.0, 1.2])
    
    with col_plus:
        pop_up = st.popover("➕", use_container_width=True, help="上传音频文件")
        with pop_up:
            st.markdown("##### 📁 上传音频文件")
            f = st.file_uploader("选择文件", type=["wav", "mp3"], label_visibility="collapsed")
            if f:
                if st.button("🚀 识别并填入", type="primary", use_container_width=True):
                    tmp = Path(f"data/tmp/{f.name}")
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp, "wb") as _f: _f.write(f.getbuffer())
                    st.session_state.transcribe_path = tmp
                    st.session_state.transcribing = True
                    st.rerun()

    with col_input:
        # Use session_state to allow both manual typing and ASR filling
        user_text = st.text_input(
            "对话框", 
            value=st.session_state.get("text_input_val", ""),
            placeholder="输入内容或修改意见...", 
            label_visibility="collapsed",
            key="main_text_input"
        )
        # Update the state if user types manually
        st.session_state.text_input_val = user_text

    with col_mic:
        # Direct audio input without popover
        audio_data = st.audio_input("录音", label_visibility="collapsed", key="mic_input")
        if audio_data:
            # We use a hash or timestamp to avoid re-transcribing the same audio on every rerun
            audio_id = hash(audio_data.getvalue())
            if st.session_state.get("last_audio_id") != audio_id:
                with st.spinner("🎧"):
                    tmp = Path(f"data/tmp/mic_{int(time.time())}.wav")
                    tmp.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp, "wb") as _f: _f.write(audio_data.getbuffer())
                    
                    try:
                        text = st.session_state.controller.transcribe(tmp)
                        if text:
                            st.session_state.text_input_val = text
                            st.session_state.last_audio_id = audio_id
                            st.rerun()
                    except Exception as e:
                        st.error(f"识别失败: {e}")

    with col_send:
        send_clicked = st.button("🚀", type="primary", use_container_width=True, help="发送文字")

    # Handle text submission
    if send_clicked and st.session_state.text_input_val:
        final_prompt = st.session_state.text_input_val
        add_user_message(final_prompt)
        handle_logic(final_prompt)
        # Clear state after sending
        st.session_state.text_input_val = ""
        st.rerun()

# --- Handle Background Transcription ---
if st.session_state.get("transcribing"):
    path = st.session_state.pop("transcribe_path")
    st.session_state.pop("transcribing")
    with st.spinner("正在转写..."):
        try:
            text = st.session_state.controller.transcribe(path)
            if text:
                add_user_message(f"【语音内容】: {text}")
                handle_logic(text)
                st.rerun()
            else: st.error("语音识别失败")
        except Exception as e: st.error(f"Error: {e}")
