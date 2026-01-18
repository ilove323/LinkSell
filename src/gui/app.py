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

def render_report(data):
    """
    Renders the sales data nicely in Streamlit, mimicking the CLI layout.
    """
    if not data: return
    
    # container with border
    with st.container(border=True):
        st.markdown("### 📊 销售小纪")
        
        # 1. Basic Info Row
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            st.markdown(f"**🗣️ 类型**: {data.get('record_type', 'N/A')}")
        with c2:
            st.markdown(f"**👨‍💼 销售**: {data.get('sales_rep', 'N/A')}")
        with c3:
            sentiment = data.get('sentiment', '未知')
            color = "green" if "积极" in str(sentiment) else "red" if "消极" in str(sentiment) else "orange"
            st.markdown(f"**😊 态度**: :{color}[{sentiment}]")
            
        st.info(f"**📝 核心摘要**: {data.get('summary', '暂无')}", icon="ℹ️")
        
        st.divider()

        # 2. Customer & Opportunity Columns
        col_cust, col_opp = st.columns(2)
        
        with col_cust:
            st.markdown("#### 👤 客户画像")
            cust = data.get("customer_info", {})
            if cust:
                st.markdown(f"- **姓名**: {cust.get('name', 'N/A')}")
                st.markdown(f"- **公司**: {cust.get('company', 'N/A')}")
                st.markdown(f"- **职位**: {cust.get('role', 'N/A')}")
                st.markdown(f"- **联系**: {cust.get('contact', 'N/A')}")
            else:
                st.caption("未提取到有效信息")

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
                else:
                    st.caption("  无明确竞争对手")
                    
                st.markdown("**🛠️ 我方参与技术**")
                techs = opp.get("tech_stack", [])
                if techs:
                    for t in techs: st.markdown(f"  - {t}")
                else:
                    st.caption("  未指定")
            else:
                st.caption("暂未发现明确商机")

        st.divider()

        # 3. Key Points & Actions
        c_kp, c_act = st.columns(2)
        with c_kp:
            st.markdown("#### 📌 关键点")
            kp = data.get("key_points", [])
            if kp:
                for idx, p in enumerate(kp, 1):
                    st.markdown(f"{idx}. {p}")
            else:
                st.caption("无")
        
        with c_act:
            st.markdown("#### ✅ 待办事项")
            act = data.get("action_items", [])
            if act:
                for idx, a in enumerate(act, 1):
                    st.markdown(f"{idx}. {a}")
            else:
                st.caption("无")

def display_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("type") == "report":
                render_report(msg["data"])
            else:
                st.markdown(msg["content"])

def add_user_message(content):
    st.session_state.messages.append({"role": "user", "content": content})

def add_ai_message(content):
    st.session_state.messages.append({"role": "assistant", "content": content})

def add_report_message(data):
    # Snapshot data
    snapshot = copy.deepcopy(data)
    st.session_state.messages.append({"role": "assistant", "type": "report", "data": snapshot})

def reset_state():
    """Resets the app to initial state."""
    st.session_state.sales_data = None
    st.session_state.step = "input"
    st.session_state.missing_fields_queue = []
    st.session_state.messages = [{"role": "assistant", "content": "你好！我是您的销售助手。请上传录音文件或直接粘贴对话文本，我来帮您整理。"}]
    st.rerun()

# --- Header (Logo & Title) ---
logo_path = Path("assents/icon/comlan.png")
col_logo, col_title = st.columns([1, 15])
with col_logo:
    if logo_path.exists():
        st.image(str(logo_path), width=50)
with col_title:
    st.title("LinkSell 智能销售助手")

# --- Main Layout: Chat History ---
# Using a container for chat history to keep it organized
chat_container = st.container()
with chat_container:
    display_chat()

# --- Input Area (Pinned to Bottom Logic) ---

# 1. Audio/File Popover (Only in Input Step)
if st.session_state.step == "input":
    # Use columns to align the popover nicely above the chat input
    c1, c2 = st.columns([0.85, 0.15])
    with c2:
        popover = st.popover("➕ 语音/文件", use_container_width=True)
        with popover:
            tab1, tab2 = st.tabs(["📁 上传", "🎤 录音"])
            with tab1:
                audio_file = st.file_uploader("文件", type=["wav", "mp3"], key="file_up", label_visibility="collapsed")
                if audio_file:
                    if st.button("开始识别", key="btn_trans_file"):
                        tmp_path = Path(f"data/tmp/{audio_file.name}")
                        tmp_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(tmp_path, "wb") as f:
                            f.write(audio_file.getbuffer())
                        st.session_state.transcribing = True
                        st.session_state.transcribe_path = tmp_path
                        st.rerun()
            with tab2:
                audio_mic = st.audio_input("录音", label_visibility="collapsed")
                if audio_mic:
                    timestamp = int(time.time())
                    tmp_path = Path(f"data/tmp/mic_{timestamp}.wav")
                    tmp_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(tmp_path, "wb") as f:
                        f.write(audio_mic.getbuffer())
                    st.session_state.transcribing = True
                    st.session_state.transcribe_path = tmp_path
                    st.rerun()

# 2. Review Action Buttons (Only in Review Step)
if st.session_state.step == "review":
    with st.container():
        col1, col2, col3 = st.columns([1, 1, 4])
        with col1:
            if st.button("✅ 确认保存", type="primary", use_container_width=True):
                with st.spinner("正在归档..."):
                    rid, path = st.session_state.controller.save(st.session_state.sales_data)
                    st.toast(f"保存成功！ID: {rid}", icon="✅")
                    time.sleep(1.5)
                    reset_state()
        with col2:
            if st.button("❌ 放弃/重来", use_container_width=True):
                st.toast("已放弃本次记录", icon="🗑️")
                time.sleep(1)
                reset_state()
        with col3:
            st.caption("👆 点击按钮保存，或在下方输入修改意见 👇")

# --- Logic Controllers ---

# Handle Transcription
if st.session_state.get("transcribing"):
    path = st.session_state.pop("transcribe_path")
    st.session_state.pop("transcribing")
    
    with st.spinner("正在听..."):
        try:
            text = st.session_state.controller.transcribe(path)
            if text:
                st.session_state.messages.append({"role": "user", "content": f"【音频内容】: {text}"})
                st.session_state.processing_text = text
                st.rerun()
            else:
                st.error("识别失败")
        except Exception as e:
            st.error(f"Error: {e}")

# Handle Text Input (Chat)
if prompt := st.chat_input("输入对话内容..."):
    add_user_message(prompt)
    
    # CASE 1: INPUT STEP
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
                add_ai_message("分析完成！请查阅上方的销售小纪。有需要修改的吗？(无误请点击上方按钮保存)")
        st.rerun()

    # CASE 2: MISSING FIELDS STEP
    elif st.session_state.step == "missing_fields":
        if st.session_state.missing_fields_queue:
            curr_key, (curr_name, _) = st.session_state.missing_fields_queue[0]
            
            user_input = prompt.strip()
            is_skip = user_input in ["无", "没有", "跳过", "不知", "不知道"]
            
            if not is_skip:
                with st.spinner(f"正在写入 {curr_name}..."):
                    st.session_state.sales_data = st.session_state.controller.refine(
                        st.session_state.sales_data, {curr_key: prompt}
                    )
                feedback_prefix = f"✅ 已补充 **{curr_name}**。"
                add_report_message(st.session_state.sales_data)
            else:
                feedback_prefix = "👌 已跳过。"
            
            st.session_state.missing_fields_queue.pop(0)
            
            if st.session_state.missing_fields_queue:
                next_key, (next_name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"{feedback_prefix} 另外，我注意到 **{next_name}** 也没填，需要补充吗？(没有请回 '无')")
            else:
                st.session_state.step = "review"
                add_ai_message(f"{feedback_prefix} 所有信息核对完毕！请查看最终报表。确认无误请点击上方 **'确认保存'** 按钮，如有修改意见请直接告诉我。")
        st.rerun()

    # CASE 3: REVIEW STEP
    elif st.session_state.step == "review":
        # Text input in review step = Modification Instruction
        with st.spinner("正在根据您的指令修改..."):
            st.session_state.sales_data = st.session_state.controller.update(
                st.session_state.sales_data, prompt
            )
            add_report_message(st.session_state.sales_data)
            add_ai_message("修改已完成，请查看最新结果。确认无误请点击 **'确认保存'**。")
        st.rerun()

# --- Handle "processing_text" trigger from Audio ---
if "processing_text" in st.session_state:
    text = st.session_state.pop("processing_text")
    with st.spinner("正在润色并分析..."):
        polished = st.session_state.controller.polish(text)
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
            add_ai_message("分析完成！请查阅上方的销售小纪。有需要修改的吗？(无误请点击上方按钮保存)")
    st.rerun()
