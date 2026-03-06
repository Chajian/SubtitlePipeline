# Contributing

Thanks for contributing.

## Development Setup

Windows:
```bat
install.bat
```

macOS / Linux:
```bash
bash setup.sh
```

## Local Checks

Run basic syntax checks before PR:

```bash
python -m py_compile auto_subtitle.py config.py subtitle/*.py
```

On Windows PowerShell:
```powershell
Get-ChildItem subtitle -Filter *.py | ForEach-Object { py -3 -m py_compile $_.FullName }
py -3 -m py_compile auto_subtitle.py
py -3 -m py_compile config.py
```

## Pull Request Rules

1. Keep changes scoped and focused.
2. Update docs when behavior changes.
3. Include reproducible steps in PR description.
4. Use clear commit messages.

## Style

- Keep code simple and explicit.
- Avoid unrelated refactors in feature/fix PRs.
- Keep scripts cross-platform when possible.
