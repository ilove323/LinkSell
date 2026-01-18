import typer
import configparser
import json
import os
from pathlib import Path
from rich import print

app = typer.Typer()

# 读取配置
config = configparser.ConfigParser()
config_path = Path("config/config.ini")
if config_path.exists():
    config.read(config_path)
else:
    print("[bold red]配置文件 config/config.ini 没找着啊！赶紧整一个！[/bold red]")

@app.command()
def init():
    """
    初始化项目，检查配置和数据文件。
    """
    print("[green]正在初始化 LinkSell...[/green]")
    
    # 检查数据文件
    data_file = config.get("storage", "data_file", fallback="data/sales_data.json")
    data_path = Path(data_file)
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

if __name__ == "__main__":
    app()
