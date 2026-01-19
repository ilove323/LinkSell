"""
LinkSell CLI 主程序

职责：
- 与用户交互（接收输入）
- 调用对话引擎处理业务逻辑
- 展示对话引擎返回的结果

特点：
- 纯UI层，不包含业务逻辑
- 简洁清晰的分层设计
"""

import typer
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text

from src.core.conversational_engine import ConversationalEngine

console = Console()
engine = ConversationalEngine()
cli_app = typer.Typer()

# ==================== UI 工具函数 ====================

def _safe_str(value):
    """安全字符串转换"""
    if not value:
        return "N/A"
    return str(value)


def load_ui_templates():
    """加载UI话术模板"""
    templates = {}
    templates_path = Path("config/ui_templates.json")
    if templates_path.exists():
        try:
            with open(templates_path, "r", encoding="utf-8") as f:
                templates = json.load(f)
        except Exception as e:
            console.print(f"[yellow]警告：UI语料库加载失败({e})，将使用默认提示。[/yellow]")
    return templates


ui_templates = load_ui_templates()


def get_random_ui(key: str, **kwargs) -> str:
    """获取随机的UI话术"""
    if key in ui_templates and isinstance(ui_templates[key], list):
        import random
        text = random.choice(ui_templates[key])
        return text.format(**kwargs) if kwargs else text
    
    # 默认话术
    defaults = {
        "modification_processing": "好的，正在为您修改...",
        "operation_cancel": "操作已取消。",
        "analysis_start": "AI正在分析数据...",
    }
    return defaults.get(key, key)


# ==================== 展示函数 ====================

def display_opportunity_detail(data: dict):
    """
    展示商机详细信息（GET操作的结果）
    """
    # 标题
    p_name = data.get("project_opportunity", {}).get("project_name")
    if not p_name:
        p_name = data.get("project_name", "未命名项目")
    
    console.print(Panel(
        f"[bold white]{p_name}[/bold white]",
        style="bold green",
        title="商机档案",
        title_align="left"
    ))

    # 基本信息表格
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    
    type_map = {"chat": "随手记/闲聊", "meeting": "正式会议"}
    table.add_row(
        "🗣️ 记录类型",
        _safe_str(type_map.get(data.get("record_type"), data.get("record_type")))
    )
    table.add_row("👨‍💼 我方销售", _safe_str(data.get("sales_rep", "未知")))
    table.add_row("📝 核心摘要", _safe_str(data.get("summary", "暂无")))
    
    sentiment = data.get("sentiment", "未知")
    sentiment_color = "green" if "积极" in str(sentiment) else (
        "red" if "消极" in str(sentiment) else "yellow"
    )
    table.add_row(
        "😊 客户态度",
        f"[{sentiment_color}]{_safe_str(sentiment)}[/{sentiment_color}]"
    )
    console.print(table)
    console.print("")

    # 客户画像
    cust_tree = Tree("[bold blue]👤 客户画像[/bold blue]")
    cust = data.get("customer_info", {})
    if cust:
        cust_tree.add(f"姓名: [bold]{_safe_str(cust.get('name', 'N/A'))}[/bold]")
        cust_tree.add(f"公司: {_safe_str(cust.get('company', 'N/A'))}")
        cust_tree.add(f"职位: {_safe_str(cust.get('role', 'N/A'))}")
        cust_tree.add(f"联系方式: {_safe_str(cust.get('contact', 'N/A'))}")
    else:
        cust_tree.add("[dim]未提取到有效信息[/dim]")
    console.print(cust_tree)
    console.print("")

    # 商机概览
    opp_tree = Tree("[bold gold1]💰 商机概览[/bold gold1]")
    opp = data.get("project_opportunity", {})
    if opp:
        is_new = '新项目' if opp.get('is_new_project') else '既有项目'
        opp_tree.add(f"属性: {is_new}")
        
        stage_key = str(opp.get("opportunity_stage", ""))
        stage_name = engine.controller.stage_map.get(stage_key, "未知")
        opp_tree.add(f"阶段: [blue]{_safe_str(stage_name)}[/blue]")
        
        opp_tree.add(f"预算: [green]{_safe_str(opp.get('budget', '未知'))}[/green]")
        opp_tree.add(f"时间: {_safe_str(opp.get('timeline', '未知'))}")
        
        comp_node = opp_tree.add("⚔️ 竞争对手")
        for c in opp.get("competitors", []):
            comp_node.add(str(c))
        
        staff_node = opp_tree.add("🧑‍💻 我方技术人员")
        for s in opp.get("technical_staff", []):
            staff_node.add(str(s))
    else:
        opp_tree.add("[dim]暂未发现明确商机[/dim]")
    console.print(opp_tree)
    console.print("")

    # 关键点和待办事项
    if opp:
        grid = Table.grid(expand=True, padding=1)
        grid.add_column()
        grid.add_column()
        
        kp_text = Text()
        kp_text.append("📌 关键点：\n", style="bold magenta")
        for idx, p in enumerate(opp.get("key_points", []), 1):
            kp_text.append(f"{idx}. {p}\n")
        
        act_text = Text()
        act_text.append("✅ 待办事项：\n", style="bold red")
        for idx, a in enumerate(opp.get("action_items", []), 1):
            act_text.append(f"{idx}. {a}\n")
        
        grid.add_row(Panel(kp_text, expand=True), Panel(act_text, expand=True))
        console.print(grid)
    
    # 跟进记录
    logs_tree = Tree("[bold purple]📜 跟进记录[/bold purple]")
    record_logs = data.get("record_logs", [])
    if record_logs:
        recent_logs = sorted(record_logs, key=lambda x: x.get("time", ""), reverse=True)[:3]
        for log in recent_logs:
            log_time = log.get("time", "未知时间")
            recorder = log.get("recorder", "未知")
            content = log.get("content", "")
            logs_tree.add(f"[dim]{log_time}[/dim] @{recorder}\n{content}")
    else:
        logs_tree.add("[dim]暂无跟进记录[/dim]")
    console.print(logs_tree)


def display_opportunity_list(results: list, search_term: str = "全部", total_count: int = 0):
    """
    展示商机列表（LIST操作的结果）
    """
    if not results:
        console.print("[yellow]暂未找到相关商机。[/yellow]")
        return
    
    table = Table(
        title=f"📋 找到 {len(results)} 条商机",
        show_header=True,
        header_style="bold magenta"
    )
    table.add_column("ID", width=12)
    table.add_column("项目名称")
    table.add_column("阶段")
    table.add_column("销售")
    
    for opp in results:
        pid = str(opp.get("id", "未知"))
        pname = _safe_str(
            opp.get("project_opportunity", {}).get("project_name", opp.get("project_name", "未知"))
        )
        stage_code = str(opp.get("project_opportunity", {}).get("opportunity_stage", "-"))
        stage_name = _safe_str(engine.controller.stage_map.get(stage_code, stage_code))
        sales = _safe_str(opp.get("sales_rep", "-"))
        
        table.add_row(pid, pname, stage_name, sales)
    
    console.print(table)


def display_candidates(candidates: list):
    """显示多个候选商机"""
    console.print("[yellow]找到多个相关商机，请选择：[/yellow]")
    for idx, cand in enumerate(candidates, 1):
        cid = cand.get('id', '无ID')
        cname = cand.get('name', '未命名')
        console.print(f"[{idx}] [bold cyan]{cid}[/bold cyan] : {cname}")


def display_error(message: str):
    """显示错误信息"""
    console.print(f"[red]{message}[/red]")


def display_success(message: str):
    """显示成功信息"""
    console.print(f"[bold green]{message}[/bold green]")


# ==================== 主交互循环 ====================

@cli_app.command()
def main(use_voice: bool = False):
    """
    LinkSell CLI 主程序
    """
    console.print(Panel(
        "[bold cyan]欢迎使用 LinkSell 销售助手[/bold cyan]\n"
        "[dim]输入商机名称查看详情，输入'创建'新建商机，输入'q'退出[/dim]",
        style="cyan"
    ))
    
    while True:
        try:
            user_input = typer.prompt("您说").strip()
            if not user_input:
                continue
            if user_input.lower() in ["q", "quit", "exit", "退出"]:
                console.print("[dim]再见！[/dim]")
                break
            # 只调用engine统一入口
            result = engine.handle_user_input(user_input)
            result_type = result.get("type")
            if result_type == "detail":
                if result.get("auto_matched"):
                    console.print("[dim]未检测到明确对象，已自动锁定当前商机[/dim]")
                console.clear()
                display_opportunity_detail(result.get("data"))
            elif result_type == "list":
                display_opportunity_list(result.get("results", []), result.get("search_term", ""))
            elif result_type == "create":
                console.print(f"[bold cyan]{result.get('message','')}[/bold cyan]")
                if result.get("missing_fields"):
                    console.print(Panel(
                        "[yellow]⚠️ 以下字段信息不完整：\n" +
                        "\n".join(f"  - {v[0]}" for v in result["missing_fields"].values()),
                        style="yellow"
                    ))
                display_opportunity_detail(result.get("draft"))
            elif result_type == "update":
                console.print(f"[bold green]{result.get('message','')}[/bold green]")
                console.clear()
                display_opportunity_detail(result.get("data"))
            elif result_type == "delete":
                if result["status"] == "confirm_needed":
                    console.print(Panel(result["warning"], style="red", title="⚠️ 删除确认"))
                    display_opportunity_detail(result["data"])
                elif result["status"] == "not_found":
                    display_error(result["message"])
                elif result["status"] == "ambiguous":
                    display_candidates(result["candidates"])
                elif result["status"] == "success":
                    display_success(result["message"])
            elif result_type == "record":
                console.print(Panel(
                    f"📝 [bold green]{result['message']}[/bold green]\n\n[dim]{result['polished_content']}[/dim]",
                    style="green"
                ))
                console.print("[dim]您可以继续输入内容追加笔记，或说'创建'进行提交。[/dim]")
            elif result_type == "error":
                display_error(result.get("message","未知错误"))
            else:
                display_error("未能识别的响应类型")
        except KeyboardInterrupt:
            console.print("\n[dim]程序已中断。[/dim]")
            break
        except Exception as e:
            console.print(f"[red]发生错误：{str(e)}[/red]")


if __name__ == "__main__":
    cli_app()
