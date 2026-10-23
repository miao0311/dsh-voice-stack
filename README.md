# dsh-voice-stack

**让 DSH 里的 agent 不光打字，还有声音。**

它读 agent 的 thinking（推理过程），挑出关键句，用微软 Edge 的原生 TTS 念出来 —— **不用进入语音模式，不用点任何按钮，也不用装浏览器扩展**。

```
agent 思考 → 会话记录 → 提取关键句 → edge-tts 合成 → 你的扬声器
```

---

## 它解决什么问题

DSH 的 `dsh-voice-mode` 是**全双工语音对话**：你要说话、它才回答、回答才被念出来。那是"对讲机"模式。

但很多时候你并不想对着电脑说话 —— 你只是想让它在后台干活，**顺便能听见它在想什么**。

这时候 voice-mode 用不了：它要求你先点麦克风进入语音模式，退出就静音。

这个项目补的就是这一块：**单向的、被动的、一直在的旁白**。

| | voice-mode | 本项目 |
|---|---|---|
| 触发方式 | 你点麦克风 | 无需操作 |
| 方向 | 双向（你说 → 它答 → 它念） | 单向（它想 → 你听） |
| 内容 | 最终回复 | **思考过程的关键句** |
| 依赖 | 麦克风 + 语音模型 | 只要网络（edge-tts） |

---

## 能干什么

**1. 念出 agent 的思考**
不是念回复，是念它**想的过程**。挑出带因果、转折、判断的句子（"因为""但是""发现问题""原来如此"），压到 110 字以内。

**2. 自动，不用管**
它监听 DSH 的会话文件（`~/.dsh/sessions/**/*.zstd`），一有新思考就念。整个链路没有一个按钮。

**3. 音量音色可调**
默认微软"晓晓"（温暖女声），音量 45%、削 3dB 高频——默认值是按"不刺耳"调的。

**4. 死了会自己起来**
三个组件互相看着（心跳检测），任何一个挂了 90 秒内被拉起。

**5. 状态可见**
侧栏底部有个 🎙，三个点分别代表朗读 / 提取 / 守护，绿=在跑、红=掉线。点开能看各自的心跳年龄。

---

## 怎么用

### 前置条件

- Windows 10/11（用了 `winsound` 和 `CREATE_NO_WINDOW`，**目前只支持 Windows**）
- Python 3.10+
- DSH 桌面端
- 能联网（edge-tts 走微软的在线合成服务，不花钱、不需要 API key）

### 安装

```powershell
# 1. 装 Python 依赖
pip install edge-tts zstandard

# 2. 把 core/ 里的脚本复制到语音目录
$home = "$env:USERPROFILE\.dsh\voice-stack"
New-Item -ItemType Directory -Force -Path $home | Out-Null
Copy-Item core\*.py $home

# 3. 装 DSH 状态插件（可选，但推荐）
dsh plugin --profile desktop add file:./plugin
```

（也可以直接跑 `install.ps1`，它会做上面这些）

### 启动

```powershell
# 三个一起起来（守护会负责另外两个）
pythonw "$env:USERPROFILE\.dsh\voice-stack\guard.py"
```

**建议注册成登录自启**，否则每次都要手动开：

```powershell
$home = "$env:USERPROFILE\.dsh\voice-stack"
$action = New-ScheduledTaskAction -Execute "pythonw.exe" -Argument "$home\guard.py" -WorkingDirectory $home
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "dsh-voice-stack" -Action $action -Trigger $trigger
```

### 验证

```powershell
# 写一句，应该马上听到
'你好，这是一条测试' | Out-File "$env:USERPROFILE\.dsh\voice-stack\say.txt" -Encoding UTF8
```

或者直接看日志：

```powershell
Get-Content "$env:USERPROFILE\.dsh\voice-stack\watch.log" -Tail 5
```

---

## 配置

改 `~/.dsh/voice-stack/config.json`（不存在就自己建）：

```json
{
  "voice": "zh-CN-XiaoxiaoNeural",
  "volume": 0.45,
  "treble": -3,
  "lowpass": 9500,
  "think_max_chars": 110
}
```

**音色**（`edge-tts --list-voices` 看全部）：

| 值 | 说明 |
|---|---|
| `zh-CN-XiaoxiaoNeural` | 女声，温暖（默认） |
| `zh-CN-XiaoyiNeural` | 女声，活泼 |
| `zh-CN-YunxiNeural` | 男声，阳光 |
| `zh-CN-YunyangNeural` | 男声，播音 |
| `zh-CN-liaoning-XiaobeiNeural` | 东北话 |
| `zh-CN-shaanxi-XiaoniNeural` | 陕西话 |

**觉得刺耳**：`volume` 降到 0.35，`treble` 降到 -5。
**觉得太闷**：`treble` 调到 0，`lowpass` 调到 12000。
**想听长一点**：`think_max_chars` 提到 200（约 25 秒）。

---

## 架构

```
                    ┌──────────────┐
   会话记录  ──────► │ watch_think  │ ──┐
  (.zstd 解压)      │  挑关键句     │   │
                    └──────────────┘   │  写
                                       ▼
                                  ┌────────┐
                                  │ say.txt│
                                  └────────┘
                                       │  监听
                                       ▼
                    ┌──────────────┐
                    │    watch     │ ──► edge-tts ──► ffmpeg ──► 扬声器
                    │  合成 + 播放  │
                    └──────────────┘
                           ▲
                           │ 每 30 秒检查心跳
                    ┌──────────────┐
                    │    guard     │
                    └──────────────┘
```

三个组件都是独立进程，通过**文件**通信（`say.txt` 和 `*.beat`），互不依赖。

---

## 为什么这么设计

**为什么用文件当信号，不用 IPC**
DSH 的客户端插件拿不到消息正文（`assistant-actions` 只给 `messageId`）。猜 DOM 结构太脆。文件是最简单可靠的跨进程通道——agent 能写、脚本能读、出问题能手动改。

**为什么用 `pythonw`**
`watch.ps1` 那种 PowerShell 方案，即使加 `-WindowStyle Hidden`，控制台窗口也会先闪一下；如果交给计划任务常驻，会缩到任务栏留个残影。`pythonw.exe` 是 GUI 子系统的解释器，**从进程创建那一刻就没有控制台**。

**为什么给子进程加 `CREATE_NO_WINDOW`**
主进程没窗口没用——`edge-tts` 和 `ffmpeg` 都是控制台程序，每次调用都会新开一个黑框。必须逐个加 `0x08000000`。

**为什么用心跳，不查进程**
`watch.py` 和 `watch_think.py` 都是 `pythonw`，按命令行匹配容易认错。每个组件每轮 touch 一下自己的 `.beat`，一次 `stat` 就知道死活。

**为什么只念关键句**
reasoning 常有几千字，逐字念要好几分钟。挑带"因为/但是/原来/结论"的句子，压到 110 字——够听出它在纠结什么，不至于变成折磨。

---

## 已知限制

- **仅 Windows**。`winsound` 和 `CREATE_NO_WINDOW` 都是 Windows 特有的，macOS / Linux 需要另写播放层。
- **需要联网**。edge-tts 走微软的在线服务，断网就没声音（但不会崩）。
- **只读 DSH 的会话格式**。`session.v4.jsonl.zstd` 的结构哪天变了，`watch_think.py` 要跟着改。
- **中文优先**。挑句规则和音色都是按中文调的。
- **不是实时对话**。从思考完成到出声有 2-3 秒延迟（合成 + 转码），不适合你来我往的聊天。

---

## 许可证

MIT
