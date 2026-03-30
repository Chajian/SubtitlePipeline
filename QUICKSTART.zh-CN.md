# 快速上手

想立刻跑起来请看本页。

## 1) 安装

Windows：
```bat
install.bat
```

## 2) 处理新视频（ASR + 中文审阅 + 翻译 + 字幕）

网络受限地区推荐：
```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

如果希望 AI 先审阅中文转写再生成英文：
```bat
run.bat "input.mp4" --model tiny --ai-review on --ai-review-provider codex --no-burn
```

如果希望通过环境变量切换 provider，可创建本地文件（已在 gitignore）：
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

临时切换 provider：
```powershell
$env:AI_REVIEW_PROVIDER = 'openai'
$env:AI_REVIEW_MODEL = 'gpt-4.1-mini'
$env:OPENAI_API_KEY = 'your_key_here'
run.bat "input.mp4" --no-burn
```

如果还想复用 `cc-switch` 已存凭据：
```powershell
.\scripts\use_ai_review_profile.ps1 siliconflow
run.bat "input.mp4" --no-burn
```

如果中文是繁体，强制简体：
```bat
run.bat "input.mp4" --model tiny --source-language zh-CN --zh-script simplified --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

成功日志通常包含：
- `Subtitle Pipeline`
- `Step 1/N`
- `Completed`

## 3) 生成硬字幕视频

```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com
```

## 4) 合并软字幕与 ASR（带时间戳文本）

```bat
run.bat "input.mp4" --merge-mode ai --subtitle-track auto --output-format both --text-only
```

输出目录 `output/`：
- `*.cn.srt`
- `*.cn.reviewed.srt`（AI 中文审阅成功时）
- `*.en.srt`
- `*.bilingual.srt`（双语合并）
- `*.bilingual.reviewed.srt`（AI 审阅成功时）
- `*.merged.srt`（启用合并模式时）
- `*.merged.txt`（启用合并模式时）
- `*.hardsub.mp4`（未使用 `--no-burn` 时）

## 5) 快速排错

### 模型预检失败
网络无法访问模型源：
- 配置 `HTTPS_PROXY` / `HTTP_PROXY`
- 使用镜像端点
- 或改用本地模型：
```bat
run.bat "input.mp4" --model-source local --model-dir .\models --no-burn
```

### SRT 不存在
你使用了 `--burn-only`，但提供的 SRT 路径不存在。

### `python ...` 没反应
直接使用虚拟环境 Python：
```bat
.\.venv\Scripts\python.exe auto_subtitle.py ...
```

### `run.bat ...` 立即退出且无日志
`run.bat` 可能损坏或为空：
- 检查 `run.bat`
- 重新运行安装：
```bat
install.bat
```
- 或直接用 Python：
```bat
.\.venv\Scripts\python.exe auto_subtitle.py "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

### AI 审阅没有运行
`--ai-review auto` 会在不可用时安全跳过。检查：
- `codex --version`
- `codex login`
- 或强制开启 `--ai-review on`

API provider：
- 设置 `AI_REVIEW_PROVIDER`
- 设置 Key（`OPENAI_API_KEY` 或 `SILICONFLOW_API_KEY`）
- 设置 `AI_REVIEW_MODEL`

当前 AI 流程（启用时）：
- 先审阅中文转写
- 由审阅后的中文翻译英文
- 可选再审阅双语字幕
