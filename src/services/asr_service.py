"""LinkSell ASR 服务 (Voice Recognition Service)

职责：
- 对接火山引擎 (Volcengine) 大模型语音识别 API
- 处理音频文件的读取、编码与上传
- 执行"提交任务 -> 轮询结果"的异步识别流程

特点：
- **Direct Mode**: 使用直连域名绕过部分网络限制
- **Robust Network**: 强制禁用系统代理 (trust_env=False) 以解决 VPN 环境下的 SSL 握手问题
- **Async Polling**: 采用轮询机制支持长语音识别
"""

import requests
import uuid
import time
import json
import base64
from pathlib import Path
from rich import print

def transcribe_audio(file_path: str, app_id: str, access_token: str, resource_id: str = "volc.bigasr.auc", cluster: str = "volcengine_input_common", debug: bool = False):
    """
    [核心功能] 执行音频转写任务
    
    参数详解:
    - file_path: 本地音频文件的绝对路径
    - app_id: 火山引擎的应用 ID
    - access_token: API 访问令牌
    - resource_id: 资源标识符 (默认: volc.bigasr.auc)
    
    返回:
    - str: 识别出的文本内容
    - None: 如果识别失败
    """
    
    # [步骤 1] 校验文件有效性
    # 确保文件存在，避免后续无效的网络请求
    p = Path(file_path)
    if not p.exists():
        print(f"[red]错误：文件不存在：{file_path}[/red]")
        return None

    # [步骤 2] 音频文件编码
    # API 要求音频数据必须是 Base64 编码的字符串
    try:
        with open(p, "rb") as f:
            audio_data = f.read()
            # 将二进制流转为 UTF-8 字符串格式的 Base64
            base64_data = base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"[red]音频读取失败：{e}[/red]")
        return None

    # [步骤 3] 初始化网络会话 (关键修复)
    # 使用 Session 可以复用 TCP 连接，提高性能
    session = requests.Session()
    
    # [特别说明] trust_env = False
    # 强制让 requests 忽略系统环境变量中的 HTTP_PROXY/HTTPS_PROXY
    # 解决开启 VPN/代理 导致的 SSLEOFError (握手中断) 问题
    session.trust_env = False 

    # [配置] 任务提交接口
    # 使用 Direct 地址以获得更好的连通性
    submit_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/submit"
    
    # 生成唯一的 Request ID，用于追踪任务
    task_id = str(uuid.uuid4())

    # 构建 HTTP 请求头
    headers = {
        "X-Api-App-Key": app_id,
        "X-Api-Access-Key": access_token,
        "X-Api-Resource-Id": resource_id,
        "X-Api-Request-Id": task_id,
        "X-Api-Sequence": "-1"
    }

    # 构建请求体 (Payload)
    # 包含用户信息、音频数据格式、以及大模型的具体参数开关
    payload = {
        "user": {"uid": "linksell_cli_user"},
        "audio": {
            "format": p.suffix.replace(".", ""), # 自动提取文件后缀 (如 wav, mp3)
            "data": base64_data 
        },
        "request": {
            "model_name": "bigmodel",
            "enable_channel_split": True, # 启用分轨
            "enable_ddc": True,           # 启用去重
            "enable_speaker_info": True,  # 启用说话人分离
            "enable_punc": True,          # 启用标点符号
            "enable_itn": True            # 启用逆文本标准化 (数字转汉字等)
        }
    }

    try:
        # [步骤 4] 发送提交请求
        # 设置 30秒 超时，防止网络卡死
        resp = session.post(submit_url, headers=headers, json=payload, timeout=30)
        status_code = resp.headers.get("X-Api-Status-Code")
        
        # 校验提交状态 (20000000 代表成功)
        if status_code != "20000000":
            print(f"[bold red]任务提交失败 (Status: {status_code})[/bold red]")
            return None
        
        # 获取 LogID，后续查询必须带上
        x_tt_logid = resp.headers.get("X-Tt-Logid", "")
        
        # [配置] 结果查询接口
        query_url = "https://openspeech-direct.zijieapi.com/api/v3/auc/bigmodel/query"
        query_headers = {
            "X-Api-App-Key": app_id,
            "X-Api-Access-Key": access_token,
            "X-Api-Resource-Id": resource_id,
            "X-Api-Request-Id": task_id,
            "X-Tt-Logid": x_tt_logid
        }

        # [步骤 5] 轮询查询结果 (Polling Loop)
        # 因为大模型识别需要时间，必须循环检查任务状态
        while True:
            # 避免请求过于频繁，每次间隔 1 秒
            time.sleep(1)
            
            # 发起查询请求
            query_resp = session.post(query_url, headers=query_headers, json={}, timeout=10)
            q_status = query_resp.headers.get("X-Api-Status-Code")
            
            # Case A: 任务完成 (Success)
            if q_status == "20000000":
                result = query_resp.json()
                if debug: print(f"[dim]Debug: {json.dumps(result, ensure_ascii=False)}[/dim]")
                
                # 提取识别文本：不同版本的 API 返回结构略有不同，做兼容处理
                if "result" in result and isinstance(result["result"], dict):
                    return result["result"].get("text", "")
                elif "result" in result and isinstance(result["result"], list) and len(result["result"]) > 0:
                    return result["result"][0].get("text", "")
                elif "resp_data" in result:
                    return str(result['resp_data'])
                return ""
                
            # Case B: 任务处理中 (Pending)
            elif q_status in ["20000001", "20000002"]:
                continue # 继续下一轮循环
                
            # Case C: 任务失败 - 静音或无效音频
            elif q_status == "20000003":
                print("[bold red]🎙️ ASR 识别失败：音频静音或音量过小。请大声点儿，或者检查麦克风权限！[/bold red]")
                return None
                
            # Case D: 其他未知错误
            else:
                print(f"[bold red]查询失败 (Status: {q_status})[/bold red]")
                return None

    except Exception as e:
        print(f"[bold red]ASR 调用异常：{e}[/bold red]")
        return None
