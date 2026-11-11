---
name: github-workflow-gen
description: "一鍵在專案注入高規格 GitHub Actions CI/CD 流水線 (.github/workflows/ci.yml)，具備單元測試、規範自檢、SHA256 驗證指引與自動 Release"
---

# GitHub Actions CI/CD 流水線生成器 (github-workflow-gen)

本技能提供標準開源級別的 GitHub Actions 流水線注入能力。

## 執行命令

遵守雙層動態路徑解析規範：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
WORKFLOW_GEN_SCRIPT="$PLUGIN_ROOT/skills/github-workflow-gen/scripts/workflow_gen.py"

python3 "$WORKFLOW_GEN_SCRIPT" [--target <project-dir>] [--type <python|generic>]
```

## 功能特性
1. **雙軌測試防線**：嚴格遵循「先跑單元測試證明工具健全，再執行業務規範驗證」的防禦哲學。
2. **完整 Release 自動化**：
   - 配置 `fetch-depth: 0` 確保能回溯歷史版本標籤。
   - 動態提取雙標籤間 Commit 清單，徹底解決無 PR 時 Release Notes 空洞的官方陷阱。
   - 保留 `generate_release_notes: true`，支援有 PR 時自動追加貢獻者名單。
3. **開源供應鏈安全**：自動打包資產、計算 SHA256 數位指紋，並在 Release 頁面產生 `sha256sum -c` 一鍵校驗代碼塊。
