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

    # 初始化 Session，配置绕过系统代理
    session = requests.Session()
    session.trust_env = False  # 关键：绕过系统代理/VPN，防止 SSL EOF 错误

    # 1. 提交任务
    submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
    task_id = str(uuid.uuid4())

    headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": task_id,
        "X-Api-Sequence": "-1"
    }

    payload = {
        "user": {"uid": "linksell_cli_user"},
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

    try:
        resp = session.post(submit_url, headers=headers, json=payload, timeout=30)
        status_code = resp.headers.get("X-Api-Status-Code")
        
        if status_code != "20000000":
            print(f"[bold red]任务提交失败 (Status: {status_code})[/bold red]")
            return None
        
        x_tt_logid = resp.headers.get("X-Tt-Logid", "")
        
        # 2. 轮询查询结果
        query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"
        query_headers = {
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": task_id,
            "X-Tt-Logid": x_tt_logid
        }

        while True:
            time.sleep(1)
            query_resp = session.post(query_url, headers=query_headers, json={}, timeout=10)
            q_status = query_resp.headers.get("X-Api-Status-Code")
            
            if q_status == "20000000":
                result = query_resp.json()
                if debug: print(f"[dim]Debug: {json.dumps(result, ensure_ascii=False)}[/dim]")
                
                if "result" in result and isinstance(result["result"], dict):
                    return result["result"].get("text", "")
                elif "result" in result and isinstance(result["result"], list) and len(result["result"]) > 0:
                    return result["result"][0].get("text", "")
                elif "resp_data" in result:
                    return str(result['resp_data'])
                return ""
            elif q_status in ["20000001", "20000002"]:
                continue
            elif q_status == "20000003":
                print("[bold red]🎙️ ASR 识别失败：音频静音或音量过小。请大声点儿，或者检查麦克风权限！[/bold red]")
                return None
            else:
                print(f"[bold red]查询失败 (Status: {q_status})[/bold red]")
                return None

    except Exception as e:
        print(f"[bold red]ASR 调用异常：{e}[/bold red]")
        return None