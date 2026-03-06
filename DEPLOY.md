# Deployment Guide

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

## Run after deployment

Windows:
```bat
run.bat input.mp4
```

macOS / Linux:
```bash
bash run.sh input.mp4
```
