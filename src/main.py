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
    
    # 改为创建商机文件夹
    opp_dir = Path("data/opportunities")
    opp_dir.mkdir(parents=True, exist_ok=True)
    
    # 记录备份文件夹
    (Path("data") / "records").mkdir(parents=True, exist_ok=True)
    
    console.print("[bold green]初始化完成。数据目录：data/opportunities/[/bold green]")

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

@app.command()
def manage():
    """
    进入商机管理控制台 (CLI)。
    支持查看、搜索、修改及删除历史商机。
    """
    # 移交指挥权给 CLI 接口模块
    from src.cli.interface import manage as run_manage
    run_manage()

if __name__ == "__main__":
    app()
