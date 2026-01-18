import typer
import configparser
import json
import os
import sys
import datetime
import re
import random
import time
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text

# 将项目根目录添加到 sys.path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.controller import LinkSellController

app = typer.Typer()
console = Console()
controller = LinkSellController()

# 加载 UI 语料库
ui_templates = {}
uitemplates_path = Path("config/ui_templates.json")
if ui_templates_path.exists():
    try:
        with open(ui_templates_path, "r", encoding="utf-8") as f:
            ui_templates = json.load(f)
    except Exception as e:
        print(f"[yellow]警告：UI 语料库加载失败 ({e})，将使用默认提示。[/yellow]")

def get_random_ui(key: str, **kwargs) -> str:
    """从语料库中随机获取一条提示语，并进行格式化填充"""
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
    if isinstance(templates, list) and templates:
        template = random.choice(templates)
    else:
        template = defaults.get(key, "")
        
    return template.format(**kwargs)

def display_result_human_readable(data: dict):
    """
    以人类可读的格式（Rich 表格和树状图）展示分析结果。
    """
    # 1. 基础信息表
    table = Table(title="[bold green]📊 销售小纪[/bold green]", show_header=False, box=None)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")

    type_map = {"chat": "随手记/闲聊", "meeting": "正式会议"}
    record_type = type_map.get(data.get("record_type"), data.get("record_type"))
    
    table.add_row("🗣️ 记录类型", record_type)
    table.add_row("👨‍💼 我方销售", data.get("sales_rep", "未知"))
    table.add_row("📝 核心摘要", data.get("summary", "暂无"))
    
    sentiment = data.get("sentiment", "未知")
    sentiment_color = "green" if "积极" in str(sentiment) else ("red" if "消极" in str(sentiment) else "yellow")
    table.add_row("😊 客户态度", f"[{sentiment_color}]{sentiment}[/{sentiment_color}]")

    console.print(table)
    console.print("")

    # 2. 客户信息树
    cust_tree = Tree("[bold blue]👤 客户画像[/bold blue]")
    cust_info = data.get("customer_info", {})
    if cust_info:
        cust_tree.add(f"姓名: [bold]{cust_info.get('name', 'N/A')}[/bold]")
        cust_tree.add(f"公司: {cust_info.get('company', 'N/A')}")
        cust_tree.add(f"职位: {cust_info.get('role', 'N/A')}")
        cust_tree.add(f"联系方式: {cust_info.get('contact', 'N/A')}")
    else:
        cust_tree.add("[dim]未提取到有效信息[/dim]")
    console.print(cust_tree)
    console.print("")

    # 3. 商机详情树
    opp_tree = Tree("[bold gold1]💰 商机概览[/bold gold1]")
    opp_info = data.get("project_opportunity", {})
    if opp_info:
        proj_name = opp_info.get("project_name", "未命名项目")
        is_new = "新项目" if opp_info.get("is_new_project") else "既有项目"
        opp_tree.add(f"项目: [bold]{proj_name}[/bold] ({is_new})")
        opp_tree.add(f"阶段: {opp_info.get('stage', '未知')}")
        opp_tree.add(f"预算: [green]{opp_info.get('budget', '未知')}[/green]")
        opp_tree.add(f"时间: {opp_info.get('timeline', '未知')}")
        opp_tree.add(f"流程: {opp_info.get('procurement_process', '未知')}")
        opp_tree.add(f"付款: {opp_info.get('payment_terms', '未知')}")
        
        comp_node = opp_tree.add("⚔️ 竞争对手")
        competitors = opp_info.get("competitors", [])
        if competitors: 
            for comp in competitors: comp_node.add(comp)
        else: comp_node.add("[dim]无明确竞争对手[/dim]")

        tech_node = opp_tree.add("🛠️ 我方参与技术")
        tech_stack = opp_info.get("tech_stack", [])
        if tech_stack:
            for tech in tech_stack: tech_node.add(tech)
        else: tech_node.add("[dim]未指定[/dim]")
    else:
        opp_tree.add("[dim]暂未发现明确商机[/dim]")
    console.print(opp_tree)
    console.print("")

    # 4. 关键点与待办事项
    grid = Table.grid(expand=True, padding=1)
    grid.add_column()
    grid.add_column()
    kp_list = data.get("key_points", [])
    action_list = data.get("action_items", [])
    max_items = max(len(kp_list), len(action_list))
    kp_text = Text(); kp_text.append("📌 关键点：\n", style="bold magenta")
    for idx, point in enumerate(kp_list, 1): kp_text.append(f"{idx}. {point}\n")
    if len(kp_list) < max_items: kp_text.append("\n" * (max_items - len(kp_list)))
    action_text = Text(); action_text.append("✅ 待办事项：\n", style="bold red")
    for idx, item in enumerate(action_list, 1): action_text.append(f"{idx}. {item}\n")
    if len(action_list) < max_items: action_text.append("\n" * (max_items - len(action_list)))
    grid.add_row(Panel(kp_text, expand=True), Panel(action_text, expand=True))
    console.print(grid)

def check_and_fill_missing_fields(data: dict):
    """交互式引导用户补充缺失字段。"""
    user_supplements = {}
    missing_fields = controller.get_missing_fields(data)
    if not missing_fields: return data

    msg = get_random_ui("check_integrity_start")
    console.print(Panel(f"[bold yellow]{msg}[/bold yellow]", style="yellow"))

    for field_key, (field_name, _) in missing_fields.items():
        prompt_text = get_random_ui("missing_field_prompts", field_name=field_name)
        user_input = typer.prompt(prompt_text, default="", show_default=False)
        if user_input and user_input.strip() not in ["无", "没有", "跳过", ""]:
            user_supplements[field_key] = user_input

    if user_supplements:
        console.print(f"[blue]{get_random_ui('processing_feedback')}[/blue]")
        return controller.refine(data, user_supplements)
    
    console.print(f"[dim]{get_random_ui('skip_feedback')}[/dim]")
    return data

@app.command()
def init():
    """初始化项目环境。"""
    print("[green]正在初始化 LinkSell 系统...[/green]")
    data_file = Path(controller.config.get("storage", "data_file", fallback="data/sales_data.json"))
    data_file.parent.mkdir(parents=True, exist_ok=True)
    if not data_file.exists():
        with open(data_file, "w", encoding="utf-8") as f: json.dump([], f)
    (data_file.parent / "records").mkdir(parents=True, exist_ok=True)
    print("[bold green]初始化完成。[/bold green]")

def launch_gui():
    """启动 Streamlit 图形界面。"""
    import subprocess
    print("[green]正在启动 LinkSell 图形界面...[/green]")
    gui_path = Path(__file__).parent / "gui" / "app.py"
    try:
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(gui_path)], check=True)
    except KeyboardInterrupt:
        print("[dim]图形界面已关闭。[/dim]")

@app.command()
def analyze(content: str = typer.Option(None, "--content", "-c"),
            audio_file: str = typer.Option(None, "--audio", "-a"),
            use_mic: bool = typer.Option(False, "--microphone", "-m"),
            save: bool = typer.Option(False, "--save", "-s"),
            debug: bool = typer.Option(False, "--debug"),
            cli: bool = typer.Option(False, "--cli")):
    """分析销售数据。"""
    if not cli and not any([content, audio_file, use_mic]):
        launch_gui(); return

    if use_mic:
        mic_file = Path("data/tmp") / f"mic_{int(time.time())}.wav"
        mic_file.parent.mkdir(parents=True, exist_ok=True)
        from src.services.audio_capture import record_audio_until_enter
        if record_audio_until_enter(str(mic_file)): audio_file = str(mic_file)
        else: return

    if audio_file:
        console.print(f"[bold cyan]{get_random_ui('mic_detected', audio_file=audio_file)}[/bold cyan]")
        content = controller.transcribe(audio_file, debug=debug)
        if not content: return

    if not content: content = typer.prompt("请输入内容")

    console.print(Panel(f"[bold cyan]{get_random_ui('polishing_start')}[/bold cyan]", style="cyan"))
    content = controller.polish(content)
    console.print(Panel(content, title="[bold green]整理后的文本[/bold green]"))

    console.print(Panel(f"[bold yellow]{get_random_ui('analysis_start')}[/bold yellow]", title="处理中"))
    result = controller.analyze(content)
    if not result: console.print("[red]分析失败。[/red]"); return

    result = check_and_fill_missing_fields(result)

    affirmative_keywords = ["是", "需要", "yes", "y", "对", "ok", "好的", "好", "可以", "行", "没问题", "嗯", "妥", "存"]
    negative_keywords = ["否", "不", "no", "n", "没", "不需要", "不用", "取消", "别"]

    while True:
        display_result_human_readable(result)
        if save:
            rid, _ = controller.save(result)
            console.print(f"[bold blue]{get_random_ui('db_save_success', record_id=rid)}[/bold blue]"); break

        user_input = typer.prompt(get_random_ui("ask_modification"), default="", show_default=False).strip()
        if not user_input: continue
        lower_input = user_input.lower()
        
        if any(kw in lower_input for kw in negative_keywords) and len(lower_input) < 10:
            save_input = typer.prompt(get_random_ui("ask_save"), default="y", show_default=False).strip().lower()
            from src.services.llm_service import judge_affirmative
            is_agree = (save_input == "" or any(kw in save_input for kw in affirmative_keywords))
            if not is_agree: is_agree = judge_affirmative(save_input, controller.api_key, controller.endpoint_id)
            if is_agree:
                rid, _ = controller.save(result)
                console.print(f"[bold blue]{get_random_ui('db_save_success', record_id=rid)}[/bold blue]"); break
            else: console.print(f"[dim]{get_random_ui('operation_cancel')}[/dim]"); break
        elif any(kw in lower_input for kw in affirmative_keywords) and len(lower_input) < 5:
            instr = typer.prompt(get_random_ui("modification_ask"))
            if instr:
                console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
                result = controller.update(result, instr)
        else:
            console.print(f"[blue]{get_random_ui('modification_processing')}[/blue]")
            result = controller.update(result, user_input)

if __name__ == "__main__":
    app()