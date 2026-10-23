r"""配置 —— 所有路径集中在这里。

开源版不能把路径写死成 某个固定目录：别人拿到跑不起来。

优先顺序：
  1. 环境变量 DSH_VOICE_HOME
  2. 默认 ~/.dsh/voice-stack（DSH 用户的家目录下，跟其它插件一致）

音色、音量这类也可以在这里改，或者写 config.json 覆盖（见 load_user_config）。
"""
import json
import os
from pathlib import Path

# ---- 目录 ----
HOME = Path(os.environ.get('DSH_VOICE_HOME', Path.home() / '.dsh' / 'voice-stack'))
HOME.mkdir(parents=True, exist_ok=True)

# ---- 文件 ----
SAY = HOME / 'say.txt'            # 要念的话（whoever writes here gets spoken）
MP3 = HOME / 'say.mp3'
WAV = HOME / 'say.wav'
STATE_FILE = HOME / 'think_state.json'   # 思考提取器记住上次念到哪条

WATCH_LOG = HOME / 'watch.log'
THINK_LOG = HOME / 'think.log'
GUARD_LOG = HOME / 'guard.log'

WATCH_BEAT = HOME / 'watch.beat'
THINK_BEAT = HOME / 'think.beat'
GUARD_BEAT = HOME / 'guard.beat'

USER_CONFIG = HOME / 'config.json'

# ---- 默认参数 ----
DEFAULTS = {
    # 音色：edge-tts 的中文音色
    #   zh-CN-XiaoxiaoNeural  女声，温暖（默认）
    #   zh-CN-XiaoyiNeural    女声，活泼
    #   zh-CN-YunxiNeural     男声，阳光
    #   zh-CN-YunyangNeural   男声，播音
    'voice': 'zh-CN-XiaoxiaoNeural',

    # 音量。1.0 是 edge-tts 的原始响度，0.45 大致相当于正常说话
    'volume': 0.45,

    # 额外的高频削减（dB）。女声的 s/c/sh 能量集中在 6~10 kHz，戴耳机时偏刺
    'treble': -3,

    # 低通截止频率（Hz）。砍掉这一频段以上的"嘶"声
    'lowpass': 9500,

    # 单次朗读的字数上限，防止一整段东西念几分钟
    'max_chars': 600,

    # 思考提取器输出给语音的字数上限（关键句总长）
    'think_max_chars': 110,

    # 心跳超过这么多秒算掉线
    'stale_seconds': 90,

    # 守护多久检查一次（秒）
    'guard_interval': 30,
}


def load_user_config():
    """合并 DEFAULTS 和 config.json（如果存在）。"""
    cfg = dict(DEFAULTS)
    try:
        if USER_CONFIG.exists():
            cfg.update(json.loads(USER_CONFIG.read_text(encoding='utf-8')))
    except Exception:
        pass
    return cfg


def audio_filter(cfg):
    """拼 ffmpeg 的 -af 参数。"""
    return 'volume=%s,treble=g=%s,lowpass=f=%s' % (
        cfg['volume'], cfg['treble'], cfg['lowpass'],
    )


def find_executable(name, candidates):
    """找一个可执行文件，找不到返回 None。

    开源版不能假设 ffmpeg 装在 某个固定路径 —— 先看 PATH，再看几个常见位置。
    """
    import shutil
    found = shutil.which(name)
    if found:
        return found
    for c in candidates:
        p = Path(c)
        if p.exists():
            return str(p)
    return None
