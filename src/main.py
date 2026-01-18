import typer
import configparser
import json
import os
import sys
import datetime
import re
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text

# 将项目根目录添加到 sys.path，解决模块导入路径问题
sys.path.append(str(Path(__file__).parent.parent))

# 导入业务服务模块
try:
    from src.services.llm_service import analyze_text, refine_sales_data, polish_text, update_sales_data, judge_affirmative
    from src.services.asr_service import transcribe_audio
except ImportError:
    pass

try:
    from src.services.audio_capture import record_audio_until_enter
except ImportError:
    record_audio_until_enter = None

app = typer.Typer()
console = Console()

# 加载系统配置
config = configparser.ConfigParser()
config_path = Path("config/config.ini")
if config_path.exists():
    config.read(config_path)
else:
    print("[bold red]错误：未找到配置文件 config/config.ini。[/bold red]")

# === 加载 UI 语料库 ===
import random
ui_templates = {}
ui_templates_path = Path("config/ui_templates.json")
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

def get_data_path():
    """获取数据存储文件的绝对路径"""
    return Path(config.get("storage", "data_file", fallback="data/sales_data.json"))

def sanitize_filename(name: str) -> str:
    """
    清洗文件名，移除操作系统不允许的特殊字符。
    
    Args:
        name (str): 原始文件名字符串。
    
    Returns:
        str: 清洗后的安全文件名。
    """
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

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
    
    # 客户情感着色
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
            for comp in competitors:
                comp_node.add(comp)
        else:
            comp_node.add("[dim]无明确竞争对手[/dim]")

        tech_node = opp_tree.add("🛠️ 我方参与技术")
        tech_stack = opp_info.get("tech_stack", [])
        if tech_stack:
            for tech in tech_stack:
                tech_node.add(tech)
        else:
            tech_node.add("[dim]未指定[/dim]")
    else:
        opp_tree.add("[dim]暂未发现明确商机[/dim]")
    console.print(opp_tree)
    console.print("")

    # 4. 关键点与待办事项 (对齐高度)
    grid = Table.grid(expand=True, padding=1)
    grid.add_column()
    grid.add_column()
    
    kp_list = data.get("key_points", [])
    action_list = data.get("action_items", [])
    
    # 计算两者中最大项数，以确保 Panel 边框高度对齐
    max_items = max(len(kp_list), len(action_list))
    
    kp_text = Text()
    kp_text.append("📌 关键点：\n", style="bold magenta")
    for idx, point in enumerate(kp_list, 1):
        kp_text.append(f"{idx}. {point}\n")
    # 填充空行以对齐高度
    if len(kp_list) < max_items:
        kp_text.append("\n" * (max_items - len(kp_list)))
    
    action_text = Text()
    action_text.append("✅ 待办事项：\n", style="bold red")
    for idx, item in enumerate(action_list, 1):
        action_text.append(f"{idx}. {item}\n")
    # 填充空行以对齐高度
    if len(action_list) < max_items:
        action_text.append("\n" * (max_items - len(action_list)))

    grid.add_row(Panel(kp_text, expand=True), Panel(action_text, expand=True))
    console.print(grid)

def save_to_db(record: dict):
    """
    持久化存储记录：
    1. 追加到主数据库文件 (sales_data.json)。
    2. 生成独立的备份文件 (data/records/)。
    
    Returns:
        int: 新记录的 ID。
    """
    # 1. 存主数据库
    data_path = get_data_path()
    
    if data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    
    # 补全元数据
    now = datetime.datetime.now()
    record["created_at"] = now.isoformat()
    record["id"] = len(data) + 1
    
    data.append(record)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 2. 存独立文件
    try:
        proj_name = record.get("project_opportunity", {}).get("project_name", "未命名项目")
        if not proj_name: proj_name = "未命名项目"
        
        safe_proj_name = sanitize_filename(proj_name)
        time_str = now.strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_proj_name}-{time_str}.json"
        
        # 确保目录存在
        records_dir = data_path.parent / "records"
        records_dir.mkdir(parents=True, exist_ok=True)
        
        record_path = records_dir / filename
        
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
            
        console.print(f"[dim]已生成独立备份文件：{record_path}[/dim]")
        
    except Exception as e:
        console.print(f"[bold red]独立文件备份失败（不影响主数据库）：{e}[/bold red]")
    
    return record["id"]

def check_and_fill_missing_fields(data: dict, api_key: str, endpoint_id: str):
    """
    检查关键字段是否缺失，并交互式引导用户补充。
    如果用户补充了信息，则调用 LLM 进行清洗和合并。
    """
    if "project_opportunity" not in data:
        data["project_opportunity"] = {}

    # 定义必填字段配置：key -> (display_name, parent_key)
    # parent_key 为 None 表示根节点，否则为 data[parent_key]
    required_config = {
        "sales_rep": ("👨‍💼 我方销售", None),
        "timeline": ("⏱️ 时间节点", "project_opportunity"),
        "budget": ("💰 预算金额", "project_opportunity"),
        "procurement_process": ("📝 采购流程", "project_opportunity"),
        "competitors": ("⚔️ 竞争对手", "project_opportunity"),
        "tech_stack": ("🛠️ 我方参与技术", "project_opportunity"),
        "payment_terms": ("💳 付款方式", "project_opportunity")
    }

    user_supplements = {}
    missing_count = 0

    msg = get_random_ui("check_integrity_start")
    console.print(Panel(f"[bold yellow]{msg}[/bold yellow]", style="yellow"))

    for field_key, (field_name, parent_key) in required_config.items():
        # 获取字段值
        if parent_key:
            target_dict = data.get(parent_key, {})
        else:
            target_dict = data
        
        val = target_dict.get(field_key)

        # 判断是否为空：None, 空字符串, 空列表, 或包含 "未知/未指定"
        is_missing = False
        if val is None:
            is_missing = True
        elif isinstance(val, str) and (not val.strip() or val in ["未知", "未指定", "N/A"]):
            is_missing = True
        elif isinstance(val, list) and not val:
            is_missing = True

        if is_missing:
            missing_count += 1
            prompt_text = get_random_ui("missing_field_prompts", field_name=field_name)
            user_input = typer.prompt(
                prompt_text, 
                default="", 
                show_default=False
            )
            
            if user_input and user_input.strip() not in ["无", "没有", "跳过", ""]:
                user_supplements[field_key] = user_input

    if user_supplements:
        console.print("[blue]好的，收到您的补充，我这就为您整理格式并进行校验...[/blue]")
        # 调用 LLM 进行清洗和校验
        refined_data = refine_sales_data(data, user_supplements, api_key, endpoint_id)
        return refined_data
    
    if missing_count == 0:
        console.print("[green]关键信息已核对完毕，记录非常完整！[/green]")
    else:
        console.print("[dim]好的，部分信息已按照您的要求跳过补充。[/dim]")

    return data

@app.command()
def init():
    """
    初始化项目环境，检查配置文件及数据目录结构。
    """
    print("[green]正在初始化 LinkSell 系统...[/green]")
    
    # 检查数据文件
    data_path = get_data_path()
    if not data_path.exists():
        data_path.parent.mkdir(parents=True, exist_ok=True)
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        print(f"[blue]数据文件已创建：{data_path}[/blue]")
    else:
        print(f"[yellow]数据文件已存在：{data_path}[/yellow]")

    # 创建 records 目录
    records_dir = data_path.parent / "records"
    if not records_dir.exists():
        records_dir.mkdir(parents=True, exist_ok=True)
        print(f"[blue]独立记录目录已创建：{records_dir}[/blue]")

    print("[bold green]初始化完成。[/bold green]")

@app.command()
def record(note_type: str = typer.Option(..., prompt="请输入记录类型(meeting/chat)"),
           content: str = typer.Option(..., prompt="请输入内容")):
    """
    [开发中] 记录一条新的销售小记。
    """
    print(f"收到！类型：{note_type}, 内容：{content}")
    print("[dim]提示：此命令尚未连接后端逻辑，建议使用 analyze 命令。[/dim]")

@app.command()
def analyze(content: str = typer.Option(None, "--content", "-c", help="要提炼的对话/会议文本内容"),
            audio_file: str = typer.Option(None, "--audio", "-a", help="要识别的录音文件路径 (支持 wav/mp3)"),
            use_mic: bool = typer.Option(False, "--microphone", "-m", help="使用麦克风直接录音"),
            save: bool = typer.Option(False, "--save", "-s", help="是否直接保存结果"),
            debug: bool = typer.Option(False, "--debug", help="开启调试模式，显示详细日志")):
    """
    核心功能：分析销售数据。
    支持输入文本或语音文件，调用 AI 进行结构化提炼，并提供交互式编辑与保存功能。
    """
    
    # 0. 优先处理麦克风输入
    if use_mic:
        # 生成临时文件路径
        tmp_dir = Path("data/tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        mic_file_path = tmp_dir / f"mic_recording_{timestamp}.wav"
        
        # 调用录音模块
        if record_audio_until_enter(str(mic_file_path)):
            audio_file = str(mic_file_path) # 将录音文件传递给后续逻辑
        else:
            return # 录音失败直接退出

    # 1. 优先处理语音输入 (包括录制或指定文件)
    if audio_file:
        console.print(f"[bold cyan]🎤 检测到录音文件：{audio_file}[/bold cyan]")
        
        # 验证 ASR 配置
        asr_app_id = config.get("asr", "app_id", fallback=None)
        asr_token = config.get("asr", "access_token", fallback=None)
        asr_resource = config.get("asr", "resource_id", fallback="volc.seedasr.auc")
        
        # 自动修正：如果用户配置文件里还残留着旧的同步接口 ID，强制改为正确的异步大模型 ID
        if asr_resource == "volc.bigasr.sauc.duration":
            asr_resource = "volc.seedasr.auc"
        
        if not asr_app_id or not asr_token or "YOUR_" in asr_token:
            console.print("[bold red]错误：ASR 大模型配置不完整。[/bold red]")
            console.print("请确保 config.ini [asr] 部分包含有效的 app_id 和 access_token。")
            console.print("参考文档：https://www.volcengine.com/docs/6561/1354868")
            return
            
        # 执行语音转写
        transcribed_text = transcribe_audio(audio_file, asr_app_id, asr_token, asr_resource, debug=debug)
        
        if transcribed_text:
            content = transcribed_text
            # 这里不再打印 "语音识别结果" 面板，留给后面统一的文本润色展示
        else:
            console.print("[bold red]语音识别失败，请检查配置或音频文件格式。[/bold red]")
            return

    # 2. 若无输入，进入交互模式
    if not content:
        console.print("[bold yellow]请输入会议记录或销售对话内容（按回车确认）：[/bold yellow]")
        content = typer.prompt("内容")

    # === 新增：文本润色环节 ===
    # 验证 LLM 配置 (润色也需要 LLM)
    api_key = config.get("doubao", "api_key", fallback=None)
    endpoint_id = config.get("doubao", "analyze_endpoint", fallback=None)
    
    if not api_key or not endpoint_id or "YOUR_" in api_key:
        console.print("[bold red]错误：大模型配置缺失。[/bold red]")
        console.print("请检查 config.ini 中的 [doubao] 配置项。")
        return

    console.print(Panel("[bold cyan]正在进行文本润色与格式化...[/bold cyan]", style="cyan"))
    polished_content = polish_text(content, api_key, endpoint_id)
    
    if polished_content:
        console.print(Panel(polished_content, title="[bold green]📝 整理后的文本[/bold green]"))
        content = polished_content # 使用润色后的文本进行后续分析
    else:
        console.print("[yellow]文本润色失败，将使用原始文本进行分析。[/yellow]")
    # ========================

    console.print(Panel("[bold yellow]AI 正在分析数据，请稍候...[/bold yellow]", title="处理中"))
    
    try:
        # 执行 AI 分析
        from src.services.llm_service import analyze_text
        result = analyze_text(content, api_key, endpoint_id)
        
        if result:
            # === 新增：强制补全检查 ===
            result = check_and_fill_missing_fields(result, api_key, endpoint_id)
            # ========================

            # 定义肯否定词库
            affirmative_keywords = ["是", "需要", "yes", "y", "对", "ok", "好的", "好", "可以", "行", "没问题", "嗯", "恩", "妥", "存"]
            negative_keywords = ["否", "不", "no", "n", "没", "不需要", "不用", "取消", "别"]

            while True:
                # 展示结果
                display_result_human_readable(result)
                
                # 自动保存模式
                if save:
                    record_id = save_to_db(result)
                    msg = get_random_ui("db_save_success", record_id=record_id)
                    console.print(f"[bold blue]{msg}[/bold blue]")
                    break

                # 1. 询问是否需要修改
                ask_mod_text = get_random_ui("ask_modification")
                user_input = typer.prompt(ask_mod_text, default="", show_default=False).strip()
                
                if not user_input:
                    continue # 空输入重试

                lower_input = user_input.lower()
                
                # 情况 A: 用户明确说 "不修改" -> 进入保存流程
                if any(kw in lower_input for kw in negative_keywords) and len(lower_input) < 10:
                    ask_save_text = get_random_ui("ask_save")
                    save_input = typer.prompt(ask_save_text, default="y", show_default=False).strip().lower()
                    
                    # 1. 本地快速判断
                    if save_input == "" or any(kw in save_input for kw in affirmative_keywords):
                        is_agree = True
                    elif any(kw in save_input for kw in negative_keywords):
                        is_agree = False
                    else:
                        # 2. 调用 LLM 深度判断意图
                        console.print("[dim]正在确认您的意图...[/dim]")
                        is_agree = judge_affirmative(save_input, api_key, endpoint_id)

                    if is_agree:
                        record_id = save_to_db(result)
                        msg = get_random_ui("db_save_success", record_id=record_id)
                        console.print(f"[bold blue]{msg}[/bold blue]")
                        break
                    else:
                        msg = get_random_ui("operation_cancel")
                        console.print(f"[dim]{msg}[/dim]")
                        break
                
                # 情况 B: 用户明确说 "需要修改" -> 进一步询问具体内容
                elif any(kw in lower_input for kw in affirmative_keywords) and len(lower_input) < 5:
                    msg = get_random_ui("modification_ask")
                    user_instruction = typer.prompt(msg)
                    
                    if user_instruction and user_instruction.strip():
                        msg = get_random_ui("modification_processing")
                        console.print(f"[blue]{msg}[/blue]")
                        result = update_sales_data(result, user_instruction, api_key, endpoint_id)
                        msg = get_random_ui("modification_success")
                        console.print(f"[green]{msg}[/green]")
                    else:
                        msg = get_random_ui("no_changes")
                        console.print(f"[dim]{msg}[/dim]")
                
                # 情况 C: 用户直接输入了修改指令 (例如 "把预算改成50万")
                else:
                    msg = get_random_ui("modification_processing")
                    console.print(f"[blue]{msg}[/blue]")
                    result = update_sales_data(result, user_input, api_key, endpoint_id)
                    msg = get_random_ui("modification_success")
                    console.print(f"[green]{msg}[/green]")

        else:
            console.print("[red]错误：AI 服务未返回有效响应。[/red]")
            
    except Exception as e:
        console.print(f"[bold red]系统异常：[/bold red] {e}")

if __name__ == "__main__":
    app()
