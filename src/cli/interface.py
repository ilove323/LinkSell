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
    table = Table(title="[bold green]📊 商机档案[/bold green]", show_header=False, box=None)
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
        proj_name = opp.get("project_name", "未命名项目")
        opp_tree.add(f"项目: [bold]{_safe_str(proj_name)}[/bold] ({'新项目' if opp.get('is_new_project') else '既有项目'})")
        
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

# --- CLI Controllers ---

def check_and_fill_missing_fields(data: dict):
    missing = controller.get_missing_fields(data)
    if not missing: return data
    console.print(Panel(f"[bold yellow]{get_random_ui('check_integrity_start')}[/bold yellow]", style="yellow"))
    user_supplements = {}
    for field_key, (field_name, _) in missing.items():
        prompt = get_random_ui("missing_field_prompts", field_name=field_name)
        val = typer.prompt(prompt, default="", show_default=False)
        if val and val.strip() not in ["无", "没有", "跳过"]:
            user_supplements[field_key] = val
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
    aff_kw = ["是", "需要", "yes", "y", "对", "ok", "好的", "好", "可以", "行", "没问题", "嗯", "妥", "存"]
    neg_kw = ["否", "不", "no", "n", "没", "不需要", "不用", "取消", "别"]
    
    current_data = data
    while True:
        console.clear()
        console.print(Panel("[bold green]LinkSell 智能销售助手 - 数据审查[/bold green]", style="bold green", expand=False))
        
        display_result_human_readable(current_data)
        
        # 1. 询问意图
        prompt_text = get_random_ui("ask_modification") if not is_new else "确认保存吗？(可以直接输入修改意见)"
        user_input = typer.prompt(prompt_text, default="", show_default=False).strip()
        
        lower_in = user_input.lower()

        # 2. 判定是否为“保存/退出”意图
        # 如果输入了否定词（取消）
        if any(kw in lower_in for kw in neg_kw) and len(lower_in) < 10:
             if typer.confirm("确定要放弃修改/保存并退出吗？"):
                 console.print(f"[dim]{get_random_ui('operation_cancel')}[/dim]")
                 return
             else:
                 continue
        
        # 如果输入了肯定词（保存），或者是空回车（默认保存）
        is_save_intent = False
        if any(kw in lower_in for kw in aff_kw) and len(lower_in) < 5:
            is_save_intent = True
        elif user_input == "": 
             is_save_intent = True
        
        if is_save_intent:
             # 二次确认
             if not is_new: # 修改模式下再问一句，新建模式下空回车就直接存了
                 if not typer.confirm("确认保存当前修改？"): continue
             
             success, msg = save_handler(current_data)
             if success:
                 console.print(f"[bold blue]{msg}[/bold blue]")
                 break
             else:
                 console.print(f"[red]保存失败：{msg}[/red]")
                 # 失败后继续循环
                 if not typer.confirm("是否继续修改？"): break
                 continue
        else:
            # 3. 否则视为修改指令
            console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
            current_data = controller.update(current_data, user_input)

@cli_app.command()
def manage():
    """管理商机 (增删改查)"""
    while True:
        console.clear()
        console.print(Panel("[bold green]LinkSell 商机管理控制台[/bold green]", style="bold green"))
        
        # List all (Simplified)
        all_opps = controller.get_all_opportunities()
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("ID", style="dim", width=4)
        table.add_column("项目名称", style="bold")
        table.add_column("销售", width=8)
        table.add_column("阶段", width=8)
        table.add_column("更新时间", style="dim")
        
        for opp in all_opps:
             pid = str(opp.get("id", "?"))
             pname = _safe_str(opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知")))
             sales = _safe_str(opp.get("sales_rep", "-"))
             stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
             stage_name = _safe_str(controller.stage_map.get(stage_code, stage_code))
             time_str = _safe_str(opp.get("updated_at", ""))[:10]
             table.add_row(pid, pname, sales, stage_name, time_str)
        
        console.print(table)
        console.print("\n[dim]提示：输入 'E 1' 编辑ID为1的记录，'D 1' 删除ID为1的记录[/dim]")
        action = typer.prompt("请选择操作: [N]新建 / [E]编辑 / [D]删除 / [Q]退出").strip().upper()
        
        if action == "Q": break
        
        if action == "N":
             run_analyze() # Reuse existing flow
        
        elif action.startswith("D"):
            # Delete
            target_id = action[1:].strip() if len(action) > 1 else typer.prompt("请输入要删除的 ID")
            target = controller.get_opportunity_by_id(target_id)
            if target:
                display_result_human_readable(target)
                pname = target.get("project_opportunity", {}).get("project_name", "未知")
                if typer.confirm(f"⚠️  警告：确定要彻底删除项目【{pname}】吗？"):
                    if controller.delete_opportunity(target_id):
                        console.print("[green]删除成功！[/green]")
                        time.sleep(1)
                    else:
                        console.print("[red]删除失败。[/red]")
                        time.sleep(1)
            else:
                console.print("[red]未找到该 ID。[/red]")
                time.sleep(1)

        elif action.startswith("E"):
            # Edit
            target_id = action[1:].strip() if len(action) > 1 else typer.prompt("请输入要编辑的 ID")
            target = controller.get_opportunity_by_id(target_id)
            if target:
                def save_wrapper(data):
                    if controller.overwrite_opportunity(data):
                        return True, "修改已保存！"
                    return False, "保存失败"
                
                _interactive_review_loop(target, save_wrapper, is_new=False)
            else:
                 console.print("[red]未找到该 ID。[/red]")
                 time.sleep(1)

@cli_app.command()
def run_analyze(content: str = None, audio_file: str = None, use_mic: bool = False, save: bool = False, debug: bool = False):
    """CLI 核心分析流程"""
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

    # 新增：意图分流
    with console.status("[bold yellow]正在识别您的需求...", spinner="dots"):
        # Utilizing identify_intent as seen in controller.py
        intent = controller.identify_intent(content)
        
    if intent == "QUERY":
        with console.status("[bold cyan]正在翻阅历史记录...", spinner="search"):
            answer = controller.handle_query(content)
            console.print(Panel(answer, title="[bold green]查询结果[/bold green]", border_style="green"))
            return
            
    if intent == "OTHER":
        console.print("[yellow]提示：[/yellow]我只是一个销售助手，您可以让我帮您分析录音，或者查询历史数据。有什么这方面我能帮您的么？")
        return

    # ANALYZE 逻辑继续
    console.print(Panel(f"[bold cyan]{get_random_ui('polishing_start')}[/bold cyan]", style="cyan"))
    content = controller.polish(content)
    console.print(Panel(content, title="[bold green]整理后的文本[/bold green]"))

    console.print(Panel(f"[bold yellow]{get_random_ui('analysis_start')}[/bold yellow]", title="处理中"))
    result = controller.analyze(content)
    if not result: console.print("[red]分析失败。[/red]"); return

    result = check_and_fill_missing_fields(result)

    # 如果命令行指定了 save，直接保存退出
    if save:
        rid, _ = controller.save(result)
        console.print(f"[bold blue]{get_random_ui('db_save_success', record_id=rid)}[/bold blue]")
        return

    # 定义保存回调
    def create_save_handler(data):
        rid, _ = controller.save(data)
        return True, get_random_ui('db_save_success', record_id=rid)

    # 进入统一审查循环
    _interactive_review_loop(result, create_save_handler, is_new=True)
