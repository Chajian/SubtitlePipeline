# Subtitle Pipeline（简体中文）

英文版：[README.md](README.md)

基于 `faster-whisper` 和 `FFmpeg` 的独立字幕流水线。

支持能力：
- 中文语音识别
- 英文翻译
- 生成中文字幕 / 英文字幕 / 双语字幕
- 可选硬字幕烧录
- 支持简体中文别名（`zh-CN`、`zh-Hans`、`cn`、`chinese`）

## 1. 一键部署

### Windows
```bat
install.bat
```

### macOS / Linux
```bash
bash setup.sh
```

两个脚本都会执行：
1. 创建 `.venv`
2. 从 `requirements.txt` 安装依赖
3. 检查 FFmpeg
4. 输出可直接运行的命令

更多细节见 [DEPLOY.zh-CN.md](DEPLOY.zh-CN.md)。

## 2. 快速开始

### 方式 A：辅助脚本

Windows：
```bat
run.bat input.mp4
run.bat input.mp4 --no-burn
```

macOS / Linux：
```bash
bash run.sh input.mp4
bash run.sh input.mp4 --no-burn
```

### 方式 B：直接调用 Python
```bash
python auto_subtitle.py input.mp4
python auto_subtitle.py input.mp4 --model medium --no-burn
python auto_subtitle.py input.mp4 --source-language zh-CN
python auto_subtitle.py input.mp4 --burn-only output/input.bilingual.srt
```

## 3. CLI 用法

```text
python auto_subtitle.py <video> [--model MODEL] [--source-language LANG] [--output OUTPUT] [--no-burn] [--burn-only SRT]
```

关键参数：
- `--model`：whisper 模型大小（`tiny/base/small/medium/large-v3`）
- `--source-language`：输入语音语言（默认 `zh`，支持 `zh-CN`、`zh-Hans`、`cn`、`chinese`）
- `--output`：输出目录（默认 `output`）
- `--no-burn`：只生成 SRT，不烧录视频
- `--burn-only`：跳过识别/翻译，直接使用现有 SRT 烧录

## 4. 输出文件

输入文件为 `input.mp4` 时（默认输出目录 `output/`）：
- `output/input.cn.srt`
- `output/input.en.srt`
- `output/input.bilingual.srt`
- `output/input.*.mp4`（启用烧录时）

## 5. 项目结构

```text
subtitle-pipeline/
  auto_subtitle.py         # CLI 入口
  config.py                # 模型/设备/字幕样式配置
  requirements.txt
  install.bat              # 一键安装（Windows）
  setup.ps1                # 一键安装（Windows PowerShell）
  setup.sh                 # 一键安装（macOS/Linux）
  run.bat                  # 运行辅助脚本（Windows）
  run.sh                   # 运行辅助脚本（macOS/Linux）
  subtitle/
    transcribe.py          # 语音识别 + 翻译
    srt.py                 # SRT 写入 + 双语合并
    embed.py               # FFmpeg 烧录与封装
```

## 6. 参考图

可编辑 draw.io 源文件：
- [docs/diagrams/pipeline-flow.drawio](docs/diagrams/pipeline-flow.drawio)
- [docs/diagrams/system-architecture.drawio](docs/diagrams/system-architecture.drawio)
- [docs/diagrams/README.md](docs/diagrams/README.md)（新增图示说明）

## 7. 环境要求

- Python 3.10+
- `PATH` 中可用的 FFmpeg
- 可选：NVIDIA GPU（加速推理）

## 8. 常见问题

### 找不到 FFmpeg
安装 FFmpeg，并确保 `ffmpeg` 命令在当前 Shell 的 `PATH` 中可用。

### CPU 运行太慢
改用较小模型（如 `--model small`），或使用 GPU 运行。

### 首次运行较慢
`faster-whisper` 首次运行会下载模型文件。

## 9. 许可证

本项目采用 MIT License，详见 [LICENSE](LICENSE)。

## 10. 开源协作

- 贡献指南：[CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)
- 行为准则：[CODE_OF_CONDUCT.zh-CN.md](CODE_OF_CONDUCT.zh-CN.md)
- 安全策略：[SECURITY.zh-CN.md](SECURITY.zh-CN.md)
- 发布流程：[RELEASE.zh-CN.md](RELEASE.zh-CN.md)
