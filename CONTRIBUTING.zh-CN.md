# 贡献指南

英文版：[CONTRIBUTING.md](CONTRIBUTING.md)

本文件是人类贡献者与 AI 代码代理（Codex、Claude 等）的统一协作规则。
默认用于日常开发与 "vibe coding" 场景。

如果 PR 中维护者给出的明确意见与本文件冲突，以维护者意见为准。

## 1. 前 5 分钟检查清单

1. 开始修改前先阅读 [README.zh-CN.md](README.zh-CN.md) 与本文件。
2. 从 `main` 创建聚焦分支：
   - `feat/<short-topic>`
   - `fix/<short-topic>`
   - `docs/<short-topic>`
3. 初始化环境：

Windows：
```bat
install.bat
```

macOS / Linux：
```bash
bash setup.sh
```

4. 先确认 CLI 可运行：
```bash
python auto_subtitle.py --help
```

## 2. 变更范围规则

1. 每个 PR 只解决一个明确目标。
2. 不要把功能修改和无关重构混在同一个 PR。
3. CLI 行为、默认值、输出变化时必须同步更新文档。
4. 除非确有必要，脚本应保持跨平台可用。

## 3. 必做本地校验

提交 PR 前必须执行。

Linux/macOS：
```bash
python -m py_compile auto_subtitle.py config.py subtitle/*.py
```

Windows PowerShell：
```powershell
Get-ChildItem subtitle -Filter *.py | ForEach-Object { py -3 -m py_compile $_.FullName }
py -3 -m py_compile auto_subtitle.py
py -3 -m py_compile config.py
```

如果修改会影响运行行为，请额外执行至少一条真实 CLI 命令，并在 PR 描述中写明。

## 4. 提交信息规范

推荐使用 Conventional Commits：

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`
- `chore: ...`

规则：
1. 一个提交对应一个完整意图。
2. 提交信息写清“为什么改”，不只写“改了哪些文件”。

## 5. Pull Request 必填项

PR 描述至少包含：

1. 改了什么。
2. 为什么改。
3. 如何验证（命令 + 结果摘要）。
4. 风险与兼容性说明。
5. 后续待办（如有）。

## 6. AI 贡献协议（Codex/Claude）

AI 贡献者必须额外遵守：

1. 先读取当前仓库上下文，不基于过期假设修改代码。
2. 只修改完成当前任务所需文件。
3. 禁止伪造占位逻辑、伪造测试结果、猜测性实现。
4. 禁止提交密钥、绝对本机路径、机器私有凭据。
5. 未明确要求前，保持向后兼容。
6. 若无法执行校验，必须明确写出未执行项和原因。
7. 涉及高风险操作（大规模删除/重命名、历史重写）前先获维护者确认。
8. 优先提交小而可审阅的变更，而不是大范围重写。

## 7. 完成定义（Definition of Done）

满足以下条件才算完成：

1. 已执行本地校验（或清晰说明为何无法执行）。
2. 行为变化对应文档已更新。
3. PR 描述可被其他贡献者复现。
4. 没有夹带无关文件改动。

## 8. 相关策略

- 行为准则：[CODE_OF_CONDUCT.zh-CN.md](CODE_OF_CONDUCT.zh-CN.md)
- 安全策略：[SECURITY.zh-CN.md](SECURITY.zh-CN.md)
- 发布流程：[RELEASE.zh-CN.md](RELEASE.zh-CN.md)
