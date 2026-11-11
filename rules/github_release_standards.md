---
trigger: model_decision
description: "當建立 GitHub 遠端倉庫、設定 GitHub Actions CI/CD 流水線、發布 Release 或執行 Git 推送部署時觸發"
---

# GitHub 開源發布與 DevOps 工程規範 (GitHub DevOps Standards)

當在任何工作區中配置 GitHub 遠端倉庫、編寫 GitHub Actions CI/CD 工作流、發布版本標籤或執行開源交付時，必須無條件嚴格遵守以下體系化工程標準：

---

### 1. 雙軌測試防線原則 (Dual-Track Validation Pipeline)

- **單元測試先於規範驗證**：
  在 CI/CD 流水線中，必須先跑 `tests/` 下的單元測試（證明測試對象與工具模組運作正常），通過後才能執行 `scripts/validate.py` 等業務規範驗收。若單元測試未通過，直接中斷流程。
- **質檢靶場與幹活工具分離**：
  `tests/` 存放白箱單元測試（如 `unittest.TestCase`），`scripts/` 存放日常幹活或業務格式驗證工具，職責不可混淆。

---

### 2. 開源供應鏈安全與 SHA-256 驗證鐵律 (Supply Chain Integrity)

- **獨立 `.sha256` 檔案的必要性**：
  所有隨 Release 發布的二進位或打包檔案（如 `*.tar.gz`, `*.zip`），發布時必須在同一 Release 頁面附帶對應的 `<filename>.sha256` 檔案。
- **相容性與無人值守校驗語法**：
  校驗檔內容必須嚴格遵循 POSIX / GNU `sha256sum` 標準格式：
  `<64位元16進位雜湊值>  <檔名>`（注意：雜湊值與檔名之間必須使用**雙空格**分隔，且檔名僅保留 basename，不含絕對或相對路徑）。
  這允許終端使用者與自動化腳本使用單一命令完成防篡改校驗：
  ```bash
  sha256sum -c <filename>.sha256
  ```
- **頁面舉證**：
  Release 說明頁面中，必須顯式提供 SHA-256 數位指紋與一鍵校驗代碼塊，建立完整的開源信任鏈。

---

### 3. 變更日誌雙重保障機制 (Dual-Layer Changelog Protocol)

- **GitHub 原生自動說明的盲區**：
  GitHub 的 `generate_release_notes: true` 機制僅聚合由 Pull Request 合併產生的變更。在個人維護、直接 Push 至 `main` 分支的專案中，會導致生成的 Release Notes 僅有空洞的 Full Changelog 比較連結。
- **動態 Commit 提取保底**：
  CI 流水線或發布輔助工具必須先透過 `git log --no-merges` 動態提取兩個標籤間的所有 Commit 作為 `release_notes.md` 的基礎內容，再附加至 Release 說明中；同時保留 `generate_release_notes: true`，實現 PR 與 Commit 變更雙重聚合。

---

### 4. Git 操作破壞性防護 (Git Destructive Guard)

- **嚴禁 Force Push**：
  嚴禁在專案中執行 `git push --force` 或 `git push -f`。此操作破壞協作者之遠端歷史，必須透過常規提交或分支合併解決歷史衝突。
- **機密零洩漏**：
  嚴禁將包含 Token（如 `ghp_*`, `gho_*`）、私鑰或憑證的設定檔提交至版本庫。專案根目錄必須在 `.gitignore` 中明確排除敏感檔案。

---

### 5. 雙層動態路徑解析規範 (Zero Hardcode Protocol)

- 外掛內所有 Skill 命令與 Python 呼叫，必須遵循動態解析協議，嚴禁寫死個人絕對路徑：
  ```bash
  PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
  ```
- Python 直譯器一律調用全域環境：`~/gemini_py3_env/bin/python`。
