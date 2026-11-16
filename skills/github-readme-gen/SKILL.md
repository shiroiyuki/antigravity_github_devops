---
name: github-readme-gen
description: "自動掃描專案或 Antigravity Plugin 結構（plugin.json、rules、skills、agents、hooks、tests、CI），生成高規格標準 README.md（含 Badges、架構樹、動態調用範例、安裝、測試與 SHA256 校驗指引）。"
---

# GitHub README 標準生成器 (`github-readme-gen`)

本技能依據開源門面與 Antigravity 規範，自動盤點目標專案或 Plugin 的結構與元數據，生成結構完整、無硬編碼路徑的標準 `README.md`。

## 執行命令

遵守雙層動態路徑解析規範：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
README_GEN_SCRIPT="$PLUGIN_ROOT/skills/github-readme-gen/scripts/readme_gen.py"

python3 "$README_GEN_SCRIPT" --target <project-dir> [--force] [--dry-run]
```

## 功能特性
1. **自動元數據探勘**：解析 `plugin.json`、`git remote origin`、`rules/*.md`、`skills/*/SKILL.md`、`agents/*/agent.md` 與 `hooks.json`。
2. **完整開源門面結構**：自動組裝 Badges（CI / Release / License / Platform）、目錄架構樹、組件特性矩陣、雙層動態路徑調用範例、三模式安裝指南、測試驗證指令與供應鏈 SHA-256 校驗指引。
3. **防誤覆蓋機制**：預設不覆蓋已存在的 `README.md`，需明確傳入 `--force`。
