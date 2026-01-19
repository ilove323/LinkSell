import typer
import json
import random
import time
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from src.core.controller import LinkSellController

console = Console()
controller = LinkSellController()
cli_app = typer.Typer()
current_opp_id = None # 全局变量：记录当前正在查看的商机 ID
staged_data = None    # 全局变量：暂存待保存的数据 (Staging Area)
pending_action = None # 全局变量：挂起的交互动作 (e.g., {'type': 'select', 'candidates': [...]})

# --- UI Template Loader (CLI Specific) ---
ui_templates = {}
ui_templates_path = Path("config/ui_templates.json")
if ui_templates_path.exists():
    try:
        with open(ui_templates_path, "r", encoding="utf-8") as f:
            ui_templates = json.load(f)
    except Exception as e:
        console.print(f"[yellow]警告：UI 语料库加载失败 ({{e}}) ，将使用默认提示。[/yellow]")

def get_random_ui(key: str, **kwargs) -> str:
    defaults = {
        "missing_field_prompts": "我注意到 [{field_name}] 还没填，需要补充吗？(没有请填 '无')",
        "processing_feedback": "好的，正在处理您的补充信息...",
        "completion_success": "数据完整性校验通过。",
        "skip_feedback": "好的，已跳过补充。",
        "mic_detected": "检测到录音文件：{audio_file}",
        "polishing_start": "正在润色文本...",
        "analysis_start": "AI 正在分析数据...",
        "check_integrity_start": "正在检查数据完整性...",
        "db_save_success": "保存成功，ID：{record_id}",
        "file_save_success": "文件已备份：{file_path}",
        "modification_ask": "请告诉我哪里需要修改？",
        "modification_processing": "好的，正在为您修改...",
        "modification_success": "修改完成。",
        "ask_modification": "您看这份记录有什么需要调整的地方吗？",
        "ask_save": "那确认无误的话，我就存档了？",
        "operation_cancel": "操作已取消。",
        "no_changes": "未检测到更改。",
        "invalid_input": "无效输入。",
        "error_json": "JSON 格式错误。",
        "error_system": "系统错误：{error}"
    }
    templates = ui_templates.get(key, [])
    template = random.choice(templates) if isinstance(templates, list) and templates else defaults.get(key, "")
    return template.format(**kwargs)

def _safe_str(val):
    """Helper to convert list or None to string for Rich rendering"""
    if isinstance(val, list):
        return ", ".join(map(str, val))
    if val is None:
        return ""
    return str(val)

# --- View Components ---

def display_result_human_readable(data: dict):
    # 提取项目名称，作为大标题展示
    p_name = data.get("project_opportunity", {}).get("project_name")
    if not p_name: p_name = data.get("project_name", "未命名项目")
    
    console.print(Panel(f"[bold white]{p_name}[/bold white]", style="bold green", title="商机档案", title_align="left"))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    
    type_map = {"chat": "随手记/闲聊", "meeting": "正式会议"}
    table.add_row("🗣️ 记录类型", _safe_str(type_map.get(data.get("record_type"), data.get("record_type"))))
    table.add_row("👨‍💼 我方销售", _safe_str(data.get("sales_rep", "未知")))
    table.add_row("📝 核心摘要", _safe_str(data.get("summary", "暂无")))
    
    sentiment = data.get("sentiment", "未知")
    sentiment_color = "green" if "积极" in str(sentiment) else ("red" if "消极" in str(sentiment) else "yellow")
    table.add_row("😊 客户态度", f"[{sentiment_color}]{_safe_str(sentiment)}[/{sentiment_color}]")
    console.print(table); console.print("")

    cust_tree = Tree("[bold blue]👤 客户画像[/bold blue]")
    cust = data.get("customer_info", {})
    if cust:
        cust_tree.add(f"姓名: [bold]{_safe_str(cust.get('name', 'N/A'))}[/bold]")
        cust_tree.add(f"公司: {_safe_str(cust.get('company', 'N/A'))}")
        cust_tree.add(f"职位: {_safe_str(cust.get('role', 'N/A'))}")
        cust_tree.add(f"联系方式: {_safe_str(cust.get('contact', 'N/A'))}")
    else: cust_tree.add("[dim]未提取到有效信息[/dim]")
    console.print(cust_tree); console.print("")

    opp_tree = Tree("[bold gold1]💰 商机概览[/bold gold1]")
    opp = data.get("project_opportunity", {})
    if opp:
        # 项目名已在顶部展示，这里不再重复，或者只展示新旧状态
        is_new = '新项目' if opp.get('is_new_project') else '既有项目'
        opp_tree.add(f"属性: {is_new}")
        
        # 数字化转换
        stage_key = str(opp.get("opportunity_stage", ""))
        stage_name = controller.stage_map.get(stage_key, "未知")
        opp_tree.add(f"阶段: [blue]{_safe_str(stage_name)}[/blue]")
        
        opp_tree.add(f"预算: [green]{_safe_str(opp.get('budget', '未知'))}[/green]")
        opp_tree.add(f"时间: {_safe_str(opp.get('timeline', '未知'))}")
        comp_node = opp_tree.add("⚔️ 竞争对手")
        for c in opp.get("competitors", []): comp_node.add(str(c))
        staff_node = opp_tree.add("🧑‍💻 我方技术人员")
        for s in opp.get("technical_staff", []): staff_node.add(str(s))
    else: opp_tree.add("[dim]暂未发现明确商机[/dim]")
    console.print(opp_tree); console.print("")

    grid = Table.grid(expand=True, padding=1)
    grid.add_column(); grid.add_column()
    kp_text = Text(); kp_text.append("📌 关键点：\n", style="bold magenta")
    for idx, p in enumerate(data.get("key_points", []), 1): kp_text.append(f"{idx}. {p}\n")
    act_text = Text(); act_text.append("✅ 待办事项：\n", style="bold red")
    for idx, a in enumerate(data.get("action_items", []), 1): act_text.append(f"{idx}. {a}\n")
    grid.add_row(Panel(kp_text, expand=True), Panel(act_text, expand=True))
    console.print(grid)

    # --- 新增：跟进记录展示区域 ---
    logs_tree = Tree("[bold purple]📜 跟进记录 (Follow-up Records)[/bold purple]")
    
    record_logs = data.get("record_logs", [])
    if record_logs:
        # 如果有历史记录，显示最近 3 条
        # 倒序取最近的
        recent_logs = sorted(record_logs, key=lambda x: x.get("time", ""), reverse=True)[:3]
        for log in recent_logs:
            time_str = log.get("time", "未知时间")
            recorder = log.get("recorder", "未知")
            content = log.get("content", "无内容")
            # 截断过长内容
            if len(content) > 100: content = content[:100] + "..."
            
            log_node = logs_tree.add(f"[dim]{time_str}[/dim] - [bold]{recorder}[/bold]")
            log_node.add(content)
        if len(record_logs) > 3:
            logs_tree.add(f"[dim]... 还有 {len(record_logs)-3} 条历史记录[/dim]")
    else:
        # 如果没有 logs (比如刚录入还没存)，显示本次的摘要或内容
        current_summary = data.get("summary")
        if current_summary:
            node = logs_tree.add("[bold green]🆕 本次记录[/bold green]")
            node.add(current_summary)
        else:
            logs_tree.add("[dim]暂无跟进记录[/dim]")
            
    console.print(logs_tree); console.print("")

# --- Core Logic Helpers ---

def check_and_fill_missing_fields(data: dict):
    missing = controller.get_missing_fields(data)
    if not missing: return data
    console.print(Panel(f"[bold yellow]{get_random_ui('check_integrity_start')}[/bold yellow]", style="yellow"))
    user_supplements = {}
    for field_key, (field_name, _) in missing.items():
        prompt = get_random_ui("missing_field_prompts", field_name=field_name)
        val = typer.prompt(prompt, default="", show_default=False)
        
        # 使用 LLM 规范化输入 (处理 "没有", "跳过" 及格式化)
        normalized_val = controller.normalize_input(val, "EMPTY_CHECK")
        
        if normalized_val:
            console.print(f"-> 记录为: [green]{normalized_val}[/green]")
            user_supplements[field_key] = normalized_val
        else:
            console.print("-> [dim]已跳过[/dim]")
            
    if user_supplements:
        console.print(f"[blue]{get_random_ui('processing_feedback')}[/blue]")
        return controller.refine(data, user_supplements)
    return data

def _interactive_review_loop(data: dict, save_handler, is_new=False):
    """
    统一的交互式审查循环。
    data: 初始数据
    save_handler: 保存/更新数据的回调函数，接收 data，返回 (success, msg)
    is_new: 是否为新建记录（影响提示语）
    """
    current_data = data
    while True:
        console.clear()
        console.print(Panel("[bold green]LinkSell 智能销售助手 - 数据审查[/bold green]", style="bold green", expand=False))
        
        display_result_human_readable(current_data)
        
        # 1. 询问意图
        prompt_text = get_random_ui("ask_modification") if not is_new else "确认保存吗？(可以直接输入修改意见)"
        user_input = typer.prompt(prompt_text, default="", show_default=False).strip()
        
        # 2. 意图判决
        if not user_input:
            is_save = True
        else:
            # 显式否定 (退出/取消)
            neg_kw = ["否", "不", "no", "n", "没", "不需要", "不用", "取消", "别", "退出", "q"]
            if len(user_input) < 10 and any(kw in user_input.lower() for kw in neg_kw):
                if typer.confirm("确定要放弃修改/保存并退出吗？"):
                    console.print(f"[dim]{get_random_ui('operation_cancel')}[/dim]")
                    return
                else:
                    continue
            # 通用肯定判断
            is_save = controller.judge_user_affirmative(user_input)
        
        if is_save:
             # 二次确认 (仅在修改模式下)
             if not is_new: 
                 if not typer.confirm("确认保存当前修改？"): continue
             
             success, msg = save_handler(current_data)
             if success:
                 console.print(f"[bold blue]{msg}[/bold blue]")
                 break
             else:
                 console.print(f"[red]保存失败：{msg}[/red]")
                 if not typer.confirm("是否继续修改？"): break
                 continue
        else:
            # 3. 修改指令
            console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
            current_data = controller.update(current_data, user_input)

def handle_create_logic(content):
    """处理 CREATE 意图 (无状态/暂存模式)"""
    global staged_data, current_opp_id, pending_action
    
    console.print(Panel(f"[bold cyan]{get_random_ui('polishing_start')}[/bold cyan]", style="cyan"))
    console.print(Panel(f"[bold yellow]{get_random_ui('analysis_start')}[/bold yellow]", title="处理中"))

    # 调用核心业务逻辑
    result_pkg = controller.process_create_request(content)
    
    if result_pkg["status"] == "error":
        console.print(f"[red]{result_pkg.get('message', '处理失败')}[/red]")
        return

    draft = result_pkg["draft"]
    status = result_pkg["status"]
    
    # 结果分支处理
    if status == "linked":
        # 自动关联成功
        match = result_pkg["linked_target"]
        current_opp_id = match["id"]
        
        # 获取旧档案并合并
        old_data = controller.get_opportunity_by_id(match["id"])
        if old_data:
            staged_data = controller.merge_draft_into_old(old_data, draft)
        else:
            staged_data = draft
            
        console.print(f"[dim]已自动关联现有项目: {match['name']} (ID: {match['id']})[/dim]")
        
    elif status == "ambiguous":
        # 发现疑似项目 -> 进入挂起选择模式
        pending_action = {
            "type": "select_ambiguity", 
            "intent": "CREATE", 
            "candidates": result_pkg["candidates"],
            "draft": draft
        }
        console.print("[yellow]🔍 发现疑似现有项目，请输入序号进行关联，或选择新建。[/yellow]")
        return 
        
    else: # status == "new"
        current_opp_id = None
        staged_data = draft
        console.print("[dim]识别为新项目草稿。[/dim]")

    # 缺失字段告知
    missing = result_pkg["missing_fields"]
    if missing:
        msg = "[yellow]⚠️  当前草稿缺失关键信息：[/yellow] " + ", ".join([v[0] for v in missing.values()])
        console.print(msg)

    # 展示结果
    display_result_human_readable(staged_data)
    console.print("[bold green]✅ 草稿已暂存。输入 'SAVE' 或 '保存' 即可写入数据库。[/bold green]")

def handle_get_logic(content):
    """处理 GET 意图"""
    global current_opp_id
    
    # 调用核心业务逻辑进行解析 (GET 一般不使用 context_id，除非用户明确指代，这里暂时不传 context_id 以保持纯粹性，
    # 或者如果希望 GET 也能继承上下文，可以传。通常 GET 是用来切换上下文的，所以传 None 比较合理，
    # 但如果用户说 "查看详情" 且没有名词，也可以 fallback 到 current。
    # 为了逻辑统一，我们可以传 current_opp_id，让 controller 判断是否 vague)
    
    target, candidates, status = controller.resolve_target_interactive(content, current_opp_id)
    
    if status == "not_found":
        search_term = controller.extract_search_term(content) or content
        console.print(f"[yellow]未找到与 '{search_term}' 相关的商机。[/yellow]")
        return

    if status == "ambiguous":
        console.print(Panel(f"[yellow]找到多个相关商机，请提供更精确的名称或直接使用 ID：[/yellow]", style="yellow"))
        for cand in candidates:
            cid = cand.get('id', '无ID')
            console.print(f"- [bold cyan]{cid}[/bold cyan] : {cand['name']} ([dim]{cand.get('source', '')}[/dim])")
        return

    if status == "found_by_context":
        console.print(f"[dim]未检测到明确对象，已自动锁定当前商机：{target.get('project_opportunity',{}).get('project_name')}[/dim]")

    if target:
        console.clear()
        display_result_human_readable(target)
        current_opp_id = target.get("id")

def handle_update_logic(content):
    """处理 UPDATE 意图 (无状态/暂存模式)"""
    global staged_data, current_opp_id
    
    # 调用核心业务逻辑进行解析
    target, candidates, status = controller.resolve_target_interactive(content, current_opp_id)
    
    if status == "not_found":
        search_term = controller.extract_search_term(content) or content
        console.print(f"[yellow]未找到与 '{search_term}' 相关的商机。[/yellow]")
        return

    if status == "ambiguous":
        console.print(Panel(f"[yellow]找到多个相关商机，请提供更精确的名称或直接使用 ID：[/yellow]", style="yellow"))
        for cand in candidates:
            cid = cand.get('id', '无ID')
            console.print(f"- [bold cyan]{cid}[/bold cyan] : {cand['name']} ([dim]{cand.get('source', '')}[/dim])")
        return

    if status == "found_by_context":
        console.print(f"[dim]未检测到明确对象，已自动锁定当前商机：{target.get('project_opportunity',{}).get('project_name')}[/dim]")
    
    # status == "found_exact" or "found_by_context" -> target is valid
    
    # 3. 执行更新 (纯逻辑，不存盘)
    console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
    updated_result = controller.update(target, content)
    
    # 4. 存入暂存区
    staged_data = updated_result
    current_opp_id = updated_result.get("id")
    
    # 5. 展示结果
    display_result_human_readable(staged_data)
    console.print("[bold green]✅ 修改已暂存。输入 'SAVE' 或 '保存' 即可写入数据库。[/bold green]")

def handle_delete_logic(content):
    """处理 DELETE 意图"""
    target, candidates, status = controller.resolve_target_interactive(content)
    
    if status == "not_found":
        search_term = controller.extract_search_term(content) or content
        console.print(f"[yellow]未找到与 '{search_term}' 相关的商机。[/yellow]")
        return

    if status == "ambiguous":
        console.print(Panel(f"[yellow]找到多个相关商机，请提供更精确的名称或直接使用 ID：[/yellow]", style="yellow"))
        for cand in candidates:
            cid = cand.get('id', '无ID')
            console.print(f"- [bold cyan]{cid}[/bold cyan] : {cand['name']} ([dim]{cand.get('source', '')}[/dim])")
        return

    # status == "found_exact" or "found_by_context" (context unlikely for delete unless explicit)
    if target:
        pname = target.get("project_opportunity", {}).get("project_name")
        console.print(Panel(f"[red]即将删除：{pname}[/red]", style="red"))
        display_result_human_readable(target) # 最后看一眼
        if typer.confirm("⚠️  此操作不可逆！确认彻底删除吗？"):
            if controller.delete_opportunity(target.get("id")):
                console.print("[green]删除成功。[/green]")
            else:
                console.print("[red]删除失败。[/red]")

# --- Main Entry Point ---

@cli_app.command()
def manage():
    """管理商机 (增删改查)"""
    # 保持原有的 manage 逻辑不变，因为它是一个独立的菜单系统
    # ... (Keep existing manage code or refactor to use handlers if desired, 
    # but for safety let's keep the existing loop as it works well for menu-driven)
    while True:
        console.clear()
        console.print(Panel("[bold green]LinkSell 商机管理控制台[/bold green]", style="bold green"))
        all_opps = controller.get_all_opportunities()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("ID", style="dim", width=12)
        table.add_column("项目名称", style="bold")
        table.add_column("销售", width=8)
        table.add_column("阶段", width=8)
        table.add_column("更新时间", style="dim")
        for opp in all_opps:
             pid = str(opp.get("id", "未知"))
             pname = _safe_str(opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知")))
             sales = _safe_str(opp.get("sales_rep", "-"))
             stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
             stage_name = _safe_str(controller.stage_map.get(stage_code, stage_code))
             time_str = _safe_str(opp.get("updated_at", ""))[:10]
             table.add_row(pid, pname, sales, stage_name, time_str)
        console.print(table)
        console.print("\n[dim]提示：输入 'E <ID>' 编辑记录，'D <ID>' 删除记录[/dim]")
        action = typer.prompt("请选择操作: [N]新建 / [E]编辑 / [D]删除 / [Q]退出").strip().upper()
        if action == "Q": break
        if action == "N": handle_create_logic("") # Reuse
        elif action.startswith("D"):
            target_id = action[1:].strip() if len(action) > 1 else typer.prompt("ID")
            target = controller.get_opportunity_by_id(target_id)
            if target:
                if typer.confirm(f"删除 {target.get('project_opportunity',{}).get('project_name')}?"):
                    controller.delete_opportunity(target.get("id"))
        elif action.startswith("E"):
            target_id = action[1:].strip() if len(action) > 1 else typer.prompt("ID")
            target = controller.get_opportunity_by_id(target_id)
            if target:
                def sw(d): return controller.overwrite_opportunity(d), "Saved"
                _interactive_review_loop(target, sw, False)

@cli_app.command()
def run_analyze(content: str = None, audio_file: str = None, use_mic: bool = False, save: bool = False, debug: bool = False):
    """CLI 核心分析流程 (Refactored Intent Dispatcher)"""
    global staged_data, current_opp_id, pending_action
    
    # 处理初始输入（来自命令行参数）
    if use_mic:
        mic_path = Path("data/tmp") / f"mic_{int(time.time())}.wav"
        from src.services.audio_capture import record_audio_until_enter
        if record_audio_until_enter(str(mic_path)): audio_file = str(mic_path)
        else: return

    if audio_file:
        console.print(f"[bold cyan]{get_random_ui('mic_detected', audio_file=audio_file)}[/bold cyan]")
        content = controller.transcribe(audio_file, debug=debug)
        if not content: return

    if not content: content = typer.prompt("请输入内容")

    # 主交互循环：持续等待用户输入，直到选择退出
    while True:
        # 0. 优先处理挂起的交互 (模拟 GUI 按钮/光标选择)
        if pending_action:
            if pending_action["type"] == "select_ambiguity":
                candidates = pending_action["candidates"]
                intent = pending_action.get("intent", "UNKNOWN")
                
                # 模拟按钮展示
                console.print(Panel(f"[yellow]请选择操作 (输入序号或ID):[/yellow]", style="yellow"))
                for i, cand in enumerate(candidates):
                    cid = cand.get('id', '无ID')
                    console.print(f"[{i+1}] 关联/查看: {cand['name']} (ID: {cid})")
                
                if intent == "CREATE":
                    console.print(f"[{len(candidates)+1}] 新建项目")
                
                console.print(f"[Q] 放弃操作")
                
                choice = typer.prompt("您的选择", show_default=False).strip()
                
                if choice.upper() == 'Q':
                    console.print("[dim]操作已取消。[/dim]")
                    pending_action = None
                    continue

                # 处理选择逻辑
                selected_cand = None
                is_create_new = False
                
                if choice.isdigit():
                    idx = int(choice)
                    if 1 <= idx <= len(candidates):
                        selected_cand = candidates[idx-1]
                    elif intent == "CREATE" and idx == len(candidates) + 1:
                        is_create_new = True
                
                # 尝试 ID 匹配
                if not selected_cand and not is_create_new:
                    for cand in candidates:
                        if str(cand.get("id")) == choice:
                            selected_cand = cand
                            break
                            
                if selected_cand:
                    # 选中了某个项目
                    console.print(f"[green]已选择: {selected_cand['name']}[/green]")
                    
                    if intent == "CREATE":
                        # CREATE 关联逻辑
                        draft = pending_action["draft"] # 之前暂存的草稿
                        old_data = controller.get_opportunity_by_id(selected_cand["id"])
                        if old_data:
                            # 统一合并逻辑
                            staged_data = controller.merge_draft_into_old(old_data, draft)
                            current_opp_id = old_data["id"]
                            console.print("[dim]已关联旧档案。[/dim]")
                            
                            # 重新检查缺失
                            missing = controller.get_missing_fields(staged_data)
                            if missing:
                                msg = "[yellow]⚠️  合并后仍缺失：[/yellow] " + ", ".join([v[0] for v in missing.values()])
                                console.print(msg)
                            
                            display_result_human_readable(staged_data)
                            console.print("[bold green]✅ 草稿已暂存。输入 'SAVE' 即可写入数据库。[/bold green]")
                            
                    else: # GET / UPDATE / DELETE
                        target = controller.get_opportunity_by_id(selected_cand["id"])
                        if target:
                            current_opp_id = target.get("id")
                            if intent == "GET":
                                console.clear(); display_result_human_readable(target)
                            elif intent == "UPDATE":
                                # 恢复之前的 prompt 内容比较困难，因为是无状态的
                                # 但 pending_action 可以存 prompt
                                # 简化处理：选中后，提示用户重新输入修改指令，或者直接进入锁定状态
                                console.print(f"[green]已锁定: {target.get('project_opportunity',{}).get('project_name')}[/green]")
                                console.print("请重新输入修改指令 (例如: 把预算改为50万)")
                            elif intent == "DELETE":
                                handle_delete_logic(str(target.get("id"))) # Re-trigger delete with ID
                    
                    pending_action = None # 清除状态
                    
                elif is_create_new:
                    console.print("[green]确认新建项目。[/green]")
                    staged_data = pending_action["draft"]
                    current_opp_id = None
                    missing = controller.get_missing_fields(staged_data)
                    if missing:
                        msg = "[yellow]⚠️  当前草稿缺失：[/yellow] " + ", ".join([v[0] for v in missing.values()])
                        console.print(msg)
                    display_result_human_readable(staged_data)
                    console.print("[bold green]✅ 草稿已暂存。输入 'SAVE' 即可写入数据库。[/bold green]")
                    pending_action = None
                else:
                    console.print("[red]无效选择，请重试。[/red]")
                
                # Loop again to keep blocking until valid selection
                continue

        # 检查退出命令
        if content.strip().lower() in ["quit", "exit", "q", "退出"]:
            console.print("[dim]已退出分析模式。[/dim]")
            break
            
        # --- 拦截 SAVE 指令 ---
        if content.strip().lower() in ["save", "保存", "存", "s"]:
            if staged_data:
                # 执行保存
                rid, fpath = controller.save(staged_data, raw_content="")
                console.print(f"[bold green]{get_random_ui('db_save_success', record_id=rid)}[/bold green]")
                current_opp_id = rid
                staged_data = None # 清空暂存区
            else:
                console.print("[yellow]暂存区为空，没有可保存的内容。[/yellow]")
            
            # 重新获取输入
            console.print("")
            content = typer.prompt("请输入内容")
            continue
        
        # 1. 意图识别 (The Brain) - 返回 {"intent": "...", "content": "..."}
        with console.status("[bold yellow]正在分析您的意图...", spinner="dots"):
            result = controller.identify_intent(content)
            intent = result.get("intent", "CREATE")
            extracted_content = result.get("content", content)
        
        console.print(f"[dim]识别意图: {intent}[/dim]")

        # 2. 意图分发 (The Dispatcher) - 使用提取的内容
        if intent == "CREATE":
            handle_create_logic(extracted_content)
        elif intent == "LIST":
            handle_list_logic(extracted_content)
        elif intent == "GET":
            handle_get_logic(extracted_content)
        elif intent == "UPDATE":
            handle_update_logic(extracted_content)
        elif intent == "DELETE":
            handle_delete_logic(extracted_content)
        elif intent == "OTHER":
            console.print(f"[yellow]{get_random_ui('intent_other_hint')}[/yellow]")
            # 也可以 fallback 到 RAG
            # controller.handle_query(extracted_content) 
        else:
            # Fallback
            handle_create_logic(extracted_content)
        
        # 获取下一次输入
        console.print("")
        content = typer.prompt("请输入内容")