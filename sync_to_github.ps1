# Lobster project auto-sync to GitHub
# Scheduled task: Lobster-GitHub-Sync (daily 04:17 / 16:37)
# Manual run: powershell -ExecutionPolicy Bypass -File D:\lobster\sync_to_github.ps1
# Flow: git add -A (.gitignore keeps secrets out) ->
#       commit (timestamped message) if changes -> push origin main

$git = 'C:\Program Files\Git\cmd\git.exe'
Set-Location 'D:\lobster'
Start-Transcript -Path 'D:\lobster\sync_github.log' -Append | Out-Null

& $git add -A
$pending = & $git status --porcelain
if ($pending) {
    $msg = 'auto-sync ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')
    & $git commit -m $msg
    & $git push origin main
    if ($LASTEXITCODE -eq 0) {
        $count = ($pending | Measure-Object).Count
        Write-Output "SYNC OK: committed and pushed $count change(s)"
    } else {
        Write-Output 'SYNC FAILED: push error (network/proxy off?), next run will retry'
    }
} else {
    Write-Output 'NOTHING TO SYNC: no changes'
}

Stop-Transcript | Out-Null
