import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wavfile
import threading
import sys
from rich.console import Console

console = Console()

def record_audio_until_enter(filename: str, samplerate=16000, channels=1):
    """
    录制音频直到用户按下回车键。
    
    Args:
        filename (str): 保存音频的文件路径 (建议 .wav)。
        samplerate (int): 采样率，默认 16000 (ASR 友好)。
        channels (int): 声道数，默认 1 (单声道)。
    
    Returns:
        bool: 录音是否成功。
    """
    try:
        # 检查设备
        # devices = sd.query_devices()
        # default_input = sd.default.device[0]
        
        recorded_data = []
        
        def callback(indata, frames, time, status):
            if status:
                print(f"[黄]录音状态异常: {status}[/黄]", file=sys.stderr)
            recorded_data.append(indata.copy())

        console.print("[bold green]🎙️ 录音准备就绪！[/bold green]")
        console.print("[bold cyan]请按回车键 (Enter) 开始录音...[/bold cyan]")
        input() # 等待第一次回车开始

        # 开始录音
        with sd.InputStream(samplerate=samplerate, channels=channels, callback=callback):
            console.print("[bold red]🔴 正在录音... (说完请按回车键停止)[/bold red]")
            input() # 等待第二次回车停止
        
        console.print("[dim]正在保存录音文件...[/dim]")
        
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
