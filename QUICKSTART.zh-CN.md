# 快速使用指南（简体中文）

如果你只想“马上跑起来”，按这页操作即可。

## 1) 一键准备环境

Windows：
```bat
install.bat
```

## 2) 直接处理新视频（识别 + 翻译 + 生成字幕）

推荐（网络受限场景）：
```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

如果中文字幕出现繁体，可强制输出简体：
```bat
run.bat "input.mp4" --model tiny --source-language zh-CN --zh-script simplified --model-source auto --mirror-endpoint https://hf-mirror.com --no-burn
```

成功时，终端通常会看到这些关键日志：
- `自动双语字幕生成`
- `Step 1/4` 到 `Step 4/4`
- `全部完成`

## 3) 需要硬字幕视频时

```bat
run.bat "input.mp4" --model tiny --model-source auto --mirror-endpoint https://hf-mirror.com
```

会在 `output/` 生成：
- `*.cn.srt`
- `*.en.srt`
- `*.bilingual.srt`（字幕映射/对齐结果）
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
