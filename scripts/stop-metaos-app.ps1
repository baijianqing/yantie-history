[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"

$processes = Get-CimInstance Win32_Process |
    Where-Object {
        $_.CommandLine -match "streamlit|metaos\.app\.run_streamlit" -and
        $_.CommandLine -match "metaos\\app\\streamlit_app\.py|metaos/app/streamlit_app\.py"
    }

if (-not $processes) {
    Write-Host "No MetaOS Streamlit app process found."
    return
}

foreach ($process in $processes) {
    if ($PSCmdlet.ShouldProcess("PID $($process.ProcessId)", "Stop MetaOS Streamlit app")) {
        Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped MetaOS app PID $($process.ProcessId)"
    }
}
