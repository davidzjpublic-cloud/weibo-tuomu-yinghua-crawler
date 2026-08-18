# Lobster GitHub sync loop (background, starts at login via HKCU Run key)
# Runs one sync immediately, then repeats every 6 hours.
# A global mutex guarantees only one instance runs.

$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\LobsterGitHubSync', [ref]$created)
if (-not $created) { exit }

$sync = 'D:\lobster\sync_to_github.ps1'
while ($true) {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $sync | Out-Null
    Start-Sleep -Seconds 21600   # 6 hours
}
