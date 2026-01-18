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

# --- View Components ---

def display_result_human_readable(data: dict):
    table = Table(title="[bold green]📊 商机档案[/bold green]", show_header=False, box=None)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    
    type_map = {"chat": "随手记/闲聊", "meeting": "正式会议"}
    table.add_row("🗣️ 记录类型", type_map.get(data.get("record_type"), data.get("record_type")))
    table.add_row("👨‍💼 我方销售", data.get("sales_rep", "未知"))
    table.add_row("📝 核心摘要", data.get("summary", "暂无"))
    
    sentiment = data.get("sentiment", "未知")
    sentiment_color = "green" if "积极" in str(sentiment) else ("red" if "消极" in str(sentiment) else "yellow")
    table.add_row("😊 客户态度", f"[{sentiment_color}]{sentiment}[/{sentiment_color}]")
    console.print(table); console.print("")

    cust_tree = Tree("[bold blue]👤 客户画像[/bold blue]")
    cust = data.get("customer_info", {})
    if cust:
        cust_tree.add(f"姓名: [bold]{cust.get('name', 'N/A')}[/bold]")
        cust_tree.add(f"公司: {cust.get('company', 'N/A')}")
        cust_tree.add(f"职位: {cust.get('role', 'N/A')}")
        cust_tree.add(f"联系方式: {cust.get('contact', 'N/A')}")
    else: cust_tree.add("[dim]未提取到有效信息[/dim]")
    console.print(cust_tree); console.print("")

    opp_tree = Tree("[bold gold1]💰 商机概览[/bold gold1]")
    opp = data.get("project_opportunity", {})
    if opp:
        proj_name = opp.get("project_name", "未命名项目")
        opp_tree.add(f"项目: [bold]{proj_name}[/bold] ({'新项目' if opp.get('is_new_project') else '既有项目'})")
        
        # 数字化转换
        stage_key = str(opp.get("opportunity_stage", ""))
        stage_name = controller.stage_map.get(stage_key, "未知")
        opp_tree.add(f"阶段: [blue]{stage_name}[/blue]")
        
        opp_tree.add(f"预算: [green]{opp.get('budget', '未知')}[/green]")
        opp_tree.add(f"时间: {opp.get('timeline', '未知')}")
        comp_node = opp_tree.add("⚔️ 竞争对手")
        for c in opp.get("competitors", []): comp_node.add(c)
        staff_node = opp_tree.add("🧑‍💻 我方技术人员")
        for s in opp.get("technical_staff", []): staff_node.add(s)
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

@cli_app.command()
def run_analyze(content: str = None, audio_file: str = None, use_mic: bool = False, save: bool = False, debug: bool = False):
    """CLI 核心分析流程"""
    if use_mic:
        mic_path = Path("data/tmp") / f"mic_{{int(time.time())}}.wav"
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
        intent = controller.get_intent(content)
        
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

    aff_kw = ["是", "需要", "yes", "y", "对", "ok", "好的", "好", "可以", "行", "没问题", "嗯", "妥", "存"]
    neg_kw = ["否", "不", "no", "n", "没", "不需要", "不用", "取消", "别"]

    while True:
        # 翻篇儿！清屏，让标题和结果永远在最上方
        console.clear()
        console.print(Panel("[bold green]LinkSell 智能销售助手 - CLI 模式[/bold green]", style="bold green", expand=False))
        
        display_result_human_readable(result)
        if save:
            rid, _ = controller.save(result)
            console.print(f"[bold blue]{get_random_ui('db_save_success', record_id=rid)}[/bold blue]"); break

        user_input = typer.prompt(get_random_ui("ask_modification"), default="", show_default=False).strip()
        if not user_input: continue
        lower_in = user_input.lower()
        
        if any(kw in lower_in for kw in neg_kw) and len(lower_in) < 10:
            save_in = typer.prompt(get_random_ui("ask_save"), default="y", show_default=False).strip().lower()
            from src.services.llm_service import judge_affirmative
            is_agree = (save_in == "" or any(kw in save_in for kw in aff_kw))
            if not is_agree: is_agree = judge_affirmative(save_in, controller.api_key, controller.endpoint_id)
            if is_agree:
                rid, _ = controller.save(result)
                console.print(f"[bold blue]{get_random_ui('db_save_success', record_id=rid)}[/bold blue]"); break
            else: console.print(f"[dim]{get_random_ui('operation_cancel')}[/dim]"); break
        elif any(kw in lower_in for kw in aff_kw) and len(lower_in) < 5:
            instr = typer.prompt(get_random_ui("modification_ask"))
            if instr:
                console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
                result = controller.update(result, instr)
        else:
            console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
            result = controller.update(result, user_input)
