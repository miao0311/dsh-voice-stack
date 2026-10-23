r"""思考提取器 —— 读 DSH 的会话记录，把 agent 的 reasoning 念出来。

原理：DSH 把每一轮完整过程写进 `~/.dsh/sessions/**/session.v4.jsonl.zstd`，
解压后是 JSONL，其中 `assistant/message` 的 `data.message.content` 是数组：

    [{"type": "reasoning", "text": "思考原文…"},
     {"type": "text",      "text": "回复正文"},
     {"type": "tool-call", ...}]

不需要任何 API，读文件就够了。

两个关键细节：
  * 一个 turn 会写多条 `assistant/message`：先是思考步，然后每个工具调用一条，
    而工具调用那几条**没有 reasoning**。所以要找「最后一条带 reasoning 的」，
    否则永远读到空。
  * reasoning 里的 markdown（反引号、星号、列表符号、引号）念出来是噪音，
    必须先剥掉。

为什么只念关键句：
  reasoning 常有几千字，逐字念要几分钟。用户要的是"知道它在想什么"，
  不是"听它念完整草稿"。
"""
import json
import os
import re
import time
from pathlib import Path

try:
    import zstandard as zstd
except ImportError:
    raise SystemExit('缺少依赖：pip install zstandard')

from config import (
    SAY, THINK_LOG, THINK_BEAT, STATE_FILE,
    load_user_config, HOME,
)

POLL_SECONDS = 2.5
MIN_REASONING_CHARS = 40
MIN_OUTPUT_CHARS = 45

# 带这些词的句子更可能是结论，而不是过程描述
KEYWORDS = (
    '发现', '问题', '原因', '关键', '但是', '所以', '其实', '不对',
    '应该', '说明', '意味着', '结论', '注意', '陷阱', '根因',
    '因为', '反而', '而是', '必须', '不能', '原来', '确认',
)


def log(msg):
    try:
        with open(THINK_LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('[%H:%M:%S] ') + msg + '\n')
    except Exception:
        pass


def sessions_dir():
    """DSH 的会话目录。可用环境变量 DSH_HOME 覆盖。"""
    home = Path(os.environ.get('DSH_HOME', Path.home() / '.dsh'))
    return home / 'sessions'


def latest_session():
    root = sessions_dir()
    try:
        files = [p for p in root.rglob('*.zstd') if p.is_file()]
    except Exception:
        return None
    return max(files, key=lambda p: p.stat().st_mtime) if files else None


def read_reasoning(path):
    """最后一条带 reasoning 的 assistant 消息。"""
    try:
        with open(path, 'rb') as fh:
            raw = zstd.ZstdDecompressor().stream_reader(fh).read()
    except Exception as exc:
        log('解压失败: %s' % exc)
        return None

    found = None
    for ln in raw.decode('utf-8', 'replace').splitlines():
        if '"assistant/message"' not in ln:      # 便宜的前置过滤
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            continue
        if obj.get('type') != 'assistant/message':
            continue
        msg = (obj.get('data') or {}).get('message') or {}
        parts = [
            p.get('text') for p in (msg.get('content') or [])
            if isinstance(p, dict) and p.get('type') == 'reasoning'
            and isinstance(p.get('text'), str) and p.get('text').strip()
        ]
        if parts:
            found = {'id': msg.get('id') or '', 'reasoning': '\n'.join(parts).strip()}
    return found


def split_sentences(text):
    """按句切分，剥掉所有只对屏幕有意义的标记。"""
    out = []
    for p in re.split(r'(?<=[。！？!?；;\n])', text):
        p = re.sub(r'```[\s\S]*?```', '', p)          # 代码块
        p = re.sub(r'`{1,3}[^`]*`{1,3}', '', p)       # 行内代码
        p = re.sub(r'^\s*\d+\s*[.、)]\s*', '', p)     # 列表序号
        p = re.sub(r'^\s*[-*•]\s*', '', p)            # 列表符号
        p = re.sub(r'[*#>\|]{1,}', '', p)             # 强调/标题/表格
        p = re.sub(r'["“”\'‘’「」『』]', '', p)       # 引号
        p = re.sub(r'\s+', ' ', p).strip()
        if len(p) >= 6 and re.search(r'[\u4e00-\u9fff]', p):
            out.append(p)
    return out


def pick_key(text, max_chars):
    """挑出承载结论的几句，保持原顺序。"""
    sentences = split_sentences(text)
    if not sentences:
        return ''

    picked = []
    for s in sentences:
        if any(k in s for k in KEYWORDS) and s not in picked:
            picked.append(s)
        if len(''.join(picked)) >= max_chars:
            break

    if len(''.join(picked)) < MIN_OUTPUT_CHARS:
        for s in [sentences[0], sentences[-1]]:
            if s not in picked:
                picked.append(s)
            if len(''.join(picked)) >= MIN_OUTPUT_CHARS:
                break

    order = {s: i for i, s in enumerate(sentences)}
    picked.sort(key=lambda s: order.get(s, 0))

    out = ''
    for s in picked:
        if len(out) + len(s) > max_chars:
            break
        out += s
    return out.strip()


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except Exception:
        return {}


def save_state(state):
    try:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    except Exception:
        pass


def main():
    cfg = load_user_config()
    max_chars = int(cfg.get('think_max_chars', 110))

    log('=== 思考提取器启动 ===')
    log('会话目录 %s' % sessions_dir())

    last_id = load_state().get('lastId', '')
    last_mtime = 0.0

    # 启动时只记录当前最新 id，不把旧思考倒出来重念
    initial = latest_session()
    if initial:
        info = read_reasoning(initial)
        if info and info.get('id'):
            last_id = info['id']
            save_state({'lastId': last_id})
            log('基线 id: %s' % last_id[:12])
        last_mtime = initial.stat().st_mtime

    while True:
        try:
            THINK_BEAT.touch()
            path = latest_session()
            if path:
                mtime = path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    info = read_reasoning(path)
                    if info and info.get('id') and info['id'] != last_id:
                        reasoning = info['reasoning']
                        last_id = info['id']
                        save_state({'lastId': last_id})
                        if len(reasoning) >= MIN_REASONING_CHARS:
                            spoken = pick_key(reasoning, max_chars)
                            if spoken:
                                SAY.write_text(spoken, encoding='utf-8')
                                log('念(%d字): %s' % (len(spoken), spoken[:60]))
        except Exception as exc:
            log('循环异常: %s' % exc)
        time.sleep(POLL_SECONDS)


if __name__ == '__main__':
    main()
