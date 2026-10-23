r"""朗读守候 —— 监听 say.txt，变化就合成播放。

链路：
    say.txt 变化
      → edge-tts 合成 mp3
      → ffmpeg 转 wav（降音量、削高频）
      → winsound 同步播放

为什么用文件当信号：
  DSH 的客户端插件拿不到消息正文（assistant-actions 只给 messageId），而猜测
  DOM 结构太脆。文件是最简单可靠的跨进程通道 —— 谁来写都行，agent 可以写，
  别的脚本也可以写。

为什么用 pythonw 跑：
  它是 GUI 子系统的解释器，不创建控制台，所以全程没有任何窗口。用
  powershell -File 启动的话，即使 -WindowStyle Hidden 也会先闪一个黑框。

用法：
    pythonw watch.py        （后台常驻）
    往 say.txt 写一句话      （就会念出来）
"""
import subprocess
import sys
import time
import winsound

from config import (
    SAY, MP3, WAV, WATCH_LOG, WATCH_BEAT,
    load_user_config, audio_filter, find_executable,
)

CREATE_NO_WINDOW = 0x08000000   # Windows: 子进程不分配控制台
POLL = 0.5


def log(msg):
    try:
        with open(WATCH_LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('[%H:%M:%S] ') + msg + '\n')
    except Exception:
        pass


def resolve_tools():
    """找到 python 和 ffmpeg。找不到就报出来，别静默失败。"""
    python = sys.executable
    # pythonw 没有 stdout，但 edge-tts 是作为模块调用的，用解释器自己即可
    if python.lower().endswith('pythonw.exe'):
        # 用同目录的 python.exe 跑模块，输出不会丢
        alt = python[:-11] + 'python.exe'
        import os
        if os.path.exists(alt):
            python = alt

    ffmpeg = find_executable('ffmpeg', [
        r'C:\Program Files\ffmpeg\bin\ffmpeg.exe',
        r'C:\ffmpeg\bin\ffmpeg.exe',
    ])
    return python, ffmpeg


def synth(text, python, cfg):
    try:
        if MP3.exists():
            MP3.unlink()
        subprocess.run(
            [python, '-m', 'edge_tts', '--voice', cfg['voice'],
             '--text', text, '--write-media', str(MP3)],
            capture_output=True, timeout=90,
            creationflags=CREATE_NO_WINDOW,
        )
        return MP3.exists() and MP3.stat().st_size > 0
    except Exception as exc:
        log('合成异常: %s' % exc)
        return False


def transcode(ffmpeg, cfg):
    if not ffmpeg:
        return False
    try:
        if WAV.exists():
            WAV.unlink()
        subprocess.run(
            [ffmpeg, '-y', '-i', str(MP3), '-ar', '24000', '-ac', '1',
             '-af', audio_filter(cfg), '-loglevel', 'quiet', str(WAV)],
            capture_output=True, timeout=90,
            creationflags=CREATE_NO_WINDOW,
        )
        return WAV.exists() and WAV.stat().st_size > 0
    except Exception as exc:
        log('转码异常: %s' % exc)
        return False


def main():
    cfg = load_user_config()
    python, ffmpeg = resolve_tools()

    log('=== 朗读守候启动 ===')
    log('目录 %s' % SAY.parent)
    log('音色 %s / 音量 %s / 滤镜 %s' % (cfg['voice'], cfg['volume'], audio_filter(cfg)))
    if not ffmpeg:
        log('⚠ 没找到 ffmpeg，将直接播放 mp3（音量和滤波不生效）')

    last_mtime = 0.0
    last_text = ''

    while True:
        try:
            WATCH_BEAT.touch()

            if SAY.exists():
                mtime = SAY.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    time.sleep(0.25)          # 等写入落盘
                    text = (SAY.read_text(encoding='utf-8', errors='replace') or '').strip()
                    if text and text != last_text:
                        last_text = text
                        if len(text) > cfg['max_chars']:
                            text = text[:cfg['max_chars']]
                        log('收到 %d 字: %s' % (len(text), text[:48]))

                        if not synth(text, python, cfg):
                            log('合成失败（检查网络 / edge-tts 是否安装）')
                        else:
                            played = False
                            if ffmpeg and transcode(ffmpeg, cfg):
                                try:
                                    winsound.PlaySound(str(WAV), winsound.SND_FILENAME)
                                    played = True
                                except Exception as exc:
                                    log('播放异常: %s' % exc)
                            if not played:
                                # ffmpeg 缺失时的退路：直接播 mp3
                                try:
                                    winsound.PlaySound(str(MP3), winsound.SND_FILENAME)
                                    played = True
                                except Exception as exc:
                                    log('直接播 mp3 失败: %s' % exc)
                            if played:
                                log('播完')
        except Exception as exc:
            log('循环异常: %s' % exc)
        time.sleep(POLL)


if __name__ == '__main__':
    main()
