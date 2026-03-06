# 部署指南

英文版：[DEPLOY.md](DEPLOY.md)

本文档说明本地一键部署方式。

## Windows

### 推荐方式
```bat
install.bat
```

`install.bat` 实际调用：
```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### 直接 PowerShell
```powershell
.\setup.ps1
```

可选：
```powershell
.\setup.ps1 -SkipFFmpegInstall
```

## macOS / Linux

```bash
bash setup.sh
```

可选：
```bash
SKIP_FFMPEG_INSTALL=1 bash setup.sh
```

## 安装脚本会做什么

1. 校验 Python 3.10+
2. 若不存在则创建 `.venv`
3. 从 `requirements.txt` 安装依赖
4. 检查 FFmpeg，并在可行时尝试自动安装
5. 输出最终运行命令

## 部署后运行

Windows：
```bat
run.bat input.mp4
```

macOS / Linux：
```bash
bash run.sh input.mp4
```
