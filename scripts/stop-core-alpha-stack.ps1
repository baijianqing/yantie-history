[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$SkipWorkers,
    [switch]$SkipOcrWorker
)

$ErrorActionPreference = "Stop"

function Stop-MatchingProcess {
    param(
        [string]$Name,
        [scriptblock]$Predicate
    )

    $processes = Get-CimInstance Win32_Process |
        Where-Object {
            $_.CommandLine -and (& $Predicate $_.CommandLine)
        }

    if (-not $processes) {
        Write-Host "No $Name process found."
        return
    }

    foreach ($process in $processes) {
        if ($PSCmdlet.ShouldProcess("PID $($process.ProcessId)", "Stop $Name")) {
            Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped $Name PID $($process.ProcessId)"
        }
    }
}

Write-Host "Stopping MetaOS Core Alpha stack"
Write-Host "This script does not stop Redis or Ollama."

Stop-MatchingProcess `
    -Name "Core Alpha API" `
    -Predicate {
        param($CommandLine)
        $CommandLine -match "uvicorn" -and
            $CommandLine -match "metaos\.app\.core_alpha_api:create_app"
    }

Stop-MatchingProcess `
    -Name "Core Alpha workbench" `
    -Predicate {
        param($CommandLine)
        ($CommandLine -match "streamlit" -or $CommandLine -match "metaos\.app\.run_streamlit") -and
            ($CommandLine -match "metaos\\app\\core_alpha_workbench\.py" -or
                $CommandLine -match "metaos/app/core_alpha_workbench\.py")
    }

if (-not $SkipWorkers) {
    Stop-MatchingProcess `
        -Name "MetaOS main worker" `
        -Predicate {
            param($CommandLine)
            $CommandLine -match "metaos\.tasks\.worker" -and
                ($CommandLine -match "\bingest\b" -or
                    $CommandLine -match "\bindex\b" -or
                    $CommandLine -match "\brag\b")
        }
} else {
    Write-Host "Skipping main worker stop."
}

if (-not $SkipOcrWorker) {
    Stop-MatchingProcess `
        -Name "MetaOS OCR worker" `
        -Predicate {
            param($CommandLine)
            $CommandLine -match "metaos\.tasks\.worker" -and
                $CommandLine -match "\bocr\b"
        }
} else {
    Write-Host "Skipping OCR worker stop."
}
