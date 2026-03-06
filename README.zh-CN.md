# Subtitle Pipeline（简体中文）

基于 `faster-whisper` + `FFmpeg` 的本地字幕流水线。

支持能力：
- 语音识别（默认中文）
- 翻译为英文
- 生成 `cn.srt` / `en.srt` / `bilingual.srt`
- 可选硬字幕烧录
- 支持简体中文别名：`zh-CN`、`zh-Hans`、`cn`、`chinese`

## 一键部署

### Windows
```bat
install.bat
```

### macOS / Linux
```bash
bash setup.sh
```

## 快速使用

```bash
python auto_subtitle.py input.mp4
python auto_subtitle.py input.mp4 --no-burn
python auto_subtitle.py input.mp4 --source-language zh-CN
python auto_subtitle.py input.mp4 --burn-only output/input.bilingual.srt
```

## 参数说明

```text
python auto_subtitle.py <video> [--model MODEL] [--source-language LANG] [--output OUTPUT] [--no-burn] [--burn-only SRT]
```

- `--model`：Whisper 模型（`tiny/base/small/medium/large-v3`）
- `--source-language`：输入语音语言（默认 `zh`）
- `--output`：输出目录（默认 `output`）
- `--no-burn`：只生成字幕，不烧录视频
- `--burn-only`：使用现有 SRT 直接烧录

## 输出文件

默认输出目录 `output/`：
- `input.cn.srt`
- `input.en.srt`
- `input.bilingual.srt`
- `input.hardsub.mp4`（开启烧录时）

## 相关文档

- 部署说明：[DEPLOY.md](DEPLOY.md)
- 英文说明：[README.md](README.md)
