# Quick Start

If you want to run it immediately, follow this page.

## 1) Setup

Windows:
```bat
install.bat
```

## 2) Process a new video (ASR + Chinese review + translation + subtitles)

Recommended in network-restricted regions:
```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

If you want AI to review the Chinese transcript before English generation:
```bat
run.bat "input.mp4" --model tiny --ai-review on --ai-review-provider codex --no-burn
```

If you prefer switching provider via environment variables, create local files ignored by git:
```powershell
@'
AI_REVIEW_MODE=on
AI_REVIEW_PROVIDER=siliconflow
'@ | Set-Content .env.ai-review.local

@'
AI_REVIEW_MODEL=Pro/MiniMaxAI/MiniMax-M2.5
AI_REVIEW_BASE_URL=https://api.siliconflow.cn/v1
SILICONFLOW_API_KEY=your_key_here
'@ | Set-Content .env.ai-review.siliconflow.local

run.bat "input.mp4" --no-burn
```

To switch provider temporarily in the current shell:
```powershell
$env:AI_REVIEW_PROVIDER = 'openai'
$env:AI_REVIEW_MODEL = 'gpt-4.1-mini'
$env:OPENAI_API_KEY = 'your_key_here'
run.bat "input.mp4" --no-burn
```

If you still want to reuse credentials already stored in `cc-switch`:
```powershell
.\scripts\use_ai_review_profile.ps1 siliconflow
run.bat "input.mp4" --no-burn
```

If Chinese subtitles appear in traditional characters, force simplified Chinese:
```bat
run.bat "input.mp4" --model tiny --source-language zh-CN --zh-script simplified --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

Expected success logs include:
- `Subtitle Pipeline`
- `Step 1/N`
- `Completed`

## 3) Generate hard-sub video

```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com
```

Outputs in `output/`:
- `*.cn.srt`
- `*.cn.reviewed.srt` (when Chinese AI review succeeds)
- `*.en.srt`
- `*.bilingual.srt` (subtitle mapping/alignment result)
- `*.bilingual.reviewed.srt` (when AI review succeeds)
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

### AI review does not run
`--ai-review auto` skips safely when the selected provider is unavailable or review fails.
Check:
- `codex --version`
- `codex login`
- or force strict mode with `--ai-review on`

For API providers:
- set `AI_REVIEW_PROVIDER`
- set provider key (`OPENAI_API_KEY` or `SILICONFLOW_API_KEY`)
- set `AI_REVIEW_MODEL`

Current AI flow when enabled:
- review Chinese transcript first
- translate English from the reviewed Chinese text
- optionally review the merged bilingual subtitles again
