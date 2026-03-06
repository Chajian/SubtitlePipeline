param(
    [switch]$SkipFFmpegInstall
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step([string]$msg) {
    Write-Host ""
    Write-Host "[setup] $msg" -ForegroundColor Cyan
}

function Resolve-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @{ Exe = "py"; Args = @("-3") }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @{ Exe = "python"; Args = @() }
    }
    throw "Python is not installed. Please install Python 3.10+."
}

function Invoke-Python($py, [string[]]$extraArgs) {
    & $py.Exe @($py.Args + $extraArgs)
}

function Assert-PythonVersion($py) {
    Invoke-Python $py @("-c", "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print(f'Python {sys.version.split()[0]}')")
}

function Ensure-FFmpeg {
    if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
        Write-Host "[ok] ffmpeg found: $(ffmpeg -version | Select-Object -First 1)"
        return
    }

    Write-Host "[warn] ffmpeg not found in PATH."
    if ($SkipFFmpegInstall) {
        Write-Host "[warn] SkipFFmpegInstall enabled. Install ffmpeg manually."
        return
    }

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "[setup] Installing ffmpeg via winget (Gyan.FFmpeg)..."
        winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "[warn] winget not available. Install ffmpeg manually: https://ffmpeg.org/download.html"
    }
}

Write-Step "Resolving Python"
$py = Resolve-Python
Assert-PythonVersion -py $py

$venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Step "Creating virtual environment (.venv)"
    Invoke-Python $py @("-m", "venv", ".venv")
}

Write-Step "Installing dependencies"
& $venvPy -m pip install --upgrade pip
& $venvPy -m pip install -r requirements.txt

Write-Step "Checking ffmpeg"
Ensure-FFmpeg

Write-Step "Done"
Write-Host "Run command:"
Write-Host ".\.venv\Scripts\python.exe .\auto_subtitle.py input.mp4"
Write-Host ""
Write-Host "Or use helper:"
Write-Host ".\run.bat input.mp4"
