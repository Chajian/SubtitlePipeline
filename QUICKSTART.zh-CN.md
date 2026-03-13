# 快速使用指南（简体中文）

如果你只想“马上跑起来”，按这页操作即可。

## 1) 一键准备环境

Windows：
```bat
install.bat
```

## 2) 直接处理新视频（识别 + 中文字幕复核 + 翻译 + 生成字幕）

推荐（网络受限场景）：
```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

如果你希望先用 AI 复核中文字幕，再生成英文字幕：
```bat
run.bat "input.mp4" --model tiny --ai-review on --ai-review-provider codex --no-burn
```

如果你更希望通过环境变量切换 provider，可以创建本地配置文件（已被 git 忽略）：
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

如果你想在当前 Shell 里临时切换 provider：
```powershell
$env:AI_REVIEW_PROVIDER = 'openai'
$env:AI_REVIEW_MODEL = 'gpt-4.1-mini'
$env:OPENAI_API_KEY = 'your_key_here'
run.bat "input.mp4" --no-burn
```

如果你仍然想复用 `cc-switch` 里已有的凭据：
```powershell
.\scripts\use_ai_review_profile.ps1 siliconflow
run.bat "input.mp4" --no-burn
```

如果中文字幕出现繁体，可强制输出简体：
```bat
run.bat "input.mp4" --model tiny --source-language zh-CN --zh-script simplified --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

成功时，终端通常会看到这些关键日志：
- `Subtitle Pipeline`
- `Step 1/N`
- `Completed`

## 3) 需要硬字幕视频时

```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com
```

会在 `output/` 生成：
- `*.cn.srt`
- `*.cn.reviewed.srt`（AI 中文复核成功时）
- `*.en.srt`
- `*.bilingual.srt`（字幕映射/对齐结果）
- `*.bilingual.reviewed.srt`（AI 复核成功时）
- `*.hardsub.mp4`（不加 `--no-burn` 时）

## 4) 常见问题（30 秒排障）

### A. 报错：模型源网络预检失败
说明：当前网络无法访问模型源。
- 配置 `HTTPS_PROXY` / `HTTP_PROXY`
- 使用镜像端点
- 或使用本地模型：
```bat
run.bat "input.mp4" --model-source local --model-dir .\models --no-burn
```

### B. 报错：SRT 文件不存在
你使用了 `--burn-only`，但指定的 `.srt` 路径不存在。

### C. `python ...` 没反应
优先使用项目 venv 的 Python：
```bat
.\.venv\Scripts\python.exe auto_subtitle.py ...
```

### D. `run.bat ...` 秒退、没有任何日志
`run.bat` 可能损坏或为空文件。
- 检查 `run.bat` 不是空文件
- 重新执行安装：
```bat
install.bat
```
- 或直接绕过 `run.bat`：
```bat
.\.venv\Scripts\python.exe auto_subtitle.py "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

### E. AI 复核没有执行
`--ai-review auto` 在所选 provider 不可用或复核失败时会自动跳过。
可先检查：
- `codex --version`
- `codex login`
- 或改用严格模式 `--ai-review on`

如果使用 API provider：
- 设置 `AI_REVIEW_PROVIDER`
- 设置对应密钥（`OPENAI_API_KEY` 或 `SILICONFLOW_API_KEY`）
- 设置 `AI_REVIEW_MODEL`

当前 AI 流程：
- 先复核中文字幕
- 再基于修正后的中文字幕生成英文
- 最后可选再复核双语字幕
