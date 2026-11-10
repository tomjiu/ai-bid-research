# 离线全链冒烟（Windows PowerShell，#601 R67）
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\smoke-windows.ps1
#   任意一步失败立即非零退出（$ErrorActionPreference = 'Stop'）。
#
# 覆盖面与 smoke-linux.sh 严格对齐：--version → collect → db --status
# → data-quality（R82）→ analyze → db export → pipeline → db --runs
# （R83）→ 产物断言。全程离线。

$ErrorActionPreference = 'Stop'

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = if ($args.Count -ge 1) { $args[0] } else { 'python' }

$TmpDir = Join-Path ([System.IO.Path]::GetTempPath()) (
    'bid-smoke-' + [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
)
New-Item -ItemType Directory -Path $TmpDir | Out-Null

try {
    $Db = Join-Path $TmpDir 'smoke.db'
    $Reports = Join-Path $TmpDir 'reports'
    $Snap = Join-Path $TmpDir 'snap.json'
    $Dq = Join-Path $TmpDir 'dq.json'
    # PathLike 参数统一正斜杠（argparse Path 两平台均可）
    $Src = 'tests/fixtures/announcements/a-别名与重复.json'

    Write-Host ''
    Write-Host '== 版本面 =='
    & $Python main.py --version

    Write-Host ''
    Write-Host '== collect：fixture 装载 → 去重 → 入库 =='
    & $Python main.py collect --source $Src --db ($Db -replace '\\', '/')

    Write-Host ''
    Write-Host '== db --status：库结构 =='
    & $Python main.py db --db ($Db -replace '\\', '/') --status

    Write-Host ''
    Write-Host '== data-quality：质量巡检（R82，含语义健康分） =='
    & $Python main.py data-quality --db ($Db -replace '\\', '/') --json > $Dq

    Write-Host ''
    Write-Host '== analyze：离线数据报告 =='
    & $Python main.py analyze --db ($Db -replace '\\', '/') --output-dir ($Reports -replace '\\', '/')

    Write-Host ''
    Write-Host '== db export：研究快照 =='
    & $Python main.py db --db ($Db -replace '\\', '/') --export json --out ($Snap -replace '\\', '/')

    Write-Host ''
    Write-Host '== pipeline（无源分析链）→ db --runs：运行台账（R83） =='
    & $Python main.py pipeline --db ($Db -replace '\\', '/') --output-dir ($Reports -replace '\\', '/')
    & $Python main.py db --db ($Db -replace '\\', '/') --runs 3

    Write-Host ''
    Write-Host '== 产物断言 =='
    & $Python -c @"
import json, sys
from pathlib import Path
db_path = Path(r'$Db')
snap_path = Path(r'$Snap')
reports_dir = Path(r'$Reports')
dq_path = Path(r'$Dq')
assert db_path.exists() and db_path.stat().st_size > 0, '数据库未落盘'
snap = json.loads(snap_path.read_text(encoding='utf-8'))
assert isinstance(snap, list) and snap, '快照为空'
assert snap[0].get('bid_id'), '快照缺 bid_id'
dq = json.loads(dq_path.read_text(encoding='utf-8'))
assert 0 <= dq['semantic_health']['health_score'] <= 100, '健康分越界'
reports = sorted(reports_dir.glob('*.md'))
assert reports, '报告未生成'
body = reports[-1].read_text(encoding='utf-8')
assert '# 领域数据分析报告' in body, '报告标题缺失'
assert '## 目录' in body, '目录缺失（R63）'
assert '## 十六、近重复公告检测' in body, '近重复节缺失（R80）'
assert '## 十七、语义质量审计' in body, '语义质量节缺失（R82）'
assert '\r' not in body, '行尾非 LF（R45 契约违背）'
print(f'断言通过：快照 {len(snap)} 条，报告 {reports[-1].name}')
"@

    Write-Host ''
    Write-Host 'SMOKE OK（Windows 离线全链）'
}
finally {
    if (Test-Path $TmpDir) {
        Remove-Item -Recurse -Force $TmpDir
    }
}
