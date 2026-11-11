# GitHub DevOps & Release Automation Toolkit (`github-devops`)

[![Validate Standards & Unit Tests](https://github.com/shiroiyuki/antigravity_github_devops/actions/workflows/ci.yml/badge.svg)](https://github.com/shiroiyuki/antigravity_github_devops/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

專為 **Google Antigravity (AGY)** 開發者與開源專案打造的五位一體（Plugin + Hook + Rule + Agent + Skill）完整 GitHub DevOps 自動化工具套件。

提供零外部 CLI 依賴的 REST API 建倉、高規格雙軌 CI/CD 注入、開源供應鏈 SHA-256 防偽驗證、Release Notes Commit 自動聚合、PreToolUse Force-Push 攔截與 Pre-Push 本地單元測試守門。

---

## 核心架構與五位一體能力

```
antigravity_github_devops/
├── plugin.json                 # 外掛套件清單 (Metadata & Display)
├── hooks.json                  # PreToolUse 守護鉤子宣告 (Matcher: run_command)
├── hooks/
│   └── devops_guard.py         # 底層安全防線 (Force-push, 敏感機密, Pre-push 測試)
├── rules/
│   └── github_release_standards.md # 發布規範與供應鏈安全準則 (Trigger: model_decision)
├── agents/
│   └── devops-engineer/
│       └── agent.md            # DevOps 專業工位人設 (Model: pro, Subagent)
├── skills/
│   ├── github-repo-init/       # 零 CLI 依賴 REST API 建倉技能
│   ├── github-workflow-gen/    # 標準雙軌 CI/CD 生成器技能
│   └── github-release-manager/ # 版本發布管理與 SHA-256 校驗技能
└── run_tests.py                # 統一多模組單元測試驅動器
```

---

## 功能特性 (Key Features)

### 1. 零 CLI 依賴建倉 (`github-repo-init`)
- 直接解析本機 `~/.config/gh/hosts.yml` 或環境變數 `GITHUB_TOKEN`，直連 GitHub REST API 建立倉庫。
- 自動初始化本地倉庫（`git init -b main`）並綁定 `origin`，支援現有倉庫安全覆蓋與防呆對齊。

### 2. 雙軌測試與開源 Release 流水線 (`github-workflow-gen`)
- 嚴格落實「單元測試（Unit Tests）前置，再執行業務規範（Validate Standards）」的防禦哲學。
- 自動打包發布資產，動態生成相容 `sha256sum -c` 的 `.tar.gz.sha256` 數位指紋檔案。
- 動態提取雙標籤間 Commit 清單，徹底解決無 PR 時 Release 說明空洞的 GitHub 官方缺陷。

### 3. 發布全流程管理 (`github-release-manager`)
- 提供 `notes`、`hash`、`tag` 三合一發布輔助 CLI。
- 嚴格預檢 Working Tree 狀態，防範 Dirty 狀態誤發 Tag。

### 4. 底層硬性安全守門 (`PreToolUse Hook`)
- **Force Push 零容忍**：硬性阻斷 `git push --force` / `-f` / `--force-with-lease`，守護遠端協作歷史。
- **機密外洩防護**：提交（`git commit`）前主動掃描暫存區，攔截 `.env`、私鑰與 GitHub Token 洩漏。
- **Pre-Push 單元測試守門**：在推送（`git push`）前自動執行本地單元測試，測試未全綠前阻斷推送。

---

## 零 Hardcode 動態路徑解析協議

本外掛全面遵循 Antigravity 雙層動態路徑解析標準（優先載入工作區本地安裝，若無則回退全域外掛），嚴禁硬編碼任何個人本機路徑：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"

# 調用建倉技能
~/gemini_py3_env/bin/python "$PLUGIN_ROOT/skills/github-repo-init/scripts/repo_ctl.py" --name <repo-name>

# 注入雙軌 CI/CD 流水線
~/gemini_py3_env/bin/python "$PLUGIN_ROOT/skills/github-workflow-gen/scripts/workflow_gen.py"

# 版本發布管理
~/gemini_py3_env/bin/python "$PLUGIN_ROOT/skills/github-release-manager/scripts/release_helper.py" tag v1.0.0 --push
```

---

## 單元測試驗證 (Unit Tests)

本外掛具備完整的白箱單元測試覆蓋：

```bash
~/gemini_py3_env/bin/python run_tests.py
```

測試涵蓋：
- Force Push 與正規表達式單詞邊界攔截。
- 暫存區敏感檔案名稱與 Token 正則掃描。
- Pre-Push 本地單元測試成功放行與失敗阻斷。
- GitHub Token 提取與本地 Git Remote 綁定機制。
- CI 流水線模板結構與關鍵步驟完整性。
- SHA-256 計算、標準雙空格校驗檔生成與 Git Tag 生命週期管理。

---

## 安裝指南 (Installation)

### 方法 1：全域安裝（推薦）
將專案複製或軟連結至全域外掛目錄：
```bash
ln -s /path/to/antigravity_github_devops ~/.gemini/config/plugins/github-devops
```

### 方法 2：單一工作區本地安裝
在目標專案根目錄下：
```bash
mkdir -p .agents/plugins
ln -s /path/to/antigravity_github_devops .agents/plugins/github-devops
```

---

## License

本專案採用 [MIT License](LICENSE) 開源授權。
