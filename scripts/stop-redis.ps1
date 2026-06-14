[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.Name -match "^redis-server(\.exe)?$" -or
        $_.CommandLine -match "\bredis-server\b"
    }

if (-not $processes) {
    Write-Host "No Redis server process found."
    return
}

foreach ($process in $processes) {
    if ($PSCmdlet.ShouldProcess("PID $($process.ProcessId)", "Stop Redis server")) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped Redis PID $($process.ProcessId)"
    }
}
