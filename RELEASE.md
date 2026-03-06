# Release Guide

## 1. Pre-Release Checklist

1. Ensure docs are up to date:
   - `README.md`
   - `DEPLOY.md`
2. Run sanity checks:
   - `python -m py_compile auto_subtitle.py config.py subtitle/*.py`
3. Verify one-click setup works:
   - Windows: `install.bat`
   - Linux/macOS: `bash setup.sh`
4. Confirm CLI help is correct:
   - `python auto_subtitle.py --help`

## 2. Versioning

Use semantic versioning:
- `MAJOR`: breaking changes
- `MINOR`: backward-compatible features
- `PATCH`: backward-compatible fixes

## 3. Tag and Release

1. Create tag:
   - `vX.Y.Z`
2. Push tag
3. Create GitHub Release from tag
4. Use [RELEASE_NOTES_TEMPLATE.md](RELEASE_NOTES_TEMPLATE.md)

## 4. Post-Release

1. Verify release assets and notes
2. Smoke test install commands from README
3. Announce updates in the project channel
