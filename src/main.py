import typer
import configparser
import json
import os
import datetime
from pathlib import Path
from rich import print
from rich.console import Console
from rich.panel import Panel

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

def save_to_db(record: dict):
    """
    把记录保存到 JSON 文件
    """
    data_path = get_data_path()
    
    # 读取现有数据
    if data_path.exists():
        with open(data_path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    
    # 添加时间戳
    record["created_at"] = datetime.datetime.now().isoformat()
    record["id"] = len(data) + 1
    
    # 追加新记录
    data.append(record)
    
    # 写入文件
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
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
def analyze(content: str = typer.Option(..., prompt="请粘贴要提炼的对话/会议内容"),
            save: bool = typer.Option(False, "--save", "-s", help="是否直接保存结果")):
    """
    [核心] 调用豆包大模型提炼销售小记，并选择是否保存。
    """
    console.print(Panel("[bold yellow]正在呼叫豆包大模型进行大脑风暴...[/bold yellow]", title="AI 思考中"))
    
    try:
        # 获取配置
        api_key = config.get("doubao", "api_key", fallback=None)
        endpoint_id = config.get("doubao", "model_endpoint_id", fallback=None)
        
        if not api_key or not endpoint_id or "YOUR_" in api_key:
            console.print("[bold red]哎呀！配置没填对！[/bold red]")
            console.print("快去 config/config.ini 把 [doubao] 下面的 api_key 和 model_endpoint_id 填上！")
            return

        # 调用服务
        from src.services.llm_service import analyze_text
        result = analyze_text(content, api_key, endpoint_id)
        
        if result:
            console.print(Panel(json.dumps(result, indent=2, ensure_ascii=False), title="[bold green]提炼结果[/bold green]"))
            
            # 如果用户没加 --save 参数，就问一句
            if not save:
                save = typer.confirm("这结果看着咋样？要不要存进数据库？")
            
            if save:
                record_id = save_to_db(result)
                console.print(f"[bold blue]妥了！已保存，记录ID：{record_id}[/bold blue]")
            else:
                console.print("[dim]行，那这次就不存了，下次再来。[/dim]")

        else:
            console.print("[red]豆包没反应，可能是累了（报错了）。[/red]")
            
    except Exception as e:
        console.print(f"[bold red]出错了：[/bold red] {e}")

if __name__ == "__main__":
    app()
