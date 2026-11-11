---
name: github-release-manager
description: "版本發布全流程管理：安全建立與推送 Git Tag、動態提取 Commit 生成 Release Notes、計算發布壓縮檔之 SHA256 數位指紋與產生 `sha256sum -c` 校驗檔"
---

# GitHub 版本發布管理器 (github-release-manager)

專為開源專案與 Antigravity 插件打造的端到端 Release 發布輔助工具鏈。

## 執行命令

遵守雙層動態路徑解析規範：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
RELEASE_HELPER="$PLUGIN_ROOT/skills/github-release-manager/scripts/release_helper.py"

# 1. 動態生成 Release Notes（聚合 Commit 清單，排除 Merge）
python3 "$RELEASE_HELPER" notes [--from-ref <tag>] [--to-ref HEAD] [-o release_notes.md]

# 2. 計算發布資產之 SHA256 並生成 .sha256 校驗檔（相容 sha256sum -c）
python3 "$RELEASE_HELPER" hash path/to/archive.tar.gz [-o path/to/archive.tar.gz.sha256]

# 3. 安全建立並推送版本 Tag（含 Working Tree 乾淨預檢）
python3 "$RELEASE_HELPER" tag v1.0.0 -m "Release v1.0.0" [--push]
```

## 功能特性
1. **防止空洞 Release Notes**：
   自動抓取前一個 Tag 至當前 HEAD 的非 Merge Commits，徹底擺脫 GitHub 原生 PR 自動生成在無 PR 時僅產生空洞對比連結的困境。
2. **開源供應鏈防偽 (Supply Chain Integrity)**：
   產出標準雙空格格式 `<hash>  <filename>` 的 `.sha256` 檔案，讓使用者與 CI 系統可直接透過 `sha256sum -c` 進行確定性無人值守驗證。
3. **安全防呆發布**：
   建立 Tag 前主動檢測工作區狀態，嚴禁在 dirty 狀態下誤發版本標籤。
