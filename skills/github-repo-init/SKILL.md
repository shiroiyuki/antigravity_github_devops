---
name: github-repo-init
description: "自動從本機配置提取 GitHub Token，透過 REST API 直連建立遠端倉庫並綁定本地 origin"
---

# GitHub 倉庫初始化與遠端綁定技能 (github-repo-init)

本技能提供無 `gh` CLI 依賴的確定性 GitHub 遠端倉庫建立與初始化能力。

## 執行命令

遵守雙層動態路徑解析與全域 Python 虛擬環境規範：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
REPO_CTL_SCRIPT="$PLUGIN_ROOT/skills/github-repo-init/scripts/repo_ctl.py"

~/gemini_py3_env/bin/python "$REPO_CTL_SCRIPT" --name <repo-name> [--private] [--desc "專案描述"]
```

## 功能特性
1. **零外部 CLI 相依**：自動讀取本機 `~/.config/gh/hosts.yml` OAuth Token 或環境變數 `GITHUB_TOKEN`，直連 GitHub REST API。
2. **自動 Git 初始化**：若當前工作區未初始化，自動執行 `git init -b main`。
3. **安全綁定遠端**：自動設定 `origin` 為 `https://github.com/<user>/<repo>.git`。
4. **防呆預檢**：若遠端已存在該倉庫，自動對齊遠端分支，不覆蓋破壞。
