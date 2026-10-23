r"""守护进程 —— 检查另外两个组件还活着没有，死了就拉起来。

为什么需要它：
  watch.py 死过一次（被外部强制终止），而 watch_think.py 还活着，还在往 say.txt
  写 —— 结果是有输入没输出，人只会听到沉默。计划任务只在登录时启动一次，
  进程被杀它察觉不到，所以需要一个定期检查的看门人。

怎么判断死活：
  看心跳文件的 mtime。每个组件每轮循环 touch 一下自己的 .beat，超过
  stale_seconds 就认为它死了。
  比枚举 pythonw 进程可靠得多 —— watch.py 和 watch_think.py 名字太像，
  按命令行匹配很容易认错。

用法：
    pythonw guard.py        （后台常驻）
"""
import subprocess
import sys
import time
from pathlib import Path

from config import (
    HOME, GUARD_LOG, GUARD_BEAT, WATCH_BEAT, THINK_BEAT,
    load_user_config,
)

CREATE_NO_WINDOW = 0x08000000


def log(msg):
    try:
        with open(GUARD_LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('[%H:%M:%S] ') + msg + '\n')
    except Exception:
        pass


def pythonw_path():
    """优先用 pythonw.exe —— 它不创建控制台，被拉起的组件也就没有窗口。"""
    exe = Path(sys.executable)
    if exe.name.lower() == 'pythonw.exe':
        return str(exe)
    alt = exe.with_name('pythonw.exe')
    return str(alt) if alt.exists() else str(exe)


def is_alive(beat, max_age):
    try:
        return (time.time() - beat.stat().st_mtime) < max_age
    except Exception:
        return False


def launch(script, label):
    if not script.exists():
        log('%s 脚本不存在: %s' % (label, script))
        return
    try:
        subprocess.Popen(
            [pythonw_path(), str(script)],
            creationflags=CREATE_NO_WINDOW,
            close_fds=True,
            cwd=str(HOME),
        )
        log('%s 心跳断了，已拉起' % label)
    except Exception as exc:
        log('%s 拉起失败: %s' % (label, exc))


def main():
    cfg = load_user_config()
    stale = int(cfg.get('stale_seconds', 90))
    interval = int(cfg.get('guard_interval', 30))

    log('=== 守护启动 ===')
    log('阈值 %ds / 每 %ds 检查一次' % (stale, interval))

    while True:
        try:
            GUARD_BEAT.touch()
            if not is_alive(WATCH_BEAT, stale):
                launch(HOME / 'watch.py', '朗读守候')
            if not is_alive(THINK_BEAT, stale):
                launch(HOME / 'watch_think.py', '思考提取器')
        except Exception as exc:
            log('循环异常: %s' % exc)
        time.sleep(interval)


if __name__ == '__main__':
    main()
