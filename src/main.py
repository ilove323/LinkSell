import typer
import sys
import os
from pathlib import Path

# 将项目根目录添加到 sys.path，解决模块导入路径问题
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.controller import LinkSellController

app = typer.Typer()
controller = LinkSellController()

def launch_gui():
    """启动 Streamlit 图形界面"""
    import subprocess
    print("[green]正在启动 LinkSell 图形界面...[/green]")
    gui_path = Path(__file__).parent / "gui" / "app.py"
    try:
        # 使用 sys.executable -m streamlit 确保使用当前虚拟环境
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(gui_path)], check=True)
    except KeyboardInterrupt:
        print("\n[dim]图形界面已关闭。[/dim]")

@app.command()
def init():
    """初始化项目环境，检查配置文件及数据目录结构"""
    from src.cli.interface import console
    console.print("[green]正在初始化 LinkSell 系统...[/green]")
    data_file = Path(controller.config.get("storage", "data_file", fallback="data/sales_data.json"))
    data_file.parent.mkdir(parents=True, exist_ok=True)
    if not data_file.exists():
        import json
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump([], f)
    (data_file.parent / "records").mkdir(parents=True, exist_ok=True)
    console.print("[bold green]初始化完成。[/bold green]")

@app.command()
def analyze(content: str = typer.Option(None, "--content", "-c", help="要提炼的对话文本"),
            audio_file: str = typer.Option(None, "--audio", "-a", help="录音文件路径"),
            use_mic: bool = typer.Option(False, "--microphone", "-m", help="使用麦克风"),
            save: bool = typer.Option(False, "--save", "-s", help="直接保存"),
            debug: bool = typer.Option(False, "--debug", help="调试模式"),
            cli: bool = typer.Option(False, "--cli", help="使用命令行模式")):
    """
    分析销售数据。默认启动图形界面 (GUI)。
    使用 --cli 参数进入命令行模式。
    """
    if not cli and not any([content, audio_file, use_mic]):
        launch_gui()
    else:
        # 移交指挥权给 CLI 接口模块
        from src.cli.interface import run_analyze
        run_analyze(content, audio_file, use_mic, save, debug)

if __name__ == "__main__":
    app()
