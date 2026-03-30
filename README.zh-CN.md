# Subtitle Pipeline 字幕流水线

English README: `README.md`  
快速上手: `QUICKSTART.zh-CN.md`

基于 `faster-whisper` 与 `FFmpeg` 的独立字幕流水线。

支持功能：
- 中文语音识别
- AI 审阅中文转写文本
- 英文翻译
- 中文 SRT / 英文 SRT / 双语 SRT 生成
- 软字幕轨抽取与 ASR/SRT 文本融合（生成带时间戳文本）
- 可选 AI 复审与双语字幕复审（`codex` / OpenAI Official / SiliconFlow）
- 可选硬字幕烧录
- 简体中文语言别名（`zh-CN`, `zh-Hans`, `cn`, `chinese`）

## 1. 一键部署

### Windows
```bat
install.bat
```

### macOS / Linux
```bash
bash setup.sh
```

脚本会完成：
1. 创建 `.venv`
2. 安装 `requirements.txt` 依赖
3. 检查 FFmpeg
4. 输出可运行命令

Windows 下 `setup.ps1` 优先使用项目级 `mise` Python（若已安装并存在 `.mise.toml`），否则回退到 `py` / `python`。

更多细节见：`DEPLOY.zh-CN.md`。

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

### 方式 B：直接 Python 命令
```bash
python auto_subtitle.py input.mp4
python auto_subtitle.py input.mp4 --model medium --no-burn
python auto_subtitle.py input.mp4 --model-source auto --mirror-endpoint https://hf-mirror.com
python auto_subtitle.py input.mp4 --model-source local --model-dir ./models --no-burn
python auto_subtitle.py input.mp4 --source-language zh-CN
python auto_subtitle.py input.mp4 --source-language zh-CN --zh-script simplified
python auto_subtitle.py input.mp4 --ai-review on --ai-review-provider codex
python auto_subtitle.py input.mp4 --ai-review on --ai-review-provider openai --ai-review-model gpt-4.1-mini
python auto_subtitle.py input.mp4 --ai-review on --ai-review-provider siliconflow --ai-review-model Pro/MiniMaxAI/MiniMax-M2.5
python auto_subtitle.py input.mp4 --burn-only output/input.bilingual.srt
python auto_subtitle.py input.mp4 --merge-mode ai --subtitle-track auto --output-format both --text-only
```

## 3. CLI 用法

```text
python auto_subtitle.py <video> [--model MODEL] [--model-source MODE] [--model-dir DIR] [--mirror-endpoint URL] [--source-language LANG] [--zh-script SCRIPT] [--output OUTPUT] [--ai-review {auto,on,off}] [--ai-review-provider {codex,openai,siliconflow}] [--ai-review-model MODEL] [--ai-review-base-url URL] [--no-burn] [--text-only] [--subtitle-track TRACK] [--merge-mode {ai,prefer-srt,prefer-asr}] [--output-format {srt,txt,both}] [--burn-only SRT]
```

关键参数：
- `--model`：Whisper 模型大小（`tiny/base/small/medium/large-v3`）
- `--model-source`：模型来源策略（`auto/official/mirror/local`）
- `--model-dir`：本地模型路径或缓存目录
- `--mirror-endpoint`：镜像端点（例如 `https://hf-mirror.com`）
- `--source-language`：输入语音语言（默认 `zh`，支持 `zh-CN/zh-Hans/cn/chinese`）
- `--zh-script`：中文字幕字形（`simplified/traditional/raw`）
- `--output`：输出目录（默认 `output`）
- `--ai-review`：AI 审阅开关（`auto/on/off`）
- `--ai-review-provider`：AI 服务提供方（`codex/openai/siliconflow`）
- `--ai-review-model`：AI 模型（对 `openai/siliconflow` 必需）
- `--ai-review-base-url`：OpenAI 兼容 API 基地址
- `--no-burn`：仅生成 SRT，跳过硬字幕烧录
- `--text-only`：仅生成文本输出（等价于跳过烧录）
- `--subtitle-track`：软字幕轨（`auto` / 索引 / 语言标签）
- `--merge-mode`：合并 ASR 与软字幕（`ai` / `prefer-srt` / `prefer-asr`）
- `--output-format`：融合文本输出格式（`srt` / `txt` / `both`）
- `--burn-only`：跳过识别/翻译，直接烧录指定 SRT

环境变量覆盖：
- `AI_REVIEW_MODE`
- `AI_REVIEW_PROVIDER`
- `AI_REVIEW_MODEL`
- `AI_REVIEW_BASE_URL`
- `OPENAI_API_KEY`
- `SILICONFLOW_API_KEY`
- `AI_REVIEW_API_KEY`

本地 env 文件会自动加载：
- `.env.ai-review.local`
- `.env.ai-review.<provider>.local`

Shell 环境变量优先级最高。

## 4. 输出

输入 `input.mp4`（默认输出目录 `output/`）：
- `output/input.cn.srt`
- `output/input.cn.reviewed.srt`（AI 中文审阅成功时）
- `output/input.en.srt`
- `output/input.bilingual.srt`
- `output/input.bilingual.reviewed.srt`（AI 审阅成功时）
- `output/input.merged.srt`（启用合并模式时）
- `output/input.merged.txt`（启用合并模式时）
- `output/input.*.mp4`（启用烧录时）

## 5. 项目结构

```text
subtitle-pipeline/
  auto_subtitle.py         # CLI 入口
  config.py                # 模型/设备/字幕样式配置
  requirements.txt
  install.bat              # Windows 一键安装
  setup.ps1                # Windows PowerShell 一键安装
  setup.sh                 # macOS/Linux 一键安装
  run.bat                  # Windows 运行脚本
  run.sh                   # macOS/Linux 运行脚本
  subtitle/
    transcribe.py          # ASR + Whisper 翻译
    srt.py                 # SRT 写入与双语合并
    ai_review.py           # AI 审阅与文本翻译/合并
    embed.py               # FFmpeg 烧录与封装
    softsub.py             # 软字幕轨抽取
    merge.py               # ASR/SRT 对齐与合并
```

## 6. 参考图

可编辑的 draw.io 源文件：
- `docs/diagrams/pipeline-flow.drawio`
- `docs/diagrams/system-architecture.drawio`
- `docs/diagrams/README.md`

## 7. 运行环境

- Python 3.10+
- 可选：`mise`
- `PATH` 中可用的 FFmpeg
- 可选 NVIDIA GPU

使用 `mise`：
```bash
mise trust .mise.toml
mise install
```

## 8. 常见问题

### 找不到 FFmpeg
安装 FFmpeg 并确保 `ffmpeg` 在 `PATH` 中。

### CPU 很慢
使用更小模型（`--model small`），或使用 GPU。

### 首次运行慢
`faster-whisper` 首次会下载模型。

### AI 审阅被跳过或部分降级
`--ai-review auto` 会在不可用时安全跳过。

Provider 配置：
- `codex`：确保 `codex --version` 与 `codex login` 正常
- `openai`：设置 `OPENAI_API_KEY` 并传 `--ai-review-model`
- `siliconflow`：设置 `SILICONFLOW_API_KEY` 并传 `--ai-review-model`

## 9. 许可证

本项目采用 MIT License，详见 `LICENSE`。

## 10. 开源协作

- `CONTRIBUTING.zh-CN.md`
- `CODE_OF_CONDUCT.zh-CN.md`
- `SECURITY.zh-CN.md`
- `RELEASE.zh-CN.md`
