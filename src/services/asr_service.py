import json
import base64
from pathlib import Path
from rich import print

# 尝试导入 Volcengine SDK
try:
    from volcengine.asr.ASRService import ASRService
except ImportError:
    ASRService = None

def transcribe_audio(file_path: str, app_id: str, access_key: str, secret_key: str, cluster: str = "volcengine_input_common"):
    """
    调用火山引擎 ASR 服务进行语音转文字。
    
    使用“一句话识别” (Short Audio Recognition) 接口，适用于 60 秒以内的短语音。
    支持格式：wav, mp3, ogg, m4a 等。
    
    Args:
        file_path (str): 音频文件的本地路径。
        app_id (str): 火山引擎 ASR 应用 ID。
        access_key (str): 火山引擎 Access Key (AK)。
        secret_key (str): 火山引擎 Secret Key (SK)。
        cluster (str, optional): 业务集群名称。默认为 "volcengine_input_common"。

    Returns:
        str: 识别后的文本内容。如果识别失败或发生错误，返回 None。
    """
    if not ASRService:
        print("[bold red]错误：未检测到 `volcengine` SDK。[/bold red]")
        print("请运行: pip install volcengine-python-sdk")
        return None

    p = Path(file_path)
    if not p.exists():
        print(f"[red]错误：文件不存在：{file_path}[/red]")
        return None

    # 初始化 ASR 服务并配置鉴权
    service = ASRService()
    service.set_ak(access_key)
    service.set_sk(secret_key)

    # 读取音频文件并编码为 base64
    try:
        with open(p, "rb") as f:
            audio_data = f.read()
            base64_data = base64.b64encode(audio_data).decode("utf-8")
    except Exception as e:
        print(f"[red]文件读取错误：{e}[/red]")
        return None

    # 构造请求参数
    # 参考文档：https://www.volcengine.com/docs/6561/80618
    req = {
        "app": {
            "appid": app_id,
            "cluster": cluster,
            "token": "access_token", # 鉴权模式下 token 可由 SDK 自动处理
        },
        "user": {
            "uid": "linksell_cli_user"
        },
        "audio": {
            "format": p.suffix.replace(".", ""), # 去除点号，如 wav, mp3
            "data": base64_data
        }
    }

    print("[dim]正在发送音频至火山引擎 ASR 服务...[/dim]")
    
    try:
        # 调用全双工/一句话识别接口
        resp = service.all_talk(req)
        result = json.loads(resp)
        
        if "result" in result and len(result["result"]) > 0 and "text" in result["result"][0]:
            text = result["result"][0]["text"]
            print(f"[green]识别成功：[/green] {text}")
            return text
        else:
            # 处理 API 返回的错误信息
            if "message" in result:
                print(f"[bold red]ASR 接口返回错误：{result['message']}[/bold red]")
            else:
                print(f"[red]无法解析的响应：{result}[/red]")
            return None

    except Exception as e:
        print(f"[bold red]ASR 服务调用异常：{e}[/bold red]")
        return None