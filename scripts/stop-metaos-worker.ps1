[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$IncludeOcr
)

$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "metaos\.tasks\.worker" -and
        (
            $_.CommandLine -match "ingest|index|rag" -or
            ($IncludeOcr -and $_.CommandLine -match "\bocr\b")
        )
    }

if (-not $processes) {
    Write-Host "No MetaOS main worker process found."
    return
}

foreach ($process in $processes) {
    if ($PSCmdlet.ShouldProcess("PID $($process.ProcessId)", "Stop MetaOS worker")) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped MetaOS worker PID $($process.ProcessId)"
    }
}
