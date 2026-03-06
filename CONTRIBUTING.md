# Contributing

Chinese version: [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)

This guide defines the working contract for both human contributors and AI coding agents (Codex, Claude, etc.).
Use it as the default rulebook for normal and "vibe coding" sessions.

If maintainer feedback in a PR conflicts with this file, maintainer feedback wins.

## 1. First 5 Minutes Checklist

1. Read [README.md](README.md) and this file before editing.
2. Create a focused branch from `main`:
   - `feat/<short-topic>`
   - `fix/<short-topic>`
   - `docs/<short-topic>`
3. Set up environment:

Windows:
```bat
install.bat
```

macOS / Linux:
```bash
bash setup.sh
```

4. Verify CLI is runnable:
```bash
python auto_subtitle.py --help
```

## 2. Scope Rules

1. Keep each PR focused on one logical goal.
2. Do not mix feature work with unrelated refactors.
3. Update docs when CLI behavior, defaults, or outputs change.
4. Keep scripts cross-platform unless platform-specific behavior is required.

## 3. Required Local Validation

Run before opening a PR.

Linux/macOS:
```bash
python -m py_compile auto_subtitle.py config.py subtitle/*.py
```

Windows PowerShell:
```powershell
Get-ChildItem subtitle -Filter *.py | ForEach-Object { py -3 -m py_compile $_.FullName }
py -3 -m py_compile auto_subtitle.py
py -3 -m py_compile config.py
```

If your change affects runtime behavior, also run one real CLI command and include it in the PR description.

## 4. Commit Message Standard

Prefer Conventional Commits:

- `feat: ...`
- `fix: ...`
- `docs: ...`
- `refactor: ...`
- `chore: ...`

Rules:
1. One commit should represent one coherent change.
2. Write messages that explain intent, not only file names.

## 5. Pull Request Requirements

Each PR description should include:

1. What changed.
2. Why it changed.
3. How it was validated (commands + result summary).
4. Risk/compatibility notes.
5. Follow-up tasks (if any).

## 6. AI Contributor Protocol (Codex/Claude)

AI contributors must follow these additional rules:

1. Read current file context first; do not assume stale project structure.
2. Modify only files needed for the requested task.
3. Do not introduce fake placeholders, fake test output, or guessed behavior.
4. Do not commit secrets, local absolute paths, or machine-specific credentials.
5. Preserve backward compatibility unless explicitly asked to break it.
6. If validation cannot be run, state exactly what was not run and why.
7. For risky operations (mass delete/rename, history rewrite), require maintainer confirmation first.
8. Prefer small, reviewable diffs over broad rewrites.

## 7. Definition of Done

A contribution is "done" when:

1. Local validation has been executed (or clearly explained if not possible).
2. Docs are updated for behavior changes.
3. PR description is reproducible by another contributor.
4. No unrelated file churn is included.

## 8. Related Policies

- Code of Conduct: [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- Security policy: [SECURITY.md](SECURITY.md)
- Release process: [RELEASE.md](RELEASE.md)
