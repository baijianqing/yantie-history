[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "metaos\.tasks\.worker" -and
        $_.CommandLine -match "\bocr\b"
    }

if (-not $processes) {
    Write-Host "No MetaOS OCR worker process found."
    return
}

foreach ($process in $processes) {
    if ($PSCmdlet.ShouldProcess("PID $($process.ProcessId)", "Stop MetaOS OCR worker")) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped MetaOS OCR worker PID $($process.ProcessId)"
    }
}
