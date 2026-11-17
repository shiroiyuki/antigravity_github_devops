---
name: github-docs-guard
description: "稽核與生成跨工具三層專案文件：AGENTS.md（相容 OpenAI Codex / Antigravity 開放標準，可選 CLAUDE.md @AGENTS.md 橋接）、docs/ 人類技術文件與 README.md 總覽；檢查連結斷鏈、佔位符、大小寫與 24KB 預算。"
---

# 跨工具專案文件與 AI 指引守護 (`github-docs-guard`)

本技能依據 **OpenAI `AGENTS.md` 開放標準**、**Anthropic Claude Code `CLAUDE.md` 規範** 與 **Google Antigravity `AGENTS.md` / `GEMINI.md` 規範**，分離並稽核倉庫內的三層文件：

1. **AI Agent 指引 (`AGENTS.md` / `CLAUDE.md` / `GEMINI.md`)**：給 AI 看的實作、修改、建置與測試指令（嚴禁 YAML Frontmatter，控制在 `<= 24,000 bytes` 且精簡 `< 200` 行）。
2. **人類深度文件 (`docs/*.md`)**：架構設計、協議與除錯手冊（不常駐佔用 Agent Context）。
3. **專案門面 (`README.md`)**：給所有人看的專案介紹、Preview、快速安裝與測試總覽。

## 執行命令

遵守雙層動態路徑解析規範：

```bash
PLUGIN_ROOT="$([ -d .agents/plugins/github-devops ] && echo .agents/plugins/github-devops || echo ~/.gemini/config/plugins/github-devops)"
DOC_AUDIT_SCRIPT="$PLUGIN_ROOT/skills/github-docs-guard/scripts/doc_audit.py"

# 1. 稽核目標倉庫文件與 AI 指引（加 --strict 可在錯誤時回傳非零退出碼）
python3 "$DOC_AUDIT_SCRIPT" --target <project-dir> [--strict] [--json]

# 2. 依專案真實架構生成跨工具根目錄 AGENTS.md（可選同時生成 CLAUDE.md @AGENTS.md 橋接與 docs/）
python3 "$DOC_AUDIT_SCRIPT" --target <project-dir> --init-agents [--claude-bridge] [--init-docs] [--force]
```
