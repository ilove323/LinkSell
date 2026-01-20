"""
LinkSell CLI 主程序

职责：
- 与用户交互（接收输入）
- 调用对话引擎处理业务逻辑
- 展示对话引擎返回的结果 (纯文本渲染)

特点：
- 纯UI层，不包含业务逻辑
- 简洁清晰的分层设计
- 移除所有复杂表格/UI组件，仅负责 Print Engine 的输出
"""

import typer
import importlib
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

# 强制重载核心模块（确保最新代码生效）
import src.core.controller
importlib.reload(src.core.controller)
import src.core.conversational_engine
importlib.reload(src.core.conversational_engine)

from src.core.conversational_engine import ConversationalEngine

console = Console()
engine = ConversationalEngine()
cli_app = typer.Typer()

@cli_app.command()
def main():
    """
    LinkSell CLI 主交互循环
    """
    console.print(Panel(
        "[bold cyan]欢迎使用 LinkSell 销售助手 (v3.1)[/bold cyan]\n"
        "[dim]直接输入需求即可，例如：'查看沈阳项目'、'把预算改了'、'记录笔记...'[/dim]",
        style="cyan",
        title="LinkSell Chat"
    ))
    
    while True:
        try:
            # 1. 接收输入
            user_input = typer.prompt("您说").strip()
            if not user_input: continue
            if user_input.lower() in ["q", "quit", "exit", "退出", "再见"]:
                console.print("[dim]好的，老哥再见！[/dim]")
                break
            
            # 2. 调用引擎处理
            result = engine.handle_user_input(user_input)
            
            # 3. 展示文本消息
            if result.get("message"):
                console.print(f"\n{result['message']}")
            
            # 4. 展示自动匹配提示
            if result.get("auto_matched"):
                console.print("[dim]💡 (系统已自动锁定当前商机上下文)[/dim]")
            
            # 5. 展示结构化详情报告 (Markdown 渲染)
            if result.get("report_text"):
                console.print("")
                console.print(Panel(Markdown(result["report_text"]), border_style="green", padding=(1, 2)))
                console.print("")

            # 6. 错误处理
            if result.get("type") == "error":
                console.print(f"[red]❌ {result.get('message', '未知错误')}[/red]")

        except KeyboardInterrupt:
            console.print("\n[dim]程序已手动中断。[/dim]")
            break
        except Exception as e:
            console.print(f"[red]程序出岔子了：{str(e)}[/red]")

if __name__ == "__main__":
    cli_app()