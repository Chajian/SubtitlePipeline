# 发布指南

英文版：[RELEASE.md](RELEASE.md)

## 1. 发布前检查清单

1. 确保文档已更新：
   - `README.md`
   - `DEPLOY.md`
2. 运行基础校验：
   - `python -m py_compile auto_subtitle.py config.py subtitle/*.py`
3. 验证一键安装可用：
   - Windows：`install.bat`
   - Linux/macOS：`bash setup.sh`
4. 确认 CLI 帮助信息正确：
   - `python auto_subtitle.py --help`

## 2. 版本规范

使用语义化版本：
- `MAJOR`：不兼容变更
- `MINOR`：向后兼容的新功能
- `PATCH`：向后兼容的修复

## 3. 打标签并发布

1. 创建标签：
   - `vX.Y.Z`
2. 推送标签
3. 基于标签创建 GitHub Release
4. 使用 [RELEASE_NOTES_TEMPLATE.zh-CN.md](RELEASE_NOTES_TEMPLATE.zh-CN.md)

## 4. 发布后

1. 校验发布资产和说明
2. 按 README 做安装冒烟测试
3. 在项目频道同步发布信息
