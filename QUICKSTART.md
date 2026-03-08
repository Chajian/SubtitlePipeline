# Quick Start

If you want to run it immediately, follow this page.

## 1) Setup

Windows:
```bat
install.bat
```

## 2) Process a new video (ASR + translation + subtitles)

Recommended in network-restricted regions:
```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

If Chinese subtitles appear in traditional characters, force simplified Chinese:
```bat
run.bat "input.mp4" --model tiny --source-language zh-CN --zh-script simplified --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

Expected success logs include:
- `自动双语字幕生成`
- `Step 1/4` to `Step 4/4`
- `全部完成`

## 3) Generate hard-sub video

```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com
```

Outputs in `output/`:
- `*.cn.srt`
- `*.en.srt`
- `*.bilingual.srt` (subtitle mapping/alignment result)
- `*.hardsub.mp4` (without `--no-burn`)

## 4) Quick troubleshooting

### Model source preflight failed
Your network cannot reach model source.
- Configure `HTTPS_PROXY` / `HTTP_PROXY`
- Use mirror endpoint
- Or use local model:
```bat
run.bat "input.mp4" --model-source local --model-dir .\models --no-burn
```

### SRT file not found
You used `--burn-only`, but the SRT path does not exist.

### `python ...` does nothing
Use project venv python directly:
```bat
.\.venv\Scripts\python.exe auto_subtitle.py ...
```

### `run.bat ...` returns immediately with no logs
`run.bat` may be damaged or empty.
- Check that `run.bat` is not empty.
- Re-run setup:
```bat
install.bat
```
- Or bypass helper script and run directly:
```bat
.\.venv\Scripts\python.exe auto_subtitle.py "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```
