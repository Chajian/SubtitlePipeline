param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("openai", "siliconflow")]
    [string]$Provider,

    [string]$PythonExe
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

function Resolve-PythonCommand {
    param([string]$ExplicitPython)

    if ($ExplicitPython) {
        return @{
            Exe = $ExplicitPython
            Args = @()
        }
    }

    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (Test-Path $venvPython) {
        return @{
            Exe = $venvPython
            Args = @()
        }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @{
            Exe = $pyLauncher.Source
            Args = @("-3")
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @{
            Exe = $pythonCmd.Source
            Args = @()
        }
    }

    throw "No usable Python runtime found. Run install.bat first or pass -PythonExe."
}

function Invoke-ExportScript {
    param(
        $ResolvedPython,
        [string]$SelectedProvider
    )

    $scriptPath = Join-Path $ScriptDir "export_ai_review_env.py"
    return & $ResolvedPython.Exe @($ResolvedPython.Args + @($scriptPath, "--provider", $SelectedProvider, "--format", "env"))
}

$resolvedPython = Resolve-PythonCommand -ExplicitPython $PythonExe
$outputLines = Invoke-ExportScript -ResolvedPython $resolvedPython -SelectedProvider $Provider

if ($LASTEXITCODE -ne 0) {
    throw "Failed to export AI review env for provider '$Provider'."
}

$applied = @()
foreach ($line in $outputLines) {
    if ($line -match '^\s*#' -or [string]::IsNullOrWhiteSpace($line)) {
        continue
    }

    $name, $value = $line -split "=", 2
    if (-not $name -or $null -eq $value) {
        continue
    }

    [Environment]::SetEnvironmentVariable($name, $value, "Process")
    $applied += $name
}

Write-Host ""
Write-Host "[ai-review] Loaded provider profile: $Provider" -ForegroundColor Cyan
Write-Host "[ai-review] Applied env vars: $($applied -join ', ')" -ForegroundColor Green
Write-Host "[ai-review] Example:" -ForegroundColor Yellow
Write-Host "run.bat ""input.mp4"" --no-burn"
