import streamlit as st
import sys
import time
import json
import copy
import importlib
from pathlib import Path
import streamlit.components.v1 as components

# Add project root to path so we can import src
# We are in LinkSell/src/gui/app.py
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
    .stTextArea textarea {
        border-radius: 10px;
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
APP_VERSION = "2.4" # 再次提升版本

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

# 强制重置旧实例
if "controller" not in st.session_state or st.session_state.get("app_ver") != APP_VERSION or not hasattr(st.session_state.controller, "identify_intent"):
    try:
        st.session_state.controller = LinkSellController()
        st.session_state.app_ver = APP_VERSION
    except Exception as e:
        st.error(f"Failed to initialize system: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": get_ui_text("greeting", "有什么需要帮忙的么")}]

if "sales_data" not in st.session_state:
    st.session_state.sales_data = None

if "step" not in st.session_state:
    st.session_state.step = "input"

if "missing_fields_queue" not in st.session_state:
    st.session_state.missing_fields_queue = []

if "chat_input_area" not in st.session_state:
    st.session_state["chat_input_area"] = ""

# --- Helper Functions (Definitions) ---

def handle_voice_and_files():
    # Mic handling
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
                        st.rerun() # 立即重绘，确保输入框更新
                    else:
                        st.toast("⚠️ 未识别到有效语音，请大声一点重试", icon="🙉")
                        st.session_state["last_audio"] = aid 
                except Exception as e:
                    error_msg = str(e)
                    if "Configuration Invalid" in error_msg:
                        st.toast("❌ ASR 配置无效！请检查 config.ini", icon="🚫")
                    else:
                        st.toast(f"❌ 语音识别出错: {error_msg}", icon="💥")
                    st.session_state["last_audio"] = aid

    # File handle
    if st.session_state.get("transcribing") and st.session_state.get("transcribe_path"):
        tp = st.session_state.pop("transcribe_path"); st.session_state.pop("transcribing")
        try:
            text = st.session_state.controller.transcribe(tp)
            if text: st.session_state["chat_input_area"] = text; st.rerun()
        except: pass

# 执行语音/文件处理 (必须在 UI 渲染前，且在函数定义后)
handle_voice_and_files()

# --- Other Helpers ---

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
                
                # 数字化转换
                stage_key = str(opp.get("opportunity_stage", ""))
                stage_name = st.session_state.controller.stage_map.get(stage_key, "未知阶段")
                st.markdown(f"- **阶段**: :blue[{stage_name}]")
                
                st.markdown(f"- **预算**: :green[{opp.get('budget', '未知')}]")
                st.markdown(f"- **时间**: {opp.get('timeline', '未知')}")
                st.markdown(f"- **流程**: {opp.get('procurement_process', '未知')}")
                st.markdown(f"- **付款**: {opp.get('payment_terms', '未知')}")
                st.markdown("**⚔️ 竞争对手**")
                comps = opp.get("competitors", [])
                if comps:
                    for c in comps: st.markdown(f"  - {c}")
                else: st.caption("  无明确竞争对手")
                st.markdown("**🧑‍💻 我方技术人员**")
                staffs = opp.get("technical_staff", [])
                if staffs:
                    for s in staffs: st.markdown(f"  - {s}")
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
            
        # --- 新增：跟进记录展示区域 ---
        st.divider()
        st.markdown("#### 📜 跟进记录 (Follow-up Records)")
        record_logs = data.get("record_logs", [])
        if record_logs:
            # 倒序显示，最近的在上面
            for log in sorted(record_logs, key=lambda x: x.get("time", ""), reverse=True):
                with st.chat_message("user", avatar="📝"):
                    st.caption(f"{log.get('time', '未知时间')} - {log.get('recorder', '未知')}")
                    st.markdown(log.get("content", "无内容"))
        else:
            # 如果没有 logs (比如新录入)，显示本次摘要
            curr_summary = data.get("summary")
            if curr_summary:
                with st.chat_message("user", avatar="🆕"):
                    st.caption("本次记录")
                    st.markdown(curr_summary)
            else:
                st.caption("暂无跟进记录")

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
    st.session_state.sales_data = None
    st.session_state.step = "input"
    st.session_state.missing_fields_queue = []
    st.session_state["chat_input_area"] = ""
    st.session_state.last_polished_text = ""
    st.rerun()

def handle_logic(prompt):
    if not prompt: return
    
    if st.session_state.step == "input":
        # 识别意图并分发给相应的处理函数 (参考 CLI 逻辑)
        with st.spinner("正在分析您的意图..."):
            result = st.session_state.controller.identify_intent(prompt)
            intent = result.get("intent", "CREATE")
            extracted_content = result.get("content", prompt)
        
        if intent == "CREATE":
            # 新建商机流程
            with st.spinner(get_ui_text("polishing_start", "正在润色...")):
                polished = st.session_state.controller.polish(extracted_content)
                st.session_state.last_polished_text = polished

            with st.spinner(get_ui_text("analysis_start", "分析中...")):
                data = st.session_state.controller.analyze(polished)
                if not data: 
                    add_ai_message("分析失败。")
                    return
            
            # 【改进】项目关联检查 - 防止重复创建
            extracted_proj_name = data.get("project_opportunity", {}).get("project_name")
            if extracted_proj_name:
                candidates = st.session_state.controller.find_potential_matches(extracted_proj_name)
                
                if candidates:
                    add_ai_message(f"🔍 检测到疑似现有项目，请选择：")
                    
                    # 构建选项
                    options = [f"{i+1}. {cand['name']}" for i, cand in enumerate(candidates)]
                    options.append(f"{len(candidates)+1}. 新建：{extracted_proj_name}")
                    
                    for opt in options:
                        add_ai_message(opt)
                    
                    # 等待用户选择
                    st.session_state.step = "select_project_for_create"
                    st.session_state.create_candidates = candidates
                    st.session_state.sales_data = data
                    st.session_state.last_polished_text = polished
                    add_ai_message("请输入序号（1-{}）：".format(len(candidates)+1))
                    return
            
            st.session_state.sales_data = data
            add_report_message(data)
            st.session_state.step = "missing_fields_start"
            add_ai_message("好的，我已为您提取了关键信息。有需要补充或修改的地方吗？")
        
        elif intent == "LIST":
            # 列表查询 - 使用 extract_search_term() 提取搜索词（与 CLI 一致）
            # 这样可以从用户的原始输入中通过 LLM 准确提取关键词
            search_term = st.session_state.controller.extract_search_term(prompt)
            search_term = search_term.strip() if search_term else ""
            clean_term = search_term.upper().replace("`", "").replace("'", "").replace('"', "")
            
            # 判断是否是"列出全部"的泛指请求
            # 情况1: extracted_content 为空（classify_intent 返回了 "content": ""）
            # 情况2: extracted_content 包含 "所有"、"ALL" 等关键词
            # 情况3: 原始内容中只包含通用词汇，无具体搜索词
            is_full_list = (
                not clean_term or 
                clean_term in ["ALL", "未知", "UNKNOWN"] or 
                clean_term in ["商机", "项目", "单子", "列表", "全部", "所有"]
            )
            
            with st.spinner("正在检索商机..."):
                if is_full_list:
                    results = st.session_state.controller.list_opportunities()
                else:
                    def simple_filter(data):
                        dump_str = json.dumps(data, ensure_ascii=False)
                        return search_term.lower() in dump_str.lower()
                    results = st.session_state.controller.list_opportunities(simple_filter)
            
            if results:
                add_ai_message(f"📋 找到 {len(results)} 条商机")
                for opp in results:
                    pname = opp.get("project_opportunity", {}).get("project_name", "未知")
                    stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
                    stage_name = st.session_state.controller.stage_map.get(stage_code, stage_code)
                    sales = opp.get("sales_rep", "-")
                    add_ai_message(f"- **{pname}** | 阶段: {stage_name} | 销售: {sales}")
            else:
                add_ai_message("暂未找到相关商机。")
        
        elif intent == "GET":
            # 查看详情 - 直接使用提取的内容作为搜索词
            search_term = extracted_content.strip() if extracted_content else prompt
            
            with st.spinner("正在定位商机..."):
                candidates = st.session_state.controller.find_potential_matches(search_term)
            
            if not candidates:
                add_ai_message(f"未找到与 '{search_term}' 相关的商机。")
            elif len(candidates) == 1:
                target = st.session_state.controller.get_opportunity_by_id(candidates[0]["id"])
                if target:
                    add_ai_message(f"已为您找到：**{target.get('project_opportunity', {}).get('project_name')}**")
                    add_report_message(target)
            else:
                st.session_state.search_candidates = candidates
                st.session_state.select_result_source = "GET"
                st.session_state.step = "select_result"
                msg = "找到多个相关商机，请选择：\n"
                for i, cand in enumerate(candidates):
                    msg += f"\n{i+1}. {cand['name']}"
                add_ai_message(msg)
        
        elif intent == "UPDATE":
            # 修改商机 - 直接使用提取的内容作为搜索词
            search_term = extracted_content.strip() if extracted_content else prompt
            
            with st.spinner("正在定位商机..."):
                candidates = st.session_state.controller.find_potential_matches(search_term)
            
            if not candidates:
                add_ai_message(f"未找到与 '{search_term}' 相关的商机。")
            elif len(candidates) == 1:
                target = st.session_state.controller.get_opportunity_by_id(candidates[0]["id"])
                if target:
                    st.session_state.sales_data = target
                    add_ai_message(f"已为您锁定项目：**{target.get('project_opportunity', {}).get('project_name')}**")
                    add_report_message(target)
                    st.session_state.step = "review"
                    add_ai_message("有什么需要调整的地方吗？")
            else:
                st.session_state.search_candidates = candidates
                st.session_state.select_result_source = "UPDATE"
                st.session_state.step = "select_result"
                msg = "找到多个相关商机，请选择要修改的项目：\n"
                for i, cand in enumerate(candidates):
                    msg += f"\n{i+1}. {cand['name']}"
                add_ai_message(msg)
        
        elif intent == "DELETE":
            # 删除商机 - 直接使用提取的内容作为搜索词
            search_term = extracted_content.strip() if extracted_content else prompt
            
            with st.spinner("正在定位商机..."):
                candidates = st.session_state.controller.find_potential_matches(search_term)
            
            if not candidates:
                add_ai_message(f"未找到与 '{search_term}' 相关的商机。")
            elif len(candidates) == 1:
                target = st.session_state.controller.get_opportunity_by_id(candidates[0]["id"])
                if target:
                    st.session_state.sales_data = target
                    pname = target.get("project_opportunity", {}).get("project_name")
                    add_ai_message(f"🗑️ 确认删除项目：**{pname}** 吗？（输入 '确认' 或 '是' 来删除）")
                    add_report_message(target)
                    st.session_state.step = "confirm_delete"
            else:
                st.session_state.search_candidates = candidates
                st.session_state.select_result_source = "DELETE"
                st.session_state.step = "select_result"
                msg = "找到多个相关商机，请选择要删除的项目：\n"
                for i, cand in enumerate(candidates):
                    msg += f"\n{i+1}. {cand['name']}"
                add_ai_message(msg)
        
        elif intent == "OTHER":
            # 非业务请求 - 使用秘书语气拒绝
            add_ai_message(get_ui_text("intent_other_hint", "抱歉，这不在我的业务范围内。请问有关于销售或商机的问题吗？"))
    
    elif st.session_state.step == "missing_fields_start":
        missing_map = st.session_state.controller.get_missing_fields(st.session_state.sales_data)
        if missing_map:
            st.session_state.step = "missing_fields"
            st.session_state.missing_fields_queue = list(missing_map.items())
            key, (name, _) = st.session_state.missing_fields_queue[0]
            add_ai_message(f"为了记录完整，我注意到 **{name}** 还没填，需要补充吗？")
        else:
            st.session_state.step = "review"
            add_ai_message("好的，商机档案已就绪。确认无误请点击下方按钮保存。")

    elif st.session_state.step == "missing_fields":
        if st.session_state.missing_fields_queue:
            curr_key, (curr_name, _) = st.session_state.missing_fields_queue[0]
            if prompt.strip() not in ["无", "没有", "跳过"]:
                st.session_state.sales_data = st.session_state.controller.refine(st.session_state.sales_data, {curr_key: prompt})
                prefix = f"✅ 已补充 **{curr_name}**。"
                add_report_message(st.session_state.sales_data)
            else: prefix = "👌 已跳过."
            st.session_state.missing_fields_queue.pop(0)
            if st.session_state.missing_fields_queue:
                nk, (nn, _) = st.session_state.missing_fields_queue[0]
                add_ai_message(f"{prefix} 另外，我注意到 **{nn}** 也没填，需要补充吗？")
            else:
                st.session_state.step = "review"
                add_ai_message(f"{prefix} 核对完毕！确认无误请点击下方 **'确认保存'**。")
    
    elif st.session_state.step == "review":
        with st.spinner("修改中..."):
            st.session_state.sales_data = st.session_state.controller.update(st.session_state.sales_data, prompt)
            add_report_message(st.session_state.sales_data)
            add_ai_message("修改完成。确认无误请点击 **'确认保存'**。")

    # 【多候选选择处理】
    elif st.session_state.step == "select_project_for_create":
        # CREATE 流程中选择项目关联
        try:
            choice = int(prompt.strip())
            candidates = st.session_state.get("create_candidates", [])
            num_candidates = len(candidates)
            
            if 1 <= choice <= num_candidates:
                # 选择了关联旧项目
                old_data = st.session_state.controller.get_opportunity_by_id(candidates[choice-1]["id"])
                if old_data:
                    selected_name = old_data.get("project_opportunity", {}).get("project_name")
                    add_ai_message(f"✅ 已关联：{selected_name}")
                    
                    # 检测冲突
                    new_data = st.session_state.sales_data
                    conflicts = st.session_state.controller.detect_data_conflicts(old_data, new_data)
                    
                    if conflicts:
                        add_ai_message(f"⚠️ 检测到 {len(conflicts)} 处字段冲突，请确认是否覆盖：")
                        st.session_state.conflict_list = conflicts
                        st.session_state.conflict_index = 0
                        st.session_state.conflict_decisions = {}
                        st.session_state.step = "confirm_conflict"
                    else:
                        # 无冲突，直接更新为关联的项目名
                        st.session_state.sales_data["project_opportunity"]["project_name"] = selected_name
                        st.session_state.step = "missing_fields_start"
                        add_report_message(st.session_state.sales_data)
                        add_ai_message("好的，我已为您提取了关键信息。有需要补充或修改的地方吗？")
            elif choice == num_candidates + 1:
                # 选择了新建
                add_ai_message(f"✅ 确认新建：{st.session_state.sales_data.get('project_opportunity', {}).get('project_name')}")
                st.session_state.step = "missing_fields_start"
                add_report_message(st.session_state.sales_data)
                add_ai_message("好的，我已为您提取了关键信息。有需要补充或修改的地方吗？")
            else:
                add_ai_message(f"❌ 无效序号。请输入 1 到 {num_candidates+1} 之间的数字。")
        except ValueError:
            add_ai_message("❌ 请输入有效的序号。")

    elif st.session_state.step == "confirm_conflict":
        # CREATE 流程中逐个确认字段冲突
        conflicts = st.session_state.get("conflict_list", [])
        conflict_index = st.session_state.get("conflict_index", 0)
        
        if conflict_index < len(conflicts):
            cat, key, label, old_val, new_val = conflicts[conflict_index]
            is_affirm = st.session_state.controller.judge_user_affirmative(prompt)
            st.session_state.conflict_decisions[conflict_index] = is_affirm
            
            if is_affirm:
                add_ai_message(f"✅ 已确认覆盖 **{label}**。")
                # 更新 sales_data
                if cat not in st.session_state.sales_data:
                    st.session_state.sales_data[cat] = {}
                st.session_state.sales_data[cat][key] = new_val
            else:
                add_ai_message(f"✅ 保留原值。")
                # 回滚到旧值
                if cat not in st.session_state.sales_data:
                    st.session_state.sales_data[cat] = {}
                st.session_state.sales_data[cat][key] = old_val
            
            st.session_state.conflict_index += 1
            
            if st.session_state.conflict_index < len(conflicts):
                # 继续下一个冲突
                ncat, nkey, nlabel, nold, nnew = conflicts[st.session_state.conflict_index]
                add_ai_message(f"{nlabel}: 原[{nold}] → 新[{nnew}]。要覆盖吗？")
            else:
                # 所有冲突处理完毕
                add_ai_message("✅ 冲突确认完毕。")
                st.session_state.step = "missing_fields_start"
                add_report_message(st.session_state.sales_data)
                add_ai_message("好的，我已为您提取了关键信息。有需要补充或修改的地方吗？")
        else:
            st.session_state.step = "missing_fields_start"
            add_ai_message("好的，我已为您提取了关键信息。有需要补充或修改的地方吗？")

    elif st.session_state.step == "select_result":
        # GET/UPDATE/DELETE 流程中选择目标商机
        try:
            choice = int(prompt.strip())
            candidates = st.session_state.get("search_candidates", [])
            
            if 1 <= choice <= len(candidates):
                target = st.session_state.controller.get_opportunity_by_id(candidates[choice-1]["id"])
                if target:
                    # 判断来源意图（保存在 session state 中）
                    source_intent = st.session_state.get("select_result_source", "GET")
                    
                    if source_intent == "GET":
                        pname = target.get("project_opportunity", {}).get("project_name")
                        add_ai_message(f"✅ 已为您找到：**{pname}**")
                        add_report_message(target)
                        # GET 之后无后续操作，返回主菜单
                        st.session_state.step = "main"
                    elif source_intent == "UPDATE":
                        pname = target.get("project_opportunity", {}).get("project_name")
                        add_ai_message(f"✅ 已为您锁定项目：**{pname}**")
                        add_report_message(target)
                        st.session_state.sales_data = target
                        st.session_state.step = "review"
                        add_ai_message("有什么需要调整的地方吗？")
                    elif source_intent == "DELETE":
                        pname = target.get("project_opportunity", {}).get("project_name")
                        add_ai_message(f"🗑️ 确认删除项目：**{pname}** 吗？（输入 '确认' 或 '是' 来删除）")
                        st.session_state.sales_data = target
                        st.session_state.step = "confirm_delete"
            else:
                add_ai_message(f"❌ 无效序号。请输入 1 到 {len(candidates)} 之间的数字。")
        except ValueError:
            add_ai_message("❌ 请输入有效的序号。")

    elif st.session_state.step == "select_delete":
        # DELETE 流程中选择目标商机（重定向到 select_result）
        st.session_state.select_result_source = "DELETE"
        st.session_state.step = "select_result"
        # 再次处理输入
        handle_logic(prompt)
        return

    elif st.session_state.step == "confirm_delete":
        # DELETE 流程中最终确认删除
        if st.session_state.controller.judge_user_affirmative(prompt):
            target_id = st.session_state.sales_data.get("id")
            if st.session_state.controller.delete_opportunity(target_id):
                add_ai_message("✅ 已成功删除。")
                reset_state()
            else:
                add_ai_message("❌ 删除失败，请重试。")
        else:
            add_ai_message("❌ 已取消删除。")
            reset_state()

# --- TRIGGER HANDLING ---
if st.session_state.get("final_send_btn"):
    p = st.session_state.get("chat_input_area", "").strip()
    if p:
        st.session_state["chat_input_area"] = ""
        st.session_state["submit_trigger"] = p
        st.rerun()

if "submit_trigger" in st.session_state:
    p = st.session_state.pop("submit_trigger")
    add_user_message(p); handle_logic(p)

# --- UI ---
display_chat()

with st.container():
    if st.session_state.step == "review":
        c1, c2, _ = st.columns([1, 1, 4])
        with c1:
            if st.button("✅ 确认保存", type="primary", use_container_width=True):
                rid, _ = st.session_state.controller.save(st.session_state.sales_data, st.session_state.get("last_polished_text", ""))
                st.toast(f"保存成功！ID: {rid}")
                add_ai_message(get_ui_text("save_success", "记录已成功存档。"))
                time.sleep(0.5); reset_state()
        with c2:
            if st.button("❌ 放弃", use_container_width=True):
                add_ai_message(f"{get_ui_text('operation_cancel', '已放弃。')} {get_ui_text('greeting', '有什么需要帮忙的么？')}"); reset_state()

    c_plus, c_in, c_mic, c_send = st.columns([0.8, 7.2, 0.8, 1.2])
    with c_plus:
        pop = st.popover("➕", use_container_width=True)
        with pop:
            f = st.file_uploader("音频", type=["wav", "mp3"], label_visibility="collapsed")
            if f and st.button("🚀 识别", key="up_f", type="primary"):
                tmp = Path(f"data/tmp/{f.name}"); tmp.parent.mkdir(parents=True, exist_ok=True)
                with open(tmp, "wb") as _f: _f.write(f.getbuffer())
                st.session_state.transcribe_path = tmp; st.session_state.transcribing = True; st.rerun()
    with c_in: st.text_area("输入", placeholder="输入或修改...", label_visibility="collapsed", key="chat_input_area", height=68)
    with c_mic: st.audio_input("录音", label_visibility="collapsed", key="mic_input")
    with c_send:
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        st.button("🚀", type="primary", use_container_width=True, key="final_send_btn")

components.html("""
<script>
const doc = window.parent.document;
function setup() {
    const ts = Array.from(doc.querySelectorAll('textarea'));
    const t = ts.find(x => x.placeholder && x.placeholder.includes("输入或修改"));
    const bs = Array.from(doc.querySelectorAll('button'));
    const b = bs.find(x => x.innerText.includes("🚀") || x.textContent.includes("🚀"));
    if (t && b && !t.dataset.hook) {
        t.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.metaKey) {
                e.preventDefault(); e.stopPropagation();
                t.blur(); setTimeout(() => { b.click(); setTimeout(() => t.focus(), 100); }, 50);
            }
        });
        t.dataset.hook = "true";
    }
}
setInterval(setup, 500);
</script>""", height=0)
