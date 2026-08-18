# Lobster GitHub sync loop (background, starts at login via HKCU Run key)
# Syncs once immediately at startup (catch-up), then every day at 05:37 local.
# A global mutex guarantees only one instance runs.

$created = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\LobsterGitHubSync', [ref]$created)
if (-not $created) { exit }

$sync = 'D:\lobster\sync_to_github.ps1'

# catch-up sync at startup
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $sync | Out-Null

while ($true) {
    $now = Get-Date
    $target = $now.Date.AddHours(5).AddMinutes(37)
    if ($target -le $now) { $target = $target.AddDays(1) }
    Start-Sleep -Seconds ([int]($target - $now).TotalSeconds)
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $sync | Out-Null
}
