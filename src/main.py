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
    from src.services.llm_service import analyze_text, refine_sales_data
    from src.services.asr_service import transcribe_audio
except ImportError:
    pass

app = typer.Typer()
console = Console()

# 加载系统配置
config = configparser.ConfigParser()
config_path = Path("config/config.ini")
if config_path.exists():
    config.read(config_path)
else:
    print("[bold red]错误：未找到配置文件 config/config.ini。[/bold red]")

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
    return re.sub(r'[\\/*?:\"<>|]', "", name).strip().replace(" ", "_")

def display_result_human_readable(data: dict):
    """
    以人类可读的格式（Rich 表格和树状图）展示分析结果。
    """
    # 1. 基础信息表
    table = Table(title="[bold green]📊 销售记录分析报告[/bold green]", show_header=False, box=None)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")

    type_map = {"chat": "🗣️ 随手记/闲聊", "meeting": "👔 正式会议"}
    record_type = type_map.get(data.get("record_type"), data.get("record_type"))
    
    table.add_row("记录类型", record_type)
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
        is_new = "✨ 新项目" if opp_info.get("is_new_project") else "🔄 既有项目"
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

    # 4. 关键点与待办
    grid = Table.grid(expand=True)
    grid.add_column()
    grid.add_column()
    
    kp_text = Text()
    kp_text.append("📌 关键点：\n", style="bold magenta")
    for idx, point in enumerate(data.get("key_points", []), 1):
        kp_text.append(f"{idx}. {point}\n")
    
    action_text = Text()
    action_text.append("✅ 待办事项：\n", style="bold red")
    for idx, item in enumerate(data.get("action_items", []), 1):
        action_text.append(f"{idx}. {item}\n")

    grid.add_row(Panel(kp_text), Panel(action_text))
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
    opp = data.get("project_opportunity", {})
    if not opp:
        data["project_opportunity"] = {}
        opp = data["project_opportunity"]

    # 定义必填字段及其中文名称
    required_fields = {
        "timeline": "⏱️ 时间节点",
        "budget": "💰 预算金额",
        "procurement_process": "📝 采购流程",
        "competitors": "⚔️ 竞争对手",
        "tech_stack": "🛠️ 我方参与技术",
        "payment_terms": "💳 付款方式"
    }

    user_supplements = {}
    missing_count = 0

    console.print(Panel("[bold yellow]老大哥正在检查数据完整性...[/bold yellow]", style="yellow"))

    for field_key, field_name in required_fields.items():
        val = opp.get(field_key)
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
            user_input = typer.prompt(
                f"老大哥发现 [{field_name}] 没填，赶紧补上 (输入 '无' 跳过)", 
                default="", 
                show_default=False
            )
            
            if user_input and user_input.strip() not in ["无", "没有", "跳过", ""]:
                user_supplements[field_key] = user_input

    if user_supplements:
        console.print("[blue]收到补充信息，正在让 AI 进行格式化和校验...[/blue]")
        # 调用 LLM 进行清洗和校验
        refined_data = refine_sales_data(data, user_supplements, api_key, endpoint_id)
        return refined_data
    
    if missing_count == 0:
        console.print("[green]完美！所有关键信息都齐了！[/green]")
    else:
        console.print("[dim]部分信息已跳过补充。[/dim]")

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
            save: bool = typer.Option(False, "--save", "-s", help="是否直接保存结果")):
    """
    核心功能：分析销售数据。
    支持输入文本或语音文件，调用 AI 进行结构化提炼，并提供交互式编辑与保存功能。
    """
    
    # 1. 优先处理语音输入
    if audio_file:
        console.print(f"[bold cyan]🎤 检测到录音文件：{audio_file}[/bold cyan]")
        
        # 验证 ASR 配置
        asr_app_id = config.get("asr", "app_id", fallback=None)
        volc_ak = config.get("volcengine", "access_key", fallback=None)
        volc_sk = config.get("volcengine", "secret_key", fallback=None)
        
        if not asr_app_id or not volc_ak or not volc_sk or "YOUR_" in volc_ak:
            console.print("[bold red]错误：语音识别配置缺失。[/bold red]")
            console.print("请检查 config.ini 中的 [asr] 和 [volcengine] 配置项。")
            return
            
        # 执行语音转写
        transcribed_text = transcribe_audio(audio_file, asr_app_id, volc_ak, volc_sk)
        
        if transcribed_text:
            content = transcribed_text
            console.print(Panel(content, title="[bold green]🎙️ 语音识别结果[/bold green]"))
        else:
            console.print("[bold red]语音识别失败，请检查文件或网络连接。[/bold red]")

    # 2. 若无输入，进入交互模式
    if not content:
        console.print("[bold yellow]请输入会议记录或销售对话内容（按回车确认）：[/bold yellow]")
        content = typer.prompt("内容")

    console.print(Panel("[bold yellow]AI 正在分析数据，请稍候...[/bold yellow]", title="处理中"))
    
    try:
        # 验证 LLM 配置
        api_key = config.get("doubao", "api_key", fallback=None)
        endpoint_id = config.get("doubao", "analyze_endpoint", fallback=None)
        
        if not api_key or not endpoint_id or "YOUR_" in api_key:
            console.print("[bold red]错误：大模型配置缺失。[/bold red]")
            console.print("请检查 config.ini 中的 [doubao] 配置项。")
            return

        # 执行 AI 分析
        from src.services.llm_service import analyze_text
        result = analyze_text(content, api_key, endpoint_id)
        
        if result:
            # === 新增：强制补全检查 ===
            result = check_and_fill_missing_fields(result, api_key, endpoint_id)
            # ========================

            while True:
                # 展示结果
                display_result_human_readable(result)
                
                # 自动保存模式
                if save:
                    record_id = save_to_db(result)
                    console.print(f"[bold blue]成功：已保存，记录 ID：{record_id}[/bold blue]")
                    break

                # 交互式菜单
                choice = typer.prompt(
                    "请选择操作：(s:保存 / d:丢弃 / e:编辑)", 
                    default="s", 
                    show_default=False
                ).lower()

                if choice == 's':
                    record_id = save_to_db(result)
                    console.print(f"[bold blue]成功：已保存，记录 ID：{record_id}[/bold blue]")
                    break
                elif choice == 'd':
                    console.print("[dim]操作已取消。[/dim]")
                    break
                elif choice == 'e':
                    # 编辑模式
                    console.print("[yellow]正在启动系统编辑器...[/yellow]")
                    edited_json = typer.edit(json.dumps(result, indent=2, ensure_ascii=False), extension=".json")
                    
                    if edited_json:
                        try:
                            result = json.loads(edited_json)
                            console.print("[green]编辑成功，正在刷新视图...[/green]")
                        except json.JSONDecodeError:
                            console.print("[bold red]错误：JSON 格式无效，已还原更改。[/bold red]")
                    else:
                        console.print("[dim]未检测到更改。[/dim]")
                else:
                    console.print("[red]无效输入，请输入 s, d 或 e。[/red]")

        else:
            console.print("[red]错误：AI 服务未返回有效响应。[/red]")
            
    except Exception as e:
        console.print(f"[bold red]系统异常：[/bold red] {e}")

if __name__ == "__main__":
    app()
