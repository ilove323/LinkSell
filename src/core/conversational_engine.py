"""
对话引擎 (Conversational Engine)

职责：
- 处理所有意图的业务逻辑 (GET/LIST/UPDATE/CREATE/DELETE/RECORD)
- 返回结构化的结果给UI层 (CLI/GUI)
- 管理对话流程和状态

不负责：
- 与用户的直接交互
- 展示结果的格式化
- UI组件的渲染
"""

from src.core.controller import LinkSellController


class ConversationalEngine:
    """对话处理引擎"""
    
    def __init__(self):
        self.controller = LinkSellController()
        self.current_opp_id = None  # 当前上下文的商机ID
        self.staged_data = None      # 待保存的暂存数据
        self.pending_action = None   # 挂起的确认动作
    
    # ==================== GET 意图 ====================
    def handle_get(self, content: str, context_id=None) -> dict:
        """
        处理GET意图：查看商机详细信息
        
        返回格式：
        {
            "status": "success" | "not_found" | "ambiguous",
            "message": "提示信息",
            "data": {...},  # 当status==success时存在
            "candidates": [...],  # 当status==ambiguous时存在
            "context_id": "设置的新上下文ID"
        }
        """
        target, candidates, resolve_status = self.controller.resolve_target_interactive(
            content, context_id or self.current_opp_id
        )
        
        if resolve_status == "not_found":
            search_term = self.controller.extract_search_term(content) or content
            return {
                "status": "not_found",
                "message": f"未找到与 '{search_term}' 相关的商机。",
                "data": None
            }
        
        if resolve_status == "ambiguous":
            return {
                "status": "ambiguous",
                "message": "找到多个相关商机，请提供更精确的名称或直接使用 ID",
                "candidates": candidates,
                "data": None
            }
        
        # found_exact 或 found_by_context
        if target:
            self.current_opp_id = target.get("id")
            auto_matched = resolve_status == "found_by_context"
            
            return {
                "status": "success",
                "message": f"已查看：{target.get('project_opportunity',{}).get('project_name')}",
                "data": target,
                "auto_matched": auto_matched,
                "context_id": target.get("id")
            }
        
        return {
            "status": "error",
            "message": "未知错误",
            "data": None
        }
    
    # ==================== LIST 意图 ====================
    def handle_list(self, content: str) -> dict:
        """
        处理LIST意图：查看商机列表
        
        返回格式：
        {
            "status": "success" | "empty",
            "message": "提示信息",
            "results": [...],
            "search_term": "搜索词"
        }
        """
        result_pkg = self.controller.process_list_request(content)
        results = result_pkg["results"]
        
        return {
            "status": "success" if results else "empty",
            "message": result_pkg["message"],
            "results": results,
            "search_term": result_pkg["search_term"]
        }
    
    # ==================== CREATE 意图 ====================
    def handle_create(self, project_name_hint: str = "") -> dict:
        """
        处理CREATE意图：正式录入/提交商机
        
        返回格式：
        {
            "status": "linked" | "new" | "error",
            "message": "提示信息",
            "draft": {...},  # 生成的草稿数据
            "linked_target": {...},  # 当status==linked时存在，关联的目标
            "missing_fields": {...}  # 缺失的字段
        }
        """
        result_pkg = self.controller.process_commit_request(project_name_hint)
        
        if result_pkg["status"] == "error":
            return {
                "status": "error",
                "message": result_pkg.get("message", "处理失败"),
                "draft": None
            }
        
        draft = result_pkg["draft"]
        status = result_pkg["status"]
        
        # 关联到现有商机或新建
        if status == "linked":
            match = result_pkg["linked_target"]
            self.current_opp_id = match["id"]
            old_data = self.controller.get_opportunity_by_id(match["id"])
            if old_data:
                draft = self.controller.merge_draft_into_old(old_data, draft)
        else:
            self.current_opp_id = None
        
        # 存入暂存区
        self.staged_data = draft
        
        # 获取缺失字段
        missing_fields = self.controller.get_missing_fields(draft)
        
        # 清空笔记缓冲
        self.controller.clear_note_buffer()
        
        return {
            "status": status,  # "linked" 或 "new"
            "message": self._generate_create_message(status, draft),
            "draft": draft,
            "linked_target": result_pkg.get("linked_target"),
            "missing_fields": missing_fields
        }
    
    def _generate_create_message(self, status: str, draft: dict) -> str:
        """生成CREATE操作的提示信息"""
        proj_name = draft.get("project_opportunity", {}).get("project_name", "未命名项目")
        if status == "linked":
            return f"✅ 已成功关联并更新现有项目: {proj_name}"
        else:
            return f"✨ 已识别并生成新商机草稿：{proj_name}"
    
    # ==================== UPDATE 意图 ====================
    def handle_update(self, content: str, context_id=None) -> dict:
        """
        处理UPDATE意图：修改商机信息
        
        返回格式：
        {
            "status": "success" | "not_found" | "ambiguous",
            "message": "提示信息",
            "data": {...},  # 修改后的数据（暂存）
            "candidates": [...],  # 当ambiguous时存在
            "auto_matched": bool,  # 是否自动匹配
            "missing_fields": {...}
        }
        """
        target, candidates, resolve_status = self.controller.resolve_target_interactive(
            content, context_id or self.current_opp_id
        )
        
        if resolve_status == "not_found":
            search_term = self.controller.extract_search_term(content) or content
            return {
                "status": "not_found",
                "message": f"未找到与 '{search_term}' 相关的商机。",
                "data": None
            }
        
        if resolve_status == "ambiguous":
            return {
                "status": "ambiguous",
                "message": "找到多个相关商机，请提供更精确的名称",
                "candidates": candidates,
                "data": None
            }
        
        # 执行更新
        updated_result = self.controller.update(target, content)
        
        # 直接保存（不需要确认）
        success = self.controller.overwrite_opportunity(updated_result)
        
        if success:
            self.current_opp_id = updated_result.get("id")
            return {
                "status": "success",
                "message": "✅ 已修改并保存",
                "data": updated_result,
                "auto_matched": resolve_status == "found_by_context",
                "context_id": updated_result.get("id")
            }
        else:
            return {
                "status": "error",
                "message": "修改失败",
                "data": None
            }
    
    # ==================== DELETE 意图 ====================
    def handle_delete(self, content: str, context_id=None) -> dict:
        """
        处理DELETE意图：删除商机
        
        返回格式：
        {
            "status": "confirm_needed" | "not_found" | "ambiguous" | "deleted",
            "message": "提示信息",
            "data": {...},  # 待删除的数据
            "candidates": [...],  # 当ambiguous时
            "warning": "删除警告"  # 当confirm_needed时
        }
        """
        target, candidates, resolve_status = self.controller.resolve_target_interactive(
            content, context_id or self.current_opp_id
        )
        
        if resolve_status == "not_found":
            search_term = self.controller.extract_search_term(content) or content
            return {
                "status": "not_found",
                "message": f"未找到与 '{search_term}' 相关的商机。",
                "data": None
            }
        
        if resolve_status == "ambiguous":
            return {
                "status": "ambiguous",
                "message": "找到多个相关商机，请提供更精确的名称",
                "candidates": candidates,
                "data": None
            }
        
        if target:
            warning = self.controller.generate_delete_warning(target)
            self.pending_action = {
                "type": "confirm_delete",
                "target": target
            }
            
            return {
                "status": "confirm_needed",
                "message": "确认删除操作",
                "data": target,
                "warning": warning
            }
        
        return {
            "status": "error",
            "message": "未知错误",
            "data": None
        }
    
    def confirm_delete(self) -> dict:
        """确认删除挂起的商机"""
        if not self.pending_action or self.pending_action.get("type") != "confirm_delete":
            return {
                "status": "error",
                "message": "没有待删除的商机"
            }
        
        target = self.pending_action.get("target")
        record_id = target.get("id")
        proj_name = target.get("project_opportunity", {}).get("project_name")
        
        success = self.controller.delete_opportunity(record_id)
        
        self.pending_action = None
        self.current_opp_id = None
        
        return {
            "status": "success" if success else "error",
            "message": f"已删除商机：{proj_name}" if success else "删除失败"
        }
    
    # ==================== RECORD 意图 ====================
    def handle_record(self, content: str) -> dict:
        """
        处理RECORD意图：添加笔记到缓冲区
        
        返回格式：
        {
            "status": "success",
            "message": "笔记已暂存",
            "note_count": 数字,
            "polished_content": "润色后的内容"
        }
        """
        polished = self.controller.add_to_note_buffer(content)
        count = len(self.controller.note_buffer)
        
        return {
            "status": "success",
            "message": f"📝 笔记已暂存 ({count}条)",
            "note_count": count,
            "polished_content": polished
        }
    
    # ==================== 确认动作处理 ====================
    def confirm_save(self, new_data=None) -> dict:
        """
        确认保存暂存的数据
        
        参数：
        - new_data: 可选，新的数据（如果有编辑）
        
        返回格式：
        {
            "status": "success" | "error",
            "message": "提示信息",
            "record_id": "保存后的ID"
        }
        """
        data_to_save = new_data or self.staged_data
        
        if not data_to_save:
            return {
                "status": "error",
                "message": "没有待保存的数据"
            }
        
        success = self.controller.overwrite_opportunity(data_to_save)
        
        if success:
            record_id = data_to_save.get("id")
            self.staged_data = None
            self.pending_action = None
            
            return {
                "status": "success",
                "message": f"✅ 已保存，ID：{record_id}",
                "record_id": record_id
            }
        else:
            return {
                "status": "error",
                "message": "保存失败"
            }
    
    def discard_changes(self) -> dict:
        """放弃暂存的修改"""
        self.staged_data = None
        self.pending_action = None
        
        return {
            "status": "success",
            "message": "已放弃修改"
        }
    
    # ==================== 工具方法 ====================
    def get_staged_data(self):
        """获取暂存的数据"""
        return self.staged_data
    
    def set_context(self, opp_id: str):
        """设置当前上下文ID"""
        self.current_opp_id = opp_id
    
    def get_context(self):
        """获取当前上下文ID"""
        return self.current_opp_id
    
    def resolve_ambiguity(self, selected_index: int) -> dict:
        """
        从多个候选中选择一个
        
        返回格式：
        {
            "status": "success" | "error",
            "data": {...}  # 选定的商机
        }
        """
        if not self.pending_action or self.pending_action.get("type") != "resolve_ambiguity":
            return {
                "status": "error",
                "message": "没有待处理的歧义"
            }
        
        candidates = self.pending_action.get("candidates", [])
        if selected_index < 0 or selected_index >= len(candidates):
            return {
                "status": "error",
                "message": "选择索引无效"
            }
        
        selected = candidates[selected_index]
        target = self.controller.get_opportunity_by_id(selected.get("id"))
        
        # 保存当前待处理的意图
        pending_intent = self.pending_action.get("intent")
        self.pending_action = None
        
        # 根据原始意图继续处理
        if pending_intent == "GET":
            self.current_opp_id = target.get("id")
            return {
                "status": "success",
                "data": target,
                "next_action": "display"
            }
        elif pending_intent == "UPDATE":
            # 返回target，等待更新指令
            return {
                "status": "success",
                "data": target,
                "next_action": "wait_update_instruction"
            }
        elif pending_intent == "DELETE":
            warning = self.controller.generate_delete_warning(target)
            self.pending_action = {
                "type": "confirm_delete",
                "target": target
            }
            return {
                "status": "success",
                "data": target,
                "warning": warning,
                "next_action": "confirm_delete"
            }
        
        return {
            "status": "success",
            "data": target
        }
    
    # ==================== 语音处理 ====================
    def handle_voice_input(self, audio_file: str) -> dict:
        """
        处理语音输入：转文字 → polish处理 → 返回处理后的文本
        """
        try:
            # 1. 转语音为文字
            text = self.controller.transcribe(audio_file)
            if not text:
                return {
                    "status": "error",
                    "message": "语音转换失败，无法识别内容"
                }
            
            # 2. 用polish处理文字
            polished = self.controller.polish(text)
            
            return {
                "status": "success",
                "text": polished,
                "raw_text": text
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"语音处理失败：{str(e)}"
            }
    
    # ==================== 统一对话入口 ====================
    def handle_user_input(self, user_input: str) -> dict:
        """
        统一对话入口：负责意图识别和分支处理，返回结构化结果
        """
        intent_result = self.controller.identify_intent(user_input)
        intent = intent_result.get("intent", "UNKNOWN")
        content = intent_result.get("content", user_input)
        
        if intent == "GET":
            result = self.handle_get(content)
            result["type"] = "detail"
            return result
        elif intent == "LIST":
            result = self.handle_list(content)
            result["type"] = "list"
            return result
        elif intent == "CREATE":
            result = self.handle_create(content)
            result["type"] = "create"
            return result
        elif intent == "UPDATE":
            result = self.handle_update(content)
            result["type"] = "update"
            return result
        elif intent == "DELETE":
            result = self.handle_delete(content)
            result["type"] = "delete"
            return result
        elif intent == "RECORD":
            result = self.handle_record(content)
            result["type"] = "record"
            return result
        else:
            return {
                "type": "error",
                "status": "unknown_intent",
                "message": "未能识别您的意图，请重新输入。"
            }
