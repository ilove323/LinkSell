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

# 将项目根目录添加到 sys.path，解决 No module named 'src' 问题
sys.path.append(str(Path(__file__).parent.parent))

# 导入业务服务
try:
    from src.services.llm_service import analyze_text
except ImportError:
    pass

app = typer.Typer()
console = Console()

# 读取配置
config = configparser.ConfigParser()
config_path = Path("config/config.ini")
if config_path.exists():
    config.read(config_path)
else:
    print("[bold red]配置文件 config/config.ini 没找着啊！赶紧整一个！[/bold red]")

def get_data_path():
    return Path(config.get("storage", "data_file", fallback="data/sales_data.json"))

def sanitize_filename(name: str) -> str:
    """
    清洗文件名，把那些操作系统不认的字符都换成下划线
    """
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

def display_result_human_readable(data: dict):
    """
    用人话（中文）展示分析结果，拒绝密密麻麻的 JSON
    """
    # 1. 基础信息表
    table = Table(title="[bold green]📊 销售小记分析报告[/bold green]", show_header=False, box=None)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")

    # 映射字典：把洋文翻译成东北话（划掉，中文）
    type_map = {"chat": "🗣️ 随手记/闲聊", "meeting": "👔 正式会议"}
    record_type = type_map.get(data.get("record_type"), data.get("record_type"))
    
    table.add_row("记录类型", record_type)
    table.add_row("📝 核心摘要", data.get("summary", "暂无"))
    
    # 客户情感
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
        cust_tree.add(f"联系: {cust_info.get('contact', 'N/A')}")
    else:
        cust_tree.add("[dim]没提取到有效信息[/dim]")
    console.print(cust_tree)
    console.print("")

    # 3. 商机详情树
    opp_tree = Tree("[bold gold1]💰 搞钱机会 (商机)[/bold gold1]")
    opp_info = data.get("project_opportunity", {})
    if opp_info:
        proj_name = opp_info.get("project_name", "未命名项目")
        is_new = "✨ 新项目" if opp_info.get("is_new_project") else "🔄 既有项目"
        opp_tree.add(f"项目: [bold]{proj_name}[/bold] ({is_new})")
        opp_tree.add(f"阶段: {opp_info.get('stage', '未知')}")
        opp_tree.add(f"预算: [green]{opp_info.get('budget', '未知')}[/green]")
        
        tech_node = opp_tree.add("🛠️ 技术/产品需求")
        for tech in opp_info.get("tech_stack", []):
            tech_node.add(tech)
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
    把记录保存到 JSON 文件 (总账) 和 独立文件 (小灶)
    """
    # 1. 存总账 (sales_data.json)
    data_path = get_data_path()
    
    if data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    
    # 补全时间戳
    now = datetime.datetime.now()
    record["created_at"] = now.isoformat()
    record["id"] = len(data) + 1
    
    data.append(record)
    
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 2. 存小灶 (独立文件) -> data/records/项目名-日期.json
    try:
        # 提取项目名作为文件名的一部分
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
        console.print(f"[bold red]小灶没存上，但这不影响总账：{e}[/bold red]")
    
    return record["id"]

@app.command()
def init():
    """
    初始化项目，检查配置和数据文件。
    """
    print("[green]正在初始化 LinkSell...[/green]")
    
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

    print("[bold green]初始化搞定！随时准备开干！[/bold green]")

@app.command()
def record(note_type: str = typer.Option(..., prompt="请输入记录类型(meeting/chat)"),
           content: str = typer.Option(..., prompt="请输入内容(或录音路径)")):
    """
    记录一条新的销售小记。
    """
    print(f"收到！类型：{note_type}, 内容：{content}")
    # 这里以后接火山引擎和豆包的逻辑
    print("[dim]（此处假装调用了高级AI进行处理...）[/dim]")

@app.command()
def analyze(content: str = typer.Option(None, "--content", "-c", help="要提炼的对话/会议内容"),
            save: bool = typer.Option(False, "--save", "-s", help="是否直接保存结果")):
    """
    [核心] 调用豆包大模型提炼销售小记，并选择是否保存。
    """
    # 如果没传 content，就现场问用户要
    if not content:
        console.print("[bold yellow]来，把你的会议记录或销售对话粘贴在这儿（按回车确认）：[/bold yellow]")
        content = typer.prompt("内容")

    console.print(Panel("[bold yellow]正在呼叫 AI 助手进行大脑风暴...[/bold yellow]", title="AI 思考中"))
    
    try:
        # 获取配置
        api_key = config.get("doubao", "api_key", fallback=None)
        endpoint_id = config.get("doubao", "analyze_endpoint", fallback=None)
        
        if not api_key or not endpoint_id or "YOUR_" in api_key:
            console.print("[bold red]哎呀！配置没填对！[/bold red]")
            console.print("快去 config/config.ini 把 API 密钥和接入点填上！")
            return

        # 调用服务
        from src.services.llm_service import analyze_text
        result = analyze_text(content, api_key, endpoint_id)
        
        if result:
            while True:
                # 使用新的人话展示函数
                display_result_human_readable(result)
                
                # 如果用户设置了自动保存，直接存
                if save:
                    record_id = save_to_db(result)
                    console.print(f"[bold blue]妥了！已保存，记录ID：{record_id}[/bold blue]")
                    break

                # 交互式询问
                choice = typer.prompt(
                    "老大哥问你：这结果咋样？(s:保存 / d:丢弃 / e:编辑)", 
                    default="s", 
                    show_default=False
                ).lower()

                if choice == 's':
                    record_id = save_to_db(result)
                    console.print(f"[bold blue]妥了！已保存，记录ID：{record_id}[/bold blue]")
                    break
                elif choice == 'd':
                    console.print("[dim]行，那这次就不存了，下次再来。[/dim]")
                    break
                elif choice == 'e':
                    # 调用系统编辑器
                    console.print("[yellow]正在启动编辑器... 改完记得保存并关闭编辑器哦！[/yellow]")
                    edited_json = typer.edit(json.dumps(result, indent=2, ensure_ascii=False), extension=".json")
                    
                    if edited_json:
                        try:
                            result = json.loads(edited_json)
                            console.print("[green]修改成功！正在重新渲染...[/green]")
                        except json.JSONDecodeError:
                            console.print("[bold red]你改的内容格式不对啊！JSON 破损了，还原回原来的版本。[/bold red]")
                    else:
                        console.print("[dim]你没改啥东西啊...[/dim]")
                else:
                    console.print("[red]别瞎输！只有 s, d, e 三个选项！[/red]")

        else:
            console.print("[red]AI 助手暂时没有响应，请稍后再试。[/red]")
            
    except Exception as e:
        console.print(f"[bold red]出错了：[/bold red] {e}")

if __name__ == "__main__":
    app()
