# Deployment Guide

Chinese version: [DEPLOY.zh-CN.md](DEPLOY.zh-CN.md)

This document explains one-click deployment for local use.

## Windows

### Recommended
```bat
install.bat
```

`install.bat` calls:
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### Direct PowerShell
```powershell
.\setup.ps1
```

Optional:
```powershell
.\setup.ps1 -SkipFFmpegInstall
```

`setup.ps1` will automatically try project-level `mise` Python first (if `mise` is installed and `.mise.toml` exists), then fall back to `py` / `python`.

## macOS / Linux

```bash
bash setup.sh
```

Optional:
```bash
SKIP_FFMPEG_INSTALL=1 bash setup.sh
```

## What setup scripts do

1. Validate Python 3.10+
2. Create `.venv` if missing
3. Install dependencies from `requirements.txt`
4. Check FFmpeg, and try auto-install when possible
5. Print final run command

## Python version via mise (optional)

This repo includes a project-level `.mise.toml`.

If you use `mise`, run in project root before setup:
```bash
mise trust .mise.toml
mise install
```

## Run after deployment

Windows:
```bat
run.bat input.mp4
```

macOS / Linux:
```bash
bash run.sh input.mp4
```

## Troubleshooting

### Windows: ".venv\\Scripts\\python.exe is not recognized"

This usually means the virtual environment was not created successfully.

Common cause:
- `python` resolves to the Microsoft Store app execution alias (`...\\WindowsApps\\python.exe`) instead of a real Python runtime.

Fix:
1. Install Python 3.10+ from python.org (or ensure `py -3` works).
2. In Windows Settings, disable App execution aliases for `python.exe` / `python3.exe`.
3. Re-run:
   ```bat
   install.bat
   ```
