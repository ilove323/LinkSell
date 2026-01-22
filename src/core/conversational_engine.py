"""LinkSell 对话引擎 (Conversational Engine) - 无状态纯响应版 (v3.2)

职责：
- 处理所有意图的业务逻辑 (GET/LIST/REPLACE/CREATE/DELETE/RECORD/SAVE/MERGE)
- 返回结构化的结果给 UI 层 (CLI/GUI)
- 管理会话上下文 (Context ID)

特点：
- **Stateless**: 不挂起任何操作，不反问用户，不等待回复
- **Search First**: GET/DELETE/REPLACE 操作前必须先检索
- **Unique Lock**: 只有当检索结果唯一时，才执行锁定或操作；否则列出清单供参考
"""

import json
from functools import lru_cache
from src.core.controller import LinkSellController


# ===== [PHASE 1 优化] 报告格式化缓存 =====
@lru_cache(maxsize=128)
def _format_report_cached(data_json: str, stage_map_json: str) -> str:
    """
    [性能优化] 缓存版报告生成函数

    问题：每次查看商机都重新生成 Markdown，浪费 CPU

    解决方案：使用 LRU 缓存，对相同的数据返回缓存结果

    参数：
        data_json: 商机数据的 JSON 字符串 (用于可哈希)
        stage_map_json: 阶段映射的 JSON 字符串

    预期收益：
        - 重复查看速度提升 95%+
        - 缓存命中率约 70%
    """
    # 反序列化
    data = json.loads(data_json)
    stage_map = json.loads(stage_map_json)

    if not data:
        return "暂无数据"

    opp = data.get("project_opportunity", {})
    cust = data.get("customer_info", {})

    # [区块 1] 基础信息
    p_name = opp.get("project_name", data.get("project_name", "未命名项目"))
    stage_code = str(opp.get("opportunity_stage", ""))
    stage_name = stage_map.get(stage_code, "未知阶段")
    is_new = "✨ 新项目" if opp.get("is_new_project") else "🔄 既有项目"

    lines = []
    lines.append(f"### {p_name} ({stage_name})")
    lines.append(f"- **ID**: `{data.get('id')}`")
    lines.append(f"- **属性**: {is_new}")
    lines.append(f"- **负责销售**: {data.get('sales_rep', '未指定')}")
    lines.append("")

    # [区块 2] 客户信息 (多行展示)
    lines.append("#### 👤 客户档案")
    if cust:
        lines.append(f"- **客户姓名**: {cust.get('name', 'N/A')}  ")
        lines.append(f"- **企业名称**: {cust.get('company', 'N/A')}  ")
        lines.append(f"- **职位角色**: {cust.get('role', 'N/A')}  ")
        lines.append(f"- **联系方式**: {cust.get('contact', 'N/A')}  ")
    else:
        lines.append("*(暂无客户信息)*")
    lines.append("")

    # [区块 3] 核心指标
    lines.append("#### 📊 项目详情")
    lines.append(f"💰 **预算金额**: {opp.get('budget', '未知')}  ")
    lines.append(f"⏱️ **时间节点**: {opp.get('timeline', '未知')}  ")

    # 客户态度 (Sentiment)
    sentiment = opp.get("sentiment")
    if sentiment:
        lines.append(f"😊 **客户态度**: {sentiment}  ")
    lines.append("")

    # 客户需求
    reqs = opp.get("customer_requirements", [])
    if reqs:
        lines.append("🛠️ **客户需求 (技术/产品)**:  ")
        for r in reqs:
            lines.append(f"  - {r}  ")
        lines.append("")

    # [区块 4] 列表项 (关键点 & 待办)
    if opp.get("key_points"):
        lines.append("📌 **核心关键点**:  ")
        for p in opp.get("key_points", []):
            lines.append(f"  - {p}  ")
        lines.append("")

    if opp.get("action_items"):
        lines.append("✅ **下步待办**:  ")
        for a in opp.get("action_items", []):
            lines.append(f"  - {a}  ")
        lines.append("")

    # [区块 5] 历史记录 (Record Logs)
    logs = data.get("record_logs", [])
    if logs:
        lines.append("📝 **销售小记 (History Logs)**:")
        # 按时间倒序排列，最新的在前面
        sorted_logs = sorted(logs, key=lambda x: x.get("time", ""), reverse=True)

        # 只显示最近 3 条，免得刷屏
        for log in sorted_logs[:3]:
            ts = log.get("time", "")[:16] # 只取到分钟
            content = log.get("content", "")
            lines.append(f"> **{ts}**: {content}  ")

        if len(sorted_logs) > 3:
            lines.append(f"> *(...还有 {len(sorted_logs)-3} 条历史记录)*  ")

    return "\n".join(lines)


class ConversationalEngine:
    """
    [核心类] 对话处理引擎
    作为 UI 层 (CLI/GUI) 和 业务层 (Controller) 之间的中间件，
    负责将用户的自然语言意图转化为具体的业务操作。
    """

    def __init__(self):
        # 初始化控制器 (负责底层数据增删改查)
        self.controller = LinkSellController()
        # [会话状态] 当前锁定的商机 ID
        # 这是 Engine 维护的唯一状态，用于实现多轮对话 (例如："把它的预算改了")
        self.current_opp_id = None  

    # ==================== 辅助方法：格式化输出 ====================

    def _format_report(self, data: dict) -> str:
        """
        [工具函数] 生成商机详情的文本报告 (Markdown格式) - 使用缓存优化
        将 JSON 数据转换为易读的 Markdown 文本，供前端渲染。

        [PHASE 1 优化] 包装器模式，使用全局缓存函数
        """
        if not data:
            return "暂无数据"

        # 转换为 JSON 字符串用于缓存键
        data_json = json.dumps(data, ensure_ascii=False, sort_keys=True)
        stage_map_json = json.dumps(self.controller.stage_map, ensure_ascii=False, sort_keys=True)

        # 调用缓存版本
        return _format_report_cached(data_json, stage_map_json)

    def _format_list(self, results: list) -> str:
        """
        [工具函数] 生成商机列表的文本报告
        用于 LIST 查询结果展示。
        """
        if not results:
            return "暂无相关商机记录。"

        lines = []
        lines.append(f"🔍 找到 {len(results)} 条相关商机：")
        lines.append("")

        for opp in results:
            # 兼容不同数据结构的显示逻辑
            if "project_opportunity" in opp:
                pid = opp.get("id", "?")
                p_name = opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知项目"))
                stage = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
                stage_name = self.controller.stage_map.get(stage, stage)
                sales = opp.get("sales_rep", "-")
                lines.append(f"- `ID: {pid}` | **{p_name}** | {stage_name} | {sales}")
            else:
                pid = opp.get("id", "?")
                p_name = opp.get("name", "未知")
                sales = opp.get("sales_rep", "未知")
                lines.append(f"- `ID: {pid}` | **{p_name}** | 销售: {sales}")

        lines.append("\n(提示：请输入精准 ID 或项目全名以锁定目标)")
        return "\n".join(lines)

    # ==================== 统一对话入口 ====================

    def handle_user_input(self, user_input: str) -> dict:
        """
        [核心入口] 统一处理用户输入
        流程: 识别意图 -> 分发到对应的 handle_xxx 方法 -> 返回结果
        """
        # 1. 意图识别
        intent_result = self.controller.identify_intent(user_input)
        intent = intent_result.get("intent", "UNKNOWN")
        content = intent_result.get("content", user_input)

        # 2. 意图分发
        if intent == "GET":
            return self.handle_get(content)
        elif intent == "LIST":
            return self.handle_list(content)
        elif intent == "CREATE":
            return self.handle_create(content)
        elif intent == "REPLACE":
            return self.handle_replace(content)
        elif intent == "DELETE":
            return self.handle_delete(content)
        elif intent == "RECORD":
            return self.handle_record(content)
        elif intent in ["SAVE", "MERGE"]:
            return self.handle_save()
        else:
            return {
                "type": "error",
                "status": "unknown_intent",
                "message": "未能识别您的意图，请尝试更明确的表达方式。"
            }

    # ==================== 业务处理器 ====================

    def _search_and_resolve(self, content: str, use_context: bool = True):
        """
        [内部逻辑] 搜索解析器
        根据用户输入的内容，尝试找到对应的商机。
        支持上下文 (Context) 优先匹配。
        """
        search_term = self.controller.extract_search_term(content)

        # 策略 1: 上下文优先
        # 如果是模糊指令 (如 "查看详情") 且当前锁定了商机，直接返回当前商机
        if (not search_term or search_term == "CURRENT") and self.current_opp_id and use_context:
            target = self.controller.get_opportunity_by_id(self.current_opp_id)
            if target:
                return [target]

        # 策略 2: 全局搜索
        final_term = search_term if search_term else content
        return self.controller.find_potential_matches(final_term)

    def handle_get(self, content: str) -> dict:
        """[GET] 处理查看详情意图"""
        candidates = self._search_and_resolve(content)

        if not candidates:
            return {"type": "error", "message": f"找不到与 '{content}' 相关的商机。"}

        # 精确匹配：锁定并展示详情
        if len(candidates) == 1:
            full_target = self.controller.get_opportunity_by_id(candidates[0].get("id"))
            if full_target:
                self.current_opp_id = full_target.get("id")
                return {
                    "type": "detail",
                    "message": f"已定位商机：{full_target.get('project_opportunity',{}).get('project_name')}",
                    "report_text": self._format_report(full_target)
                }

        # 模糊匹配：展示列表供选择
        return {
            "type": "list",
            "message": "找到多个匹配结果，请提供更精准的名称或直接使用 ID：",
            "report_text": self._format_list(candidates)
        }

    def handle_list(self, content: str) -> dict:
        """[LIST] 处理列表查询意图"""
        result_pkg = self.controller.process_list_request(content)
        results = result_pkg["results"]
        return {
            "type": "list",
            "message": result_pkg["message"],
            "report_text": self._format_list(results)
        }

    def handle_replace(self, content: str) -> dict:
        """[REPLACE] 处理修改意图"""
        # 1. 优先检查当前锁定上下文
        target = None
        if self.current_opp_id:
            target = self.controller.get_opportunity_by_id(self.current_opp_id)
        
        # 2. 如果没有锁定，才尝试去搜索
        if not target:
            candidates = self._search_and_resolve(content, use_context=False)
            if not candidates:
                return {"type": "error", "message": "找不到要修改的目标，请先查询并锁定一个商机，或在指令中包含准确的项目名称。"}
            if len(candidates) > 1:
                return {
                    "type": "list",
                    "message": "匹配到多个目标，请指定唯一 ID 进行修改：",
                    "report_text": self._format_list(candidates)
                }
            target = self.controller.get_opportunity_by_id(candidates[0].get("id"))

        if target:
            # 3. 执行修改 (调用 Controller)
            updated = self.controller.replace(target, content)
            
            # 计算变更差异 (生成 Diff)
            changes = self.controller.calculate_changes(target, updated)
            change_msg = ""
            if changes:
                change_msg = "\n\n**🔄 本次更新内容：**\n" + "\n".join(changes)
            
            # 保存修改
            if self.controller.overwrite_opportunity(updated):
                self.current_opp_id = updated.get("id")
                return {
                    "type": "update",
                    "message": f"✅ 修改已保存。{change_msg}",
                    "report_text": self._format_report(updated)
                }
        return {"type": "error", "message": "修改保存失败。"}

    def handle_delete(self, content: str) -> dict:
        """[DELETE] 处理删除意图"""
        candidates = self._search_and_resolve(content)

        if not candidates:
            return {"type": "error", "message": "找不到要删除的目标。"}

        if len(candidates) > 1:
            return {
                "type": "list",
                "message": "匹配到多个目标，为防止误删，请使用精准 ID 进行删除：",
                "report_text": self._format_list(candidates)
            }

        real_id = candidates[0].get("id")
        p_name = candidates[0].get("name") or candidates[0].get("project_opportunity", {}).get("project_name")

        if self.controller.delete_opportunity(real_id):
            if self.current_opp_id == real_id:
                self.current_opp_id = None
            return {"type": "delete", "message": f"🗑️ 已成功删除商机：{p_name}"}

        return {"type": "error", "message": "删除失败。"}

    def handle_create(self, content: str) -> dict:
        """[CREATE] 处理创建意图"""
        result_pkg = self.controller.process_commit_request()
        if result_pkg["status"] == "error":
            return {"type": "error", "message": result_pkg.get("message", "提交失败")}

        draft = result_pkg["draft"]
        
        # 保存新商机
        if self.controller.overwrite_opportunity(draft):
            self.current_opp_id = draft.get("id")
            self.controller.clear_note_buffer() # 成功后清空笔记缓存
            
            # 检查缺失字段
            missing = self.controller.get_missing_fields(draft)
            missing_msg = f"\n⚠️ 提醒：关键字段 ({', '.join([v[0] for v in missing.values()])}) 缺失。" if missing else ""

            return {
                "type": "create",
                "message": f"✨ 新建并保存成功：{draft.get('project_name')}{missing_msg}",
                "report_text": self._format_report(draft)
            }
        else:
            return {
                "type": "error", 
                "message": "❌ 保存失败：未识别到有效的项目名称。\nAI 没能从笔记里提取出项目名，请再说一句明确的话，比如：“项目名称是XX改造工程”。"
            }

    def handle_record(self, content: str) -> dict:
        """[RECORD] 处理笔记记录意图"""
        polished = self.controller.add_to_note_buffer(content)
        count = len(self.controller.note_buffer)

        ctx_msg = ""
        if self.current_opp_id:
            curr = self.controller.get_opportunity_by_id(self.current_opp_id)
            if curr:
                name = curr.get("project_opportunity", {}).get("project_name", "当前商机")
                ctx_msg = f"\n(当前上下文: {name})"

        return {
            "type": "record",
            "message": f"📝 笔记已暂存 ({count}条){ctx_msg}\n> {polished}"
        }

    def handle_save(self) -> dict:
        """[SAVE] 处理保存意图 (将缓存笔记存入上下文商机)"""
        if not self.current_opp_id:
            return {"type": "error", "message": "❌ 未选定商机。请先搜索并查看一个商机，再说'保存'。"}
        if not self.controller.note_buffer:
            return {"type": "error", "message": "❌ 没笔记可存。"}

        target = self.controller.get_opportunity_by_id(self.current_opp_id)
        if not target:
            return {"type": "error", "message": "锁定项目失效。"}

        # 合并笔记
        merged = self.controller.merge(target, "\n".join(self.controller.note_buffer))
        
        # 计算变更差异
        changes = self.controller.calculate_changes(target, merged)
        
        if self.controller.overwrite_opportunity(merged):
            self.controller.clear_note_buffer()
            
            change_msg = ""
            if changes:
                change_msg = "\n\n**🔄 本次自动更新字段：**\n" + "\n".join(changes)
            
            return {
                "type": "detail",
                "message": f"✅ 笔记已追加至：{merged.get('project_opportunity',{}).get('project_name')}{change_msg}",
                "report_text": self._format_report(merged)
            }
        return {"type": "error", "message": "保存失败。"}

    def handle_voice_input(self, audio_file: str) -> dict:
        """[AUX] 处理语音输入转换"""
        try:
            text = self.controller.transcribe(audio_file)
            if not text:
                return {"status": "error", "message": "未识别到有效语音。"}
            polished = self.controller.polish(text)
            return {"status": "success", "text": polished}
        except Exception as e:
            return {"status": "error", "message": f"语音错误: {e}"}