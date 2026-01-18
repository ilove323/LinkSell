import json
import base64
import requests
import uuid
import time
from pathlib import Path
from rich import print

def transcribe_audio(file_path: str, app_id: str, access_token: str, resource_id: str = "volc.bigasr.auc", cluster: str = "volcengine_input_common", debug: bool = False):
    """
    依照用户验证成功的 DEMO 实现的火山引擎 ASR 大模型任务处理。
    采用“提交任务 -> 轮询查询”模式。
    使用 Direct 接口地址以确保稳定性。
    """
    p = Path(file_path)
    if not p.exists():
        print(f"[red]错误：文件不存在：{file_path}[/red]")
        return None

    # 将本地音频转为 Base64
    try:
        with open(p, "rb") as f:
            audio_data = f.read()
            base64_data = base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"[red]音频读取失败：{e}[/red]")
        return None

    # 1. 提交任务
    # 使用用户 DEMO 中的 Direct 域名
    submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
    task_id = str(uuid.uuid4())

    headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": task_id,
        "X-Api-Sequence": "-1"
    }

    # 构造请求体
    payload = {
        "user": {
            "uid": "linksell_cli_user"
        },
        "audio": {
            "format": p.suffix.replace(".", ""),
            "data": base64_data 
        },
        "request": {
            "model_name": "bigmodel",
            "enable_channel_split": True,
            "enable_ddc": True,
            "enable_speaker_info": True,
            "enable_punc": True,
            "enable_itn": True
        }
    }

    if debug:
        print(f"[dim]正在提交 ASR 任务 (ID: {task_id})...[/dim]")
        print(f"[dim]使用 Resource ID: {resource_id}[/dim]")
    
    try:
        resp = requests.post(submit_url, headers=headers, json=payload, timeout=30)
        status_code = resp.headers.get("X-Api-Status-Code")
        
        if status_code != "20000000":
            print(f"[bold red]任务提交失败 (Status: {status_code})[/bold red]")
            if debug:
                print(f"[dim]{resp.text}[/dim]")
            return None
        
        x_tt_logid = resp.headers.get("X-Tt-Logid", "")
        
        # 2. 轮询查询结果
        query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"
        if debug:
            print("[dim]任务已提交，正在等待识别结果...[/dim]")
        
        query_headers = {
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": task_id,
            "X-Tt-Logid": x_tt_logid
        }

        while True:
            time.sleep(1) # 休息一秒再查
            query_resp = requests.post(query_url, headers=query_headers, json={}, timeout=10)
            q_status = query_resp.headers.get("X-Api-Status-Code")
            
            if q_status == "20000000": # 成功完成
                result = query_resp.json()
                
                # 仅在 debug 模式下打印
                if debug:
                    print(f"[dim]Debug: {json.dumps(result, ensure_ascii=False)}[/dim]")
                
                # 兼容不同的返回结构
                # 结构 A: {"result": {"text": "...", "utterances": [...]}} (Seed ASR)
                if "result" in result and isinstance(result["result"], dict):
                    text = result["result"].get("text", "")
                    return text

                # 结构 B: {"result": [{"text": "..."}]} (Big Model ASR 旧版/部分接口)
                elif "result" in result and isinstance(result["result"], list) and len(result["result"]) > 0:
                    text = result["result"][0].get("text", "")
                    return text
                
                # 结构 C: {"resp_data": "..."} (其他)
                elif "resp_data" in result:
                    return str(result['resp_data'])

                else:
                    print(f"[yellow]任务完成但未提取到文本。完整响应：{result}[/yellow]")
                    return ""
            elif q_status in ["20000001", "20000002"]: # 排队中或处理中
                continue
            else:
                print(f"[bold red]查询失败 (Status: {q_status})[/bold red]")
                if debug:
                    print(f"[dim]{query_resp.text}[/dim]")
                return None

    except Exception as e:
        import traceback
        print(f"[bold red]ASR 调用过程发生异常：{e}[/bold red]")
        print(f"[dim]{traceback.format_exc()}[/dim]")
        return None
