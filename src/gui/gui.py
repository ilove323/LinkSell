"""
LinkSell GUI 主程序 (Streamlit)

职责：
- 提供用户界面
- 接收用户输入  
- 调用对话引擎处理逻辑
- 展示对话引擎返回的结果

特点：
- 纯UI层，不包含业务逻辑
- 使用conversational_engine进行业务处理
"""

import streamlit as st
import sys
import time
import json
import copy
from pathlib import Path
import streamlit.components.v1 as components

# Add project root to path
root = Path(__file__).parent.parent.parent
if str(root) not in sys.path:
    sys.path.append(str(root))

from src.core.conversational_engine import ConversationalEngine

# ==================== Page Config ====================
st.set_page_config(page_title="LinkSell 智能销售助手", page_icon="💼", layout="wide")

# ==================== Header ====================
logo_path = Path("assets/icon/comlan.png")
col_logo, col_title = st.columns([1, 6])
with col_logo:
    if logo_path.exists():
        st.image(str(logo_path), width=120)
with col_title:
    st.title("LinkSell 智能销售助手")

# ==================== Styles ====================
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

# ==================== Init Session State ====================
APP_VERSION = "3.0"

if "ui_templates" not in st.session_state:
    try:
        with open("config/ui_templates.json", "r", encoding="utf-8") as f:
            st.session_state.ui_templates = json.load(f)
    except:
        st.session_state.ui_templates = {}

if "engine" not in st.session_state or st.session_state.get("app_ver") != APP_VERSION:
    st.session_state.engine = ConversationalEngine()
    st.session_state.app_ver = APP_VERSION

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "有什么需要帮忙的么？您可以查看、创建或修改商机。"
    }]

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

# ==================== Helper Functions ====================

def get_ui_text(key: str, default: str = "") -> str:
    """获取UI话术"""
    import random
    texts = st.session_state.ui_templates.get(key, [])
    if isinstance(texts, list):
        return random.choice(texts) if texts else default
    return texts if texts else default


def add_ai_message(content: str):
    """添加AI消息"""
    st.session_state.messages.append({"role": "assistant", "content": content})


def add_user_message(content: str):
    """添加用户消息"""
    st.session_state.messages.append({"role": "user", "content": content})


def handle_voice_input():
    """处理语音输入"""
    if "voice_input" not in st.session_state:
        st.session_state.voice_input = None
    
    if "last_voice_hash" not in st.session_state:
        st.session_state.last_voice_hash = None
    
    audio_data = st.session_state.voice_input
    if audio_data:
        # 计算音频哈希值，避免重复处理同一音频
        audio_hash = hash(audio_data.getvalue())
        if st.session_state.last_voice_hash != audio_hash:
            # 保存音频文件
            tmp_path = Path(f"data/tmp/voice_{int(time.time())}.wav")
            tmp_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(tmp_path, "wb") as f:
                f.write(audio_data.getbuffer())
            
            # 调用引擎处理语音
            with st.spinner("🎙️ 正在处理语音..."):
                try:
                    result = st.session_state.engine.handle_voice_input(str(tmp_path))
                    if result.get("status") == "success":
                        # 将处理后的文字放入输入框
                        st.session_state.voice_text = result.get("text", "")
                        st.session_state.last_voice_hash = audio_hash
                        st.session_state.voice_input = None  # 清空语音输入
                        st.rerun()
                except Exception as e:
                    st.error(f"语音处理失败: {e}")


def add_report_message(data: dict):
    """添加报告消息（展示商机详情）"""
    st.session_state.messages.append({"role": "assistant", "content": "report", "data": data})


def add_list_message(results: list, search_term: str = ""):
    """添加列表消息"""
    st.session_state.messages.append({"role": "assistant", "content": "list", "results": results, "search_term": search_term})


def display_report(data: dict):
    """展示商机报告"""
    if not data:
        st.warning("无数据可展示")
        return
    
    with st.container():
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
                stage_key = str(opp.get("opportunity_stage", ""))
                stage_name = st.session_state.engine.controller.stage_map.get(stage_key, "未知阶段")
                st.markdown(f"- **阶段**: :blue[{stage_name}]")
                st.markdown(f"- **预算**: :green[{opp.get('budget', '未知')}]")
                st.markdown(f"- **时间**: {opp.get('timeline', '未知')}")
            else:
                st.caption("暂未发现明确商机")
        
        st.divider()
        st.markdown("#### 📌 关键点")
        key_points = opp.get("key_points", []) if opp else []
        if key_points:
            for idx, point in enumerate(key_points, 1):
                st.markdown(f"{idx}. {point}")
        else:
            st.caption("暂无关键点")
        
        st.markdown("#### ✅ 待办事项")
        action_items = opp.get("action_items", []) if opp else []
        if action_items:
            for idx, item in enumerate(action_items, 1):
                st.markdown(f"{idx}. {item}")
        else:
            st.caption("暂无待办事项")
        
        # 跟进记录
        st.divider()
        st.markdown("#### 📜 跟进记录")
        record_logs = data.get("record_logs", [])
        if record_logs:
            recent_logs = sorted(record_logs, key=lambda x: x.get("time", ""), reverse=True)[:3]
            for log in recent_logs:
                log_time = log.get("time", "未知时间")
                recorder = log.get("recorder", "未知")
                content = log.get("content", "")
                with st.expander(f"📅 {log_time} @{recorder}"):
                    st.write(content)
        else:
            st.caption("暂无跟进记录")


def display_candidates(candidates: list) -> int:
    """显示候选商机，返回选中的索引"""
    st.markdown("#### 找到多个相关商机，请选择：")
    
    selected_idx = None
    cols = st.columns(len(candidates))
    
    for idx, cand in enumerate(candidates):
        with cols[idx]:
            if st.button(f"[{cand.get('id', '?')}]\n{cand.get('name', '未命名')}", key=f"cand_{idx}"):
                selected_idx = idx
    
    return selected_idx


def process_user_input(user_input: str):
    """只做输入输出，所有分支交engine统一入口"""
    if not user_input.strip():
        return
    add_user_message(user_input)
    result = st.session_state.engine.handle_user_input(user_input)
    result_type = result.get("type")
    if result_type == "detail":
        if result.get("auto_matched"):
            add_ai_message("💡 未检测到明确对象，已自动使用当前上下文商机。")
        add_ai_message(result.get("message", ""))
        add_report_message(result.get("data"))
    elif result_type == "list":
        add_ai_message(f"📋 找到 {len(result.get('results', []))} 条商机")
        add_list_message(result.get('results', []), result.get('search_term', ''))
    elif result_type == "create":
        add_ai_message(result.get("message", ""))
        if result.get("missing_fields"):
            add_ai_message("⚠️ 以下字段信息不完整：")
            for field_key, (field_name, _) in result["missing_fields"].items():
                add_ai_message(f"  - {field_name}")
        add_report_message(result.get("draft"))
    elif result_type == "update":
        add_ai_message(f"✅ {result.get('message','')}")
        add_report_message(result.get("data"))
    elif result_type == "delete":
        if result["status"] == "confirm_needed":
            add_ai_message("🗑️ 删除确认")
            add_ai_message(result["warning"])
            add_report_message(result["data"])
        elif result["status"] == "not_found":
            add_ai_message(f"❌ {result['message']}")
        elif result["status"] == "ambiguous":
            add_ai_message(result["message"])
            st.session_state.pending_action = {
                "type": "resolve_ambiguity",
                "intent": "DELETE",
                "candidates": result["candidates"]
            }
        elif result["status"] == "success":
            add_ai_message(result["message"])
    elif result_type == "record":
        add_ai_message(f"📝 {result['message']}\n\n{result['polished_content']}")
        add_ai_message("您可以继续输入内容追加笔记，或说'创建'进行提交。")
    elif result_type == "error":
        add_ai_message(result.get("message", "未知错误"))
    else:
        add_ai_message("未能识别的响应类型")


# ==================== 结果处理函数 ====================

def _handle_get_result(result: dict):
    """处理GET结果"""
    if result["status"] == "success":
        if result.get("auto_matched"):
            add_ai_message("💡 未检测到明确对象，已自动使用当前上下文商机。")
        
        add_ai_message(result["message"])
        add_report_message(result["data"])
    
    elif result["status"] == "not_found":
        add_ai_message(f"❌ {result['message']}")
    
    elif result["status"] == "ambiguous":
        add_ai_message(result["message"])
        st.session_state.pending_action = {
            "type": "resolve_ambiguity",
            "intent": "GET",
            "candidates": result["candidates"]
        }


def _handle_list_result(result: dict):
    """处理LIST结果"""
    if result["status"] == "empty":
        add_ai_message(result["message"])
    else:
        add_ai_message(f"📋 找到 {len(result['results'])} 条商机")
        results = result["results"]
        if results:
            list_data = []
            for opp in results:
                pid = str(opp.get("id", "未知"))
                pname = opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知"))
                stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
                stage_name = st.session_state.engine.controller.stage_map.get(stage_code, stage_code)
                sales = opp.get("sales_rep", "-")
                list_data.append({"ID": pid, "项目名称": pname, "阶段": stage_name, "销售": sales})
            st.dataframe(list_data, use_container_width=True)


def _handle_create_result(result: dict):
    """处理CREATE结果"""
    if result["status"] in ["linked", "new"]:
        add_ai_message(result["message"])
        
        if result.get("missing_fields"):
            add_ai_message("⚠️ 以下字段信息不完整：")
            for field_key, (field_name, _) in result["missing_fields"].items():
                add_ai_message(f"  - {field_name}")
        
        add_report_message(result["draft"])
        
        st.session_state.pending_action = {
            "type": "save_discard",
            "data": result["draft"]
        }
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ 确认保存"):
                save_result = st.session_state.engine.confirm_save(result["draft"])
                add_ai_message(save_result["message"])
                st.session_state.pending_action = None
                st.rerun()
        
        with col2:
            if st.button("❌ 放弃修改"):
                st.session_state.engine.discard_changes()
                add_ai_message("已放弃修改")
                st.session_state.pending_action = None
                st.rerun()
    else:
        add_ai_message(f"❌ {result['message']}")


def _handle_update_result(result: dict):
    """处理UPDATE结果"""
    if result["status"] == "success":
        if result.get("auto_matched"):
            add_ai_message("💡 未检测到明确对象，已自动使用当前上下文商机。")
        
        add_ai_message(f"✅ {result['message']}")
        add_report_message(result["data"])
    
    elif result["status"] == "not_found":
        add_ai_message(f"❌ {result['message']}")
    
    elif result["status"] == "ambiguous":
        add_ai_message(result["message"])
        st.session_state.pending_action = {
            "type": "resolve_ambiguity",
            "intent": "UPDATE",
            "candidates": result["candidates"]
        }


def _handle_delete_result(result: dict):
    """处理DELETE结果"""
    if result["status"] == "confirm_needed":
        add_ai_message("🗑️ 删除确认")
        add_ai_message(result["warning"])
        add_report_message(result["data"])
        
        st.session_state.pending_action = {
            "type": "confirm_delete",
            "target": result["data"]
        }
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚨 确定删除", key="delete_confirm"):
                delete_result = st.session_state.engine.confirm_delete()
                add_ai_message(delete_result["message"])
                st.session_state.pending_action = None
                st.rerun()
        
        with col2:
            if st.button("❌ 取消", key="delete_cancel"):
                st.session_state.engine.discard_changes()
                add_ai_message("已取消删除")
                st.session_state.pending_action = None
                st.rerun()
    
    elif result["status"] == "not_found":
        add_ai_message(f"❌ {result['message']}")
    
    elif result["status"] == "ambiguous":
        add_ai_message(result["message"])
        st.session_state.pending_action = {
            "type": "resolve_ambiguity",
            "intent": "DELETE",
            "candidates": result["candidates"]
        }


def _handle_record_result(result: dict):
    """处理RECORD结果"""
    if result["status"] == "success":
        add_ai_message(f"📝 {result['message']}\n\n{result['polished_content']}")
        add_ai_message("您可以继续输入内容追加笔记，或说'创建'进行提交。")


# ==================== Main Chat Interface ====================

# 显示历史消息
for message in st.session_state.messages:
    if message["role"] == "assistant":
        if message["content"] == "report":
            # 展示报告
            with st.chat_message("assistant", avatar="📊"):
                display_report(message.get("data"))
        elif message["content"] == "list":
            # 展示列表
            with st.chat_message("assistant", avatar="📋"):
                results = message.get("results", [])
                if results:
                    list_data = []
                    for opp in results:
                        pid = str(opp.get("id", "未知"))
                        pname = opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知"))
                        stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
                        stage_name = st.session_state.engine.controller.stage_map.get(stage_code, stage_code)
                        sales = opp.get("sales_rep", "-")
                        list_data.append({"ID": pid, "项目名称": pname, "阶段": stage_name, "销售": sales})
                    st.dataframe(list_data, use_container_width=True)
        else:
            with st.chat_message("assistant", avatar="🤖"):
                st.write(message["content"])
    else:
        with st.chat_message("user", avatar="👤"):
            st.write(message["content"])

# 用户输入
st.divider()

# 主输入框
user_input = st.chat_input("请输入您的需求...", key="main_chat_input")
if user_input:
    process_user_input(user_input)
    st.rerun()

# 如果有语音转文字的内容，优先处理
if "voice_text" in st.session_state and st.session_state.voice_text:
    user_input = st.session_state.voice_text
    st.session_state.voice_text = ""  # 清空
    process_user_input(user_input)
    st.rerun()

# 工具栏：语音录制 + 文件上传
col_mic, col_upload, col_spacer = st.columns([1, 1.2, 10])

with col_mic:
    st.audio_input("🎙️ 录音", label_visibility="collapsed", key="voice_input")
    handle_voice_input()

with col_upload:
    # 文件上传
    uploaded_file = st.file_uploader("📁 上传音频", type=["wav", "mp3", "m4a"], label_visibility="collapsed", key="audio_file_uploader")
    if uploaded_file:
        # 保存上传的文件
        tmp_path = Path(f"data/tmp/{uploaded_file.name}")
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # 处理音频
        with st.spinner("📁 正在处理上传的音频..."):
            try:
                result = st.session_state.engine.handle_voice_input(str(tmp_path))
                if result.get("status") == "success":
                    st.session_state.voice_text = result.get("text", "")
                    st.session_state.audio_file_uploader = None  # 清空
                    st.success("音频处理完成，已填充到输入框")
                    st.rerun()
                else:
                    st.error(f"处理失败: {result.get('message', '未知错误')}")
            except Exception as e:
                st.error(f"处理失败: {e}")

# 处理待处理的歧义或确认动作
if st.session_state.pending_action:
    action_type = st.session_state.pending_action.get("type")
    
    if action_type == "resolve_ambiguity":
        st.divider()
        candidates = st.session_state.pending_action.get("candidates", [])
        selected_idx = display_candidates(candidates)
        
        if selected_idx is not None:
            resolve_result = st.session_state.engine.resolve_ambiguity(selected_idx)
            
            if resolve_result.get("next_action") == "display":
                add_ai_message("已选择商机")
                add_report_message(resolve_result["data"])
            elif resolve_result.get("next_action") == "confirm_delete":
                add_ai_message(resolve_result["warning"])
                add_report_message(resolve_result["data"])
            
            st.rerun()
