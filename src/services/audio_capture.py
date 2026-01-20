"""
LinkSell 音频采集服务 (Audio Capture)

职责：
- 调用系统麦克风进行实时音频录制
- 将原始 PCM 数据编码并保存为 WAV 文件
- 处理录音设备的异常状态

特点：
- **Interactive**: 采用"按回车开始/停止"的交互模式
- **ASR Ready**: 默认使用 16kHz 采样率，适配大多数语音识别 API
"""

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import threading
import sys
from rich.console import Console

console = Console()

def record_audio_until_enter(filename: str, samplerate=16000, channels=1):
    """
    [核心功能] 录制音频直到用户按下回车键。
    这是一个阻塞式函数，适用于 CLI 交互。
    
    Args:
        filename (str): 保存音频的文件路径 (建议 .wav)。
        samplerate (int): 采样率，默认 16000 (火山引擎 ASR 推荐值)。
        channels (int): 声道数，默认 1 (单声道)。
    
    Returns:
        bool: 录音是否成功。
    """
    try:
        # 用于存储录制的原始数据块
        recorded_data = []
        
        # [回调函数] 当声卡有数据时自动调用
        def callback(indata, frames, time, status):
            if status:
                # 打印设备警告 (如 Buffer Overflow)
                print(f"[黄]录音状态异常: {status}[/黄]", file=sys.stderr)
            recorded_data.append(indata.copy())

        # 交互提示
        console.print("[bold green]🎙️ 录音准备就绪！[/bold green]")
        console.print("[bold cyan]请按回车键 (Enter) 开始录音...[/bold cyan]")
        input() # 等待第一次回车开始

        # [上下文管理器] 启动输入流
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
            console.print("[bold red]🔴 正在录音... (说完请按回车键停止)[/bold red]")
            input() # 等待第二次回车停止
        
        console.print("[dim]正在保存录音文件...[/dim]")
        
        # 将数据块拼接并写入文件
        if recorded_data:
            full_recording = np.concatenate(recorded_data, axis=0)
            wavfile.write(filename, samplerate, full_recording)
            console.print(f"[green]录音已保存：{filename}[/green]")
            return True
        else:
            console.print("[red]未录制到任何音频数据。[/red]")
            return False

    except Exception as e:
        console.print(f"[bold red]录音失败：{e}[/bold red]")
        console.print("请确保已安装 `portaudio` 库 (Mac: `brew install portaudio`) 并授予终端麦克风权限。")
        return False