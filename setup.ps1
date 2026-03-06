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

function Invoke-Checked([string]$exe, [string[]]$commandArgs, [string]$action) {
    & $exe @commandArgs
    if ($LASTEXITCODE -ne 0) {
        $joinedArgs = ($commandArgs -join " ")
        throw "$action failed (exit code $LASTEXITCODE): $exe $joinedArgs"
    }
}

function Test-PythonLauncher([string]$exe, [string[]]$launcherArgs) {
    try {
        & $exe @($launcherArgs + @("-c", "import sys; print(sys.version_info[0])")) | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Try-Resolve-MisePython {
    $miseCmd = Get-Command mise -ErrorAction SilentlyContinue
    if (-not $miseCmd) {
        return $null
    }

    $miseExe = $miseCmd.Source

    try {
        $miseConfig = Join-Path $ProjectRoot ".mise.toml"
        if (Test-Path $miseConfig) {
            Write-Step "Detected mise project config (.mise.toml), syncing tools"
            Invoke-Checked -exe $miseExe -commandArgs @("trust", "-y", $miseConfig) -action "Trust mise project config"
            Invoke-Checked -exe $miseExe -commandArgs @("install", "-y") -action "Run mise install"
        }

        $misePython = & $miseExe "which" "python" 2>$null
        if ($LASTEXITCODE -ne 0) {
            return $null
        }

        $misePython = "$misePython".Trim()
        if ([string]::IsNullOrWhiteSpace($misePython)) {
            return $null
        }

        if (Test-PythonLauncher -exe $misePython -launcherArgs @()) {
            Write-Host "[ok] Using python from mise: $misePython"
            return @{ Exe = $misePython; Args = @() }
        }

        Write-Host "[warn] mise resolved python but it is not usable: $misePython"
    } catch {
        Write-Host "[warn] mise detected but failed: $($_.Exception.Message)"
    }

    return $null
}

function Resolve-Python {
    $misePython = Try-Resolve-MisePython
    if ($misePython) {
        return $misePython
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $exe = $pyLauncher.Source
        if (Test-PythonLauncher -exe $exe -launcherArgs @("-3")) {
            return @{ Exe = $exe; Args = @("-3") }
        }
        Write-Host "[warn] Found py launcher but it is not usable: $exe"
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        $exe = $pythonCmd.Source
        if (Test-PythonLauncher -exe $exe -launcherArgs @()) {
            return @{ Exe = $exe; Args = @() }
        }
        Write-Host "[warn] Found python command but it is not usable: $exe"
    }

    throw "No usable Python runtime found. If using mise, run 'mise install' in project root. Otherwise install Python 3.10+ and disable the Windows App Execution Alias for python if it points to WindowsApps."
}

function Invoke-Python($py, [string[]]$extraArgs, [string]$action = "Run Python command") {
    Invoke-Checked -exe $py.Exe -commandArgs @($py.Args + $extraArgs) -action $action
}

function Assert-PythonVersion($py) {
    Invoke-Python -py $py -extraArgs @("-c", "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print(f'Python {sys.version.split()[0]}')") -action "Validate Python version"
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

$venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Step "Using existing virtual environment (.venv)"
} else {
    Write-Step "Resolving Python"
    $py = Resolve-Python
    Assert-PythonVersion -py $py

    Write-Step "Creating virtual environment (.venv)"
    Invoke-Python -py $py -extraArgs @("-m", "venv", ".venv") -action "Create virtual environment (.venv)"
}

if (-not (Test-Path $venvPy)) {
    throw "Virtual environment was not created correctly. Missing: $venvPy"
}

Invoke-Checked -exe $venvPy -commandArgs @("-c", "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'; print(f'Python {sys.version.split()[0]}')") -action "Validate virtual environment Python version"

Write-Step "Installing dependencies"
Invoke-Checked -exe $venvPy -commandArgs @("-m", "pip", "install", "--upgrade", "pip") -action "Upgrade pip"
Invoke-Checked -exe $venvPy -commandArgs @("-m", "pip", "install", "-r", "requirements.txt") -action "Install dependencies"

Write-Step "Checking ffmpeg"
Ensure-FFmpeg

Write-Step "Done"
Write-Host "Run command:"
Write-Host ".\.venv\Scripts\python.exe .\auto_subtitle.py input.mp4"
Write-Host ""
Write-Host "Or use helper:"
Write-Host ".\run.bat input.mp4"
