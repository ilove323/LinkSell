"""
LinkSell 程序入口 (Main Entry Point)

职责：
- 系统的统一启动入口
- 负责环境初始化路径配置
- 路由转发：根据参数启动 GUI 或 CLI 模式

特点：
- **Unified**: 统一管理所有启动指令 (init, chat, analyze)
- **Lazy Load**: 根据子命令动态导入模块，加快启动速度
"""

import typer
import sys
import os
from pathlib import Path
from rich import print

# [环境配置] 必须最先执行
# 将项目根目录添加到 sys.path，确保 src 模块可以被正确导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.controller import LinkSellController

# 初始化 Typer 应用和核心控制器
app = typer.Typer()
controller = LinkSellController()

def launch_gui():
    """
    [辅助函数] 启动 Streamlit 图形界面
    原理：使用 subprocess 启动一个新的 streamlit 进程
    """
    import subprocess
    print("[green]🚀 正在启动 LinkSell 图形界面...[/green]")
    
    # 定位 GUI 脚本路径
    gui_path = Path(__file__).parent / "gui" / "gui.py"
    
    try:
        # 阻塞式运行 Streamlit
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(gui_path)], check=True)
    except KeyboardInterrupt:
        print("\n[dim]👋 图形界面已关闭。[/dim]")

@app.command()
def init():
    """
    [命令] 初始化项目环境
    功能：创建必要的数据目录结构 (data/opportunities, data/records)
    """
    from src.cli.interface import console
    console.print("[green]🛠️ 正在初始化 LinkSell 系统...[/green]")
    
    # [核心逻辑] 确保数据存储目录存在
    opp_dir = Path("data/opportunities")
    opp_dir.mkdir(parents=True, exist_ok=True)
    
    # 兼容旧版的记录备份文件夹
    (Path("data") / "records").mkdir(parents=True, exist_ok=True)
    
    console.print("[bold green]✅ 初始化完成。数据目录：data/opportunities/[/bold green]")

@app.command()
def chat():
    """
    [命令] 启动 CLI 对话模式
    功能：进入纯命令行交互界面
    """
    from src.cli.cli import main
    main()

@app.command()
def analyze(content: str = typer.Option(None, "--content", "-c", help="要提炼的对话文本"),
            audio_file: str = typer.Option(None, "--audio", "-a", help="录音文件路径"),
            use_mic: bool = typer.Option(False, "--microphone", "-m", help="使用麦克风"),
            save: bool = typer.Option(False, "--save", "-s", help="直接保存"),
            debug: bool = typer.Option(False, "--debug", help="调试模式"),
            cli: bool = typer.Option(False, "--cli", help="使用新版命令行模式")):
    """
    [命令] 分析销售数据 (混合模式)
    默认启动图形界面 (GUI)。
    使用 --cli 参数可进入命令行模式。
    """
    # [路由逻辑] 根据参数分发到不同的处理模块
    if cli:
        from src.cli.cli import main
        main()
    elif not any([content, audio_file, use_mic]):
        # 如果没有任何输入参数，默认启动 GUI
        launch_gui()
    else:
        # [Legacy] 暂时兼容旧的单次分析接口
        from src.cli.interface import run_analyze
        run_analyze(content, audio_file, use_mic, save, debug)

@app.command()
def manage():
    """
    [命令] 进入商机管理控制台 (Legacy)
    已废弃，推荐使用 chat 命令。
    """
    from src.cli.interface import manage as run_manage
    run_manage()

if __name__ == "__main__":
    app()