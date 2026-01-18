import streamlit as st
import sys
import time
import json
import copy
from pathlib import Path
import streamlit.components.v1 as components

# Add project root to path so we can import src
root = Path(__file__).parent.parent.parent
sys.path.append(str(root))

from src.core.controller import LinkSellController

# --- Page Config ---
st.set_page_config(page_title="LinkSell 智能销售助手", page_icon="💼", layout="wide")

# --- Header ---
logo_path = Path("assets/icon/comlan.png")
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if logo_path.exists(): st.image(str(logo_path), width=120)
with col_title:
    st.title("LinkSell 智能销售助手")

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
    .stTextArea textarea {
        border-radius: 10px;
    }
    /* 极致修剪语音按钮：确保只漏出麦克风图标 */
    [data-testid="stAudioInput"] {
        max-width: 100px !important;
        min-width: 100px !important;
        overflow: hidden !important;
        background: transparent !important;
        border: none !important;
    }
    /* 隐藏所有多余的控制面板、计时器、播放器 */
    [data-testid="stAudioInput"] section, 
    [data-testid="stAudioInput"] div[data-testid="stMarkdownContainer"],
    [data-testid="stAudioInput"] div[aria-label="Audio waveform"],
    [data-testid="stAudioInput"] button[aria-label="Play"],
    [data-testid="stAudioInput"] div:has(> button[aria-label="Play"]) {
        display: none !important;
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
    st.session_state.messages = [{"role": "assistant", "content": "有什么需要帮忙的么"}]

if "sales_data" not in st.session_state:
    st.session_state.sales_data = None

if "step" not in st.session_state:
    st.session_state.step = "input"

if "missing_fields_queue" not in st.session_state:
    st.session_state.missing_fields_queue = []

# Initialize text area state
if "chat_input_area" not in st.session_state:
    st.session_state["chat_input_area"] = ""

# --- TOP-LEVEL LOGIC (BEFORE UI RENDERING) ---

# 1. Handle Mic Result (Sync text to input area)
if "mic_input" in st.session_state and st.session_state.mic_input:
    audio_data = st.session_state.mic_input
    # Generate a unique key for this audio clip
    audio_id = hash(audio_data.getvalue())
    if st.session_state.get("last_processed_audio") != audio_id:
        tmp_path = Path(f"data/tmp/mic_{int(time.time())}.wav")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "wb") as _f: _f.write(audio_data.getbuffer())
        try:
            text = st.session_state.controller.transcribe(tmp_path)
            if text:
                # Direct injection into the widget's state
                st.session_state["chat_input_area"] = text
                st.session_state["last_processed_audio"] = audio_id
                st.rerun()
        except: pass

# 2. Handle File Upload Result
if st.session_state.get("transcribing") and st.session_state.get("transcribe_path"):
    path = st.session_state.pop("transcribe_path")
    st.session_state.pop("transcribing")
    try:
        text = st.session_state.controller.transcribe(path)
        if text:
            st.session_state["chat_input_area"] = text
            st.rerun()
    except: pass

# 3. Handle Logical Submission (Triggered by Button)
if st.session_state.get("final_send_btn"):
    prompt = st.session_state.get("chat_input_area", "").strip()
    if prompt:
        # Clear box and queue logic
        st.session_state["chat_input_area"] = "" 
        st.session_state["submit_trigger"] = prompt
        st.rerun()

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
    """只重置业务逻辑状态，保留聊天历史。"""
    st.session_state.sales_data = None
    st.session_state.step = "input"
    st.session_state.missing_fields_queue = []
    st.session_state["chat_input_area"] = ""
    
    # 重新说第一句话，但作为追加，而不是重置
    greeting = "有什么需要帮忙的么"
    add_ai_message(f"✅ 记录已存档！\n\n{greeting}")
    st.rerun()

def handle_logic(prompt):
    """Unified logic handler for user input."""
    if not prompt: return
    
    if st.session_state.step == "input":
        # 1. 识别意图
        intent = st.session_state.controller.get_intent(prompt)
        
        if intent == "QUERY":
            with st.spinner("正在查账..."):
                answer = st.session_state.controller.handle_query(prompt)
                add_ai_message(answer)
                return
        
        if intent == "OTHER":
            add_ai_message("抱歉哈，这事儿超出了我的业务范围。我是专门帮您整理销售记录的，或者是查查旧账，有什么这方面我能帮您的么？")
            return
            
        # 2. 如果是 ANALYZE，走原有逻辑
        with st.spinner("分析中..."):
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
                add_ai_message("分析完成！确认无误请点击下方按钮保存。")
    elif st.session_state.step == "missing_fields":
        if st.session_state.missing_fields_queue:
            curr_key, (curr_name, _) = st.session_state.missing_fields_queue[0]
            if prompt.strip() not in ["无", "没有", "跳过"]:
                st.session_state.sales_data = st.session_state.controller.refine(st.session_state.sales_data, {curr_key: prompt})
                feedback_prefix = f"✅ 已补充 **{curr_name}**。"
                add_report_message(st.session_state.sales_data)
            else: feedback_prefix = "👌 已跳过。"
            st.session_state.missing_fields_queue.pop(0)
            if st.session_state.missing_fields_queue:
                next_key, (next_name, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"{feedback_prefix} 另外，我注意到 **{next_name}** 也没填，需要补充吗？")
            else:
                st.session_state.step = "review"
                add_ai_message(f"{feedback_prefix} 核对完毕！确认无误请点击下方 **'确认保存'**。")
    elif st.session_state.step == "review":
        with st.spinner("修改中..."):
            st.session_state.sales_data = st.session_state.controller.update(st.session_state.sales_data, prompt)
            add_report_message(st.session_state.sales_data)
            add_ai_message("修改完成。确认无误请点击 **'确认保存'**。")

# Logic trigger handling
if "submit_trigger" in st.session_state:
    p = st.session_state.pop("submit_trigger")
    add_user_message(p)
    handle_logic(p)

# --- Chat History ---
display_chat()

# --- BOTTOM UI ---
with st.container():
    if st.session_state.step == "review":
        rb1, rb2, _ = st.columns([1, 1, 4])
        with rb1:
            if st.button("✅ 确认保存", type="primary", use_container_width=True):
                rid, _ = st.session_state.controller.save(st.session_state.sales_data)
                st.toast(f"保存成功！ID: {rid}"); time.sleep(1); reset_state()
        with rb2:
            if st.button("❌ 放弃", use_container_width=True): reset_state()

    # Unified Bar
    c_plus, c_in, c_mic, c_send = st.columns([0.8, 7.2, 0.8, 1.2])
    with c_plus:
        pop = st.popover("➕", use_container_width=True)
        with pop:
            f = st.file_uploader("音频", type=["wav", "mp3"], label_visibility="collapsed")
            if f and st.button("🚀 识别并填入", key="up_f", type="primary"):
                tmp = Path(f"data/tmp/{f.name}"); tmp.parent.mkdir(parents=True, exist_ok=True)
                with open(tmp, "wb") as _f: _f.write(f.getbuffer())
                st.session_state.transcribe_path = tmp; st.session_state.transcribing = True; st.rerun()
    with c_in:
        # Standard key binding
        st.text_area("输入框", placeholder="输入或修改...", label_visibility="collapsed", key="chat_input_area", height=68)
    with c_mic:
        st.audio_input("录音", label_visibility="collapsed", key="mic_input")
    with c_send:
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        st.button("🚀", type="primary", use_container_width=True, key="final_send_btn")

# JS for Enter/Ctrl+Enter
components.html("""
<script>
const doc = window.parent.document;
function setupInput() {
    // 1. 寻找那个 placeholder 匹配的 textarea
    const textareas = Array.from(doc.querySelectorAll('textarea'));
    const textarea = textareas.find(t => t.placeholder && t.placeholder.includes("输入或修改"));

    // 2. 寻找那个带着大火箭的发送按钮
    const buttons = Array.from(doc.querySelectorAll('button'));
    const send_btn = buttons.find(b => b.innerText.includes("🚀") || b.textContent.includes("🚀"));

    if (textarea && send_btn && !textarea.dataset.hookAttached) {
        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                // 如果按了 Shift/Ctrl/Alt，那是真想换行，咱不管
                if (e.shiftKey || e.ctrlKey || e.metaKey) {
                    return;
                }
                
                // 否则，这就是要发送！
                e.preventDefault();
                e.stopPropagation();

                // 核心骚操作：先失去焦点，强制同步数据到 Streamlit 后台
                textarea.blur();
                
                // 稍微等几毫秒，让数据飞一会儿，再点发送
                setTimeout(() => {
                    send_btn.click();
                    // 点完再把焦点拉回来，方便下次输入
                    setTimeout(() => textarea.focus(), 100);
                }, 50);
            }
        });
        textarea.dataset.hookAttached = "true";
        console.log("老大哥的 Enter 钩子已经挂好了！");
    }
}
// 提高侦察频率，每 500ms 检查一次
setInterval(setupInput, 500);
</script>""", height=0)