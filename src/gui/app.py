import streamlit as st
import sys
import time
import json
import copy
import importlib
from pathlib import Path
import streamlit.components.v1 as components

# Add project root to path so we can import src
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

# 强制重载模块，确保最新代码生效
import src.core.controller
importlib.reload(src.core.controller)
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
    /* 极致修剪语音按钮 */
    [data-testid="stAudioInput"] {
        max-width: 100px !important;
        min-width: 100px !important;
        overflow: hidden !important;
        background: transparent !important;
        border: none !important;
    }
    [data-testid="stAudioInput"] section, 
    [data-testid="stAudioInput"] div[data-testid="stMarkdownContainer"],
    [data-testid="stAudioInput"] div[aria-label="Audio waveform"],
    [data-testid="stAudioInput"] button[aria-label="Play"] {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Init Controller & State ---
APP_VERSION = "2.5" 

if "ui_templates" not in st.session_state:
    try:
        with open("config/ui_templates.json", "r", encoding="utf-8") as f:
            st.session_state.ui_templates = json.load(f)
    except:
        st.session_state.ui_templates = {}

def get_ui_text(key, default=""):
    import random
    texts = st.session_state.ui_templates.get(key, [])
    return random.choice(texts) if texts else default

if "controller" not in st.session_state or st.session_state.get("app_ver") != APP_VERSION:
    st.session_state.controller = LinkSellController()
    st.session_state.app_ver = APP_VERSION

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": get_ui_text("greeting", "有什么需要帮忙的么")}]

if "current_opp_id" not in st.session_state:
    st.session_state.current_opp_id = None

if "staged_data" not in st.session_state:
    st.session_state.staged_data = None

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

if "chat_input_area" not in st.session_state:
    st.session_state["chat_input_area"] = ""

# --- Helper Functions ---

def handle_voice_and_files():
    if "mic_input" in st.session_state and st.session_state.mic_input:
        audio = st.session_state.mic_input
        aid = hash(audio.getvalue())
        if st.session_state.get("last_audio") != aid:
            tmp = Path(f"data/tmp/mic_{int(time.time())}.wav"); tmp.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as _f: _f.write(audio.getbuffer())
            with st.spinner("🎙️ 正在将语音转换为文字..."):
                try:
                    text = st.session_state.controller.transcribe(tmp)
                    if text: 
                        st.session_state["chat_input_area"] = text
                        st.session_state["last_audio"] = aid
                        st.rerun()
                except: pass

    if st.session_state.get("transcribing") and st.session_state.get("transcribe_path"):
        tp = st.session_state.pop("transcribe_path"); st.session_state.pop("transcribing")
        try:
            text = st.session_state.controller.transcribe(tp)
            if text: st.session_state["chat_input_area"] = text; st.rerun()
        except: pass

handle_voice_and_files()

def render_report(data):
    if not data: return
    with st.container(border=True):
        st.markdown("### 📊 商机详情")
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
                stage_key = str(opp.get("opportunity_stage", ""))
                stage_name = st.session_state.controller.stage_map.get(stage_key, "未知阶段")
                st.markdown(f"- **阶段**: :blue[{stage_name}]")
                st.markdown(f"- **预算**: :green[{opp.get('budget', '未知')}]")
                st.markdown(f"- **时间**: {opp.get('timeline', '未知')}")
            else: st.caption("暂未发现明确商机")
        
        # 缺失字段警告
        missing = st.session_state.controller.get_missing_fields(data)
        if missing:
            with st.expander("⚠️ 缺少关键信息", expanded=True):
                for _, (name, _) in missing.items(): st.warning(f"缺失: {name}")

        st.divider()
        st.markdown("#### 📜 跟进记录")
        
        # 1. 展示本次待保存的小记 (如果有)
        # 逻辑：如果 summary 存在，且跟最近一条 log 不重复（防止保存后刷新页面出现双份），则展示
        curr_summary = data.get("summary")
        record_logs = data.get("record_logs", [])
        
        is_duplicate = False
        if record_logs and curr_summary:
            last_log_content = record_logs[-1].get("content", "")
            if curr_summary.strip() == last_log_content.strip():
                is_duplicate = True
        
        if curr_summary and not is_duplicate:
            with st.chat_message("user", avatar="🆕"):
                st.caption("本次待保存")
                st.markdown(curr_summary)

        # 2. 展示历史记录
        if record_logs:
            # 倒序显示，最近3条
            for log in sorted(record_logs, key=lambda x: x.get("time", ""), reverse=True)[:3]:
                st.caption(f"{log.get('time')} - {log.get('recorder')}")
                st.markdown(log.get("content"))
        elif not curr_summary:
            st.caption("暂无跟进记录")

def display_chat():
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("type") == "report": render_report(msg["data"])
            else: st.markdown(msg["content"])

def add_user_message(content): st.session_state.messages.append({"role": "user", "content": content})
def add_ai_message(content): st.session_state.messages.append({"role": "assistant", "content": content})
def add_report_message(data): st.session_state.messages.append({"role": "assistant", "type": "report", "data": copy.deepcopy(data)})

def reset_state():
    st.session_state.staged_data = None
    st.session_state.pending_action = None
    st.session_state["chat_input_area"] = ""
    st.rerun()

def handle_missing(missing_map):
    # 辅助函数：处理缺失字段通知 (无状态)
    # 确保使用的是暂存区数据
    target_data = st.session_state.staged_data if st.session_state.staged_data else st.session_state.sales_data
    if target_data:
        add_report_message(target_data)
    
    if missing_map:
        names = [v[0] for v in missing_map.values()]
        msg = f"⚠️ 当前草稿缺失关键信息：**{', '.join(names)}**。\n\n您可以在对话框直接输入补充（如“预算50万”），或直接点击下方 **确认保存**。"
        add_ai_message(msg)
    else:
        add_ai_message("✅ 信息完整。确认无误请点击下方 **确认保存**。")

def handle_logic(prompt):
    if not prompt: return
    
    # 如果有挂起的交互动作，忽略新的文本输入 (强制用户点击按钮)
    if st.session_state.pending_action:
        return

    # 始终重入意图识别 (无状态)
    with st.spinner("正在分析意图..."):
        result = st.session_state.controller.identify_intent(prompt)
        intent = result.get("intent", "CREATE")
        extracted_content = result.get("content", prompt)
    
    if intent == "CREATE":
        with st.spinner("处理中..."):
            pkg = st.session_state.controller.process_create_request(extracted_content)
        if pkg["status"] == "error":
            add_ai_message(f"❌ {pkg.get('message')}")
            return
        
        st.session_state.staged_data = pkg["draft"]
        if pkg["status"] == "linked":
            match = pkg["linked_target"]
            st.session_state.current_opp_id = match["id"]
            
            # 获取旧档案并合并
            old_data = st.session_state.controller.get_opportunity_by_id(match["id"])
            if old_data:
                st.session_state.staged_data = st.session_state.controller.merge_draft_into_old(old_data, pkg["draft"])
            
            add_ai_message(f"✅ 自动关联：**{match['name']}**")
            # 重新检查缺失 (基于合并后的数据)
            missing = st.session_state.controller.get_missing_fields(st.session_state.staged_data)
            handle_missing(missing)
            
        elif pkg["status"] == "ambiguous":
            st.session_state.pending_action = {"type": "create_ambiguity", "candidates": pkg["candidates"]}
            add_ai_message("🔍 发现疑似现有项目，请选择关联或新建：")
            # 此时不展示详情，等待用户选择
            
        else:
            add_ai_message("✨ 识别为新项目。")
            handle_missing(pkg["missing_fields"])

    elif intent in ["GET", "UPDATE", "DELETE"]:
        target, candidates, status = st.session_state.controller.resolve_target_interactive(
            extracted_content, st.session_state.current_opp_id if intent == "UPDATE" else None
        )
        
        if status == "not_found":
            add_ai_message(f"未找到相关商机。")
        elif status == "ambiguous":
            st.session_state.pending_action = {"type": "search_ambiguity", "intent": intent, "candidates": candidates}
            add_ai_message("找到多个商机，请选择：")
        elif target:
            st.session_state.current_opp_id = target["id"]
            if intent == "GET":
                add_ai_message(f"已找到：**{target.get('project_opportunity',{}).get('project_name')}**")
                add_report_message(target)
            elif intent == "UPDATE":
                with st.spinner("生成修改草稿..."):
                    upd = st.session_state.controller.update(target, prompt)
                    st.session_state.staged_data = upd
                add_ai_message(f"已锁定项目并生成修改草稿。")
                add_report_message(upd)
                add_ai_message("修改已暂存，确认请点击 **确认保存**。")
            elif intent == "DELETE":
                st.session_state.pending_action = {"type": "confirm_delete", "target": target}
                add_ai_message(f"🗑️ 确认删除 **{target.get('project_opportunity',{}).get('project_name')}** 吗？")
                add_report_message(target)

    elif intent == "LIST":
        add_ai_message("📋 正在获取商机列表...")
        # (Simplified LIST logic for brevity)
        results = st.session_state.controller.list_opportunities()
        if results:
            for r in results[:5]: add_ai_message(f"- {r.get('project_opportunity',{}).get('project_name')} (ID: {r.get('id')})")
        else: add_ai_message("列表为空。")

    elif intent == "OTHER":
        add_ai_message(get_ui_text("intent_other_hint", "抱歉，这超出了我的业务范围。"))

# --- UI Render ---
display_chat()

# --- Pending Actions (Buttons) ---
if st.session_state.pending_action:
    pa = st.session_state.pending_action
    with st.chat_message("assistant"):
        if pa["type"] == "create_ambiguity":
            cols = st.columns(len(pa["candidates"]) + 1)
            for i, cand in enumerate(pa["candidates"]):
                if cols[i].button(f"关联: {cand['name']}", key=f"assoc_{cand['id']}"):
                    st.session_state.current_opp_id = cand["id"]
                    
                    # 获取旧档案并合并
                    old_data = st.session_state.controller.get_opportunity_by_id(cand["id"])
                    if old_data:
                        # 注意：此时 staged_data 里存的是 Draft
                        merged = st.session_state.controller.merge_draft_into_old(old_data, st.session_state.staged_data)
                        st.session_state.staged_data = merged
                    
                    st.session_state.pending_action = None
                    add_ai_message(f"✅ 已关联至: {cand['name']}")
                    
                    # 重新检查缺失
                    missing = st.session_state.controller.get_missing_fields(st.session_state.staged_data)
                    handle_missing(missing)
                    st.rerun()
            if cols[-1].button("新建项目", key="create_new_btn"):
                st.session_state.current_opp_id = None
                st.session_state.pending_action = None
                add_ai_message("✅ 确认新建。")
                
                # 新建后展示详情并检查缺失
                missing = st.session_state.controller.get_missing_fields(st.session_state.staged_data)
                handle_missing(missing)
                st.rerun()
            if st.button("放弃本次录入", key="discard_create_btn"):
                st.session_state.staged_data = None
                st.session_state.pending_action = None
                add_ai_message("已放弃本次录入草稿。")
                st.rerun()
        
        elif pa["type"] == "search_ambiguity":
            for cand in pa["candidates"]:
                if st.button(f"选择: {cand['name']} (ID: {cand['id']})", key=f"sel_{cand['id']}"):
                    st.session_state.pending_action = None
                    # Re-trigger logic with the selected ID
                    handle_logic(f"查看 ID {cand['id']}")
                    st.rerun()
            if st.button("取消选择", key="cancel_search_btn"):
                st.session_state.pending_action = None
                add_ai_message("已取消选择。")
                st.rerun()
                    
        elif pa["type"] == "confirm_delete":
            c1, c2 = st.columns(2)
            if c1.button("🗑️ 确认彻底删除", type="primary", use_container_width=True):
                if st.session_state.controller.delete_opportunity(pa["target"]["id"]):
                    add_ai_message("✅ 已成功删除。")
                st.session_state.pending_action = None
                st.rerun()
            if c2.button("取消", use_container_width=True):
                st.session_state.pending_action = None
                st.rerun()

# --- Staged Data (Save Button) ---
# 只有在没有挂起的交互动作时，才显示保存按钮
if st.session_state.staged_data and not st.session_state.pending_action:
    with st.container():
        c1, c2, _ = st.columns([1, 1, 4])
        if c1.button("💾 确认保存", type="primary", use_container_width=True):
            rid, _ = st.session_state.controller.save(st.session_state.staged_data)
            add_ai_message(f"✅ 保存成功！ID: {rid}")
            st.session_state.current_opp_id = rid
            st.session_state.staged_data = None
            st.rerun()
        if c2.button("放弃修改", use_container_width=True):
            st.session_state.staged_data = None
            add_ai_message("已放弃当前草稿。")
            st.rerun()

# --- Input Box ---
if st.session_state.get("final_send_btn"):
    p = st.session_state.get("chat_input_area", "").strip()
    if p:
        st.session_state["chat_input_area"] = ""
        st.session_state["submit_trigger"] = p
        st.rerun()

if "submit_trigger" in st.session_state:
    p = st.session_state.pop("submit_trigger")
    add_user_message(p); handle_logic(p); st.rerun()

c_plus, c_in, c_mic, c_send = st.columns([0.8, 7.2, 0.8, 1.2])
with c_plus:
    pop = st.popover("➕")
    with pop:
        f = st.file_uploader("音频", type=["wav", "mp3"])
        if f and st.button("🚀 识别"):
            tmp = Path(f"data/tmp/{f.name}"); tmp.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp, "wb") as _f: _f.write(f.getbuffer())
            st.session_state.transcribe_path = tmp; st.session_state.transcribing = True; st.rerun()
            
is_input_disabled = bool(st.session_state.pending_action)
with c_in: st.text_area("输入", placeholder="在此输入指令..." if not is_input_disabled else "请先点击上方按钮完成选择...", label_visibility="collapsed", key="chat_input_area", height=68, disabled=is_input_disabled)
with c_mic: st.audio_input("录音", label_visibility="collapsed", key="mic_input") # Audio input might not support disabled, assume text is primary
with c_send: 
    st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
    st.button("🚀", type="primary", use_container_width=True, key="final_send_btn", disabled=is_input_disabled)

# JS for Enter key submission
components.html("""
<script>
const doc = window.parent.document;
function setup() {
    const ts = Array.from(doc.querySelectorAll('textarea'));
    const t = ts.find(x => x.placeholder && x.placeholder.includes("在此输入指令"));
    const bs = Array.from(doc.querySelectorAll('button'));
    const b = bs.find(x => x.innerText.includes("🚀") || x.textContent.includes("🚀"));
    if (t && b && !t.dataset.hook) {
        t.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); b.click();
            }
        });
        t.dataset.hook = "true";
    }
}
setInterval(setup, 500);
</script>""", height=0)