# dsh-voice-stack 安装脚本
#
# 做四件事：
#   1. 把 core/*.py 复制到 ~\.dsh\voice-stack
#   2. 装 Python 依赖（edge-tts、zstandard）
#   3. 注册登录自启的计划任务
#   4. 立刻启动
#
# 需要 PowerShell 5.1+，并以当前用户身份运行（不需要管理员）。

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$voiceHome = Join-Path $env:USERPROFILE '.dsh\voice-stack'

Write-Host ''
Write-Host '=== dsh-voice-stack 安装 ===' -ForegroundColor Cyan
Write-Host "安装目录: $voiceHome"
Write-Host ''

# 1. 复制脚本
Write-Host '[1/4] 复制脚本...'
New-Item -ItemType Directory -Force -Path $voiceHome | Out-Null
Copy-Item (Join-Path $here 'core\*.py') $voiceHome -Force
Write-Host "      已复制 $((Get-ChildItem (Join-Path $voiceHome '*.py')).Count) 个文件"

# 2. 依赖
Write-Host '[2/4] 安装 Python 依赖...'
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) {
    Write-Host '      找不到 python，请先安装 Python 3.10+ 并加入 PATH' -ForegroundColor Red
    exit 1
}
& $python -m pip install --quiet --upgrade edge-tts zstandard
if ($LASTEXITCODE -ne 0) {
    Write-Host '      依赖安装失败，请手动执行: pip install edge-tts zstandard' -ForegroundColor Yellow
}
Write-Host "      完成（$python）"

# 3. 自启任务
Write-Host '[3/4] 注册登录自启...'
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + $voiceHome + '\guard.py"') -WorkingDirectory $voiceHome
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'dsh-voice-stack' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
Write-Host '      任务 dsh-voice-stack 已注册'

# 4. 启动
Write-Host '[4/4] 启动...'
Start-ScheduledTask -TaskName 'dsh-voice-stack'
Start-Sleep -Seconds 3

Write-Host ''
Write-Host '=== 安装完成 ===' -ForegroundColor Green
Write-Host ''
Write-Host '测试一下：'
Write-Host ('  ''你好，这是第一条测试'' | Out-File "' + $voiceHome + '\say.txt" -Encoding UTF8')
Write-Host ''
Write-Host '看日志：'
Write-Host ('  Get-Content "' + $voiceHome + '\watch.log" -Tail 5')
Write-Host ''
Write-Host '装 UI 状态面板（可选）：'
Write-Host ('  dsh plugin --profile desktop add file:' + (Join-Path $here 'plugin'))
Write-Host ''
