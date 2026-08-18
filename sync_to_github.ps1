# Lobster project auto-sync to GitHub
# Scheduled task: Lobster-GitHub-Sync (daily 04:17 / 16:37)
# Manual run: powershell -ExecutionPolicy Bypass -File D:\lobster\sync_to_github.ps1
# Flow: git add -A (.gitignore keeps secrets out) ->
#       commit (timestamped) if changes ->
#       push if there are unpushed commits (retries previous failures)

$git = 'C:\Program Files\Git\cmd\git.exe'
Set-Location 'D:\lobster'
# never hang waiting for credentials in unattended runs
$env:GIT_TERMINAL_PROMPT = '0'
Start-Transcript -Path 'D:\lobster\sync_github.log' -Append | Out-Null

& $git add -A
$pending = & $git status --porcelain
if ($pending) {
    $msg = 'auto-sync ' + (Get-Date -Format 'yyyy-MM-dd HH:mm')
    & $git commit -m $msg
    if ($LASTEXITCODE -ne 0) {
        Write-Output 'COMMIT FAILED'
    }
}

$unpushed = [int](& $git rev-list --count 'origin/main..HEAD')
if ($unpushed -gt 0) {
    & $git push origin main
    if ($LASTEXITCODE -eq 0) {
        Write-Output "SYNC OK: pushed $unpushed commit(s)"
    } else {
        Write-Output 'SYNC FAILED: push error (network/proxy off?), next run will retry'
    }
} elseif ($pending) {
    Write-Output 'COMMITTED but push check said nothing to push?'
} else {
    Write-Output 'NOTHING TO SYNC: no changes, everything pushed'
}

Stop-Transcript | Out-Null
