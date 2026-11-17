#!/usr/bin/env python3
"""
GitHub Actions Workflow Generator
一鍵在專案注入高規格 CI & Release 流水線。
"""

import sys
import argparse
from pathlib import Path


CI_TEMPLATE = r"""name: CI & Release Flow

on:
  push:
    branches:
      - main
    tags:
      - "v*"
  pull_request:
    branches:
      - main

permissions:
  contents: write

jobs:
  test:
    name: Validate Standards & Unit Tests
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f tests/requirements.txt ]; then pip install -r tests/requirements.txt; fi
          pip install pyyaml || true

      - name: Verify Python Syntax
        run: python -m compileall -q .

      - name: Run Unit Tests
        run: |
          if [ -f run_tests.py ]; then
            python run_tests.py
          elif [ -d tests ] || [ -d test ]; then
            python -m unittest discover tests || python -m unittest discover test
          else
            echo "未檢測到測試目錄，跳過單元測試。"
          fi

      - name: Validate Standards
        run: |
          if [ -f scripts/validate.py ]; then
            python scripts/validate.py
          fi

      - name: Validate Docs & Agent Instructions
        run: |
          python - << 'PY'
          import re, sys
          from pathlib import Path
          from urllib.parse import unquote

          root = Path(".")
          errors = []
          readme = root / "README.md"
          if not readme.is_file() or not readme.read_text(encoding="utf-8", errors="ignore").strip():
              errors.append("README.md is missing or empty.")
          else:
              txt = readme.read_text(encoding="utf-8", errors="ignore")
              for ph in ("<your-username>", "<owner>", "<your-org>"):
                  if ph in txt:
                      errors.append(f"README.md contains unreplaced placeholder: {ph}")
              if re.search(r"github\.com[:/][^/\s]+/<repo-name>", txt, re.I):
                  errors.append("README.md contains unreplaced repository URL placeholder: <repo-name>")

          for sub in ("", ".agents", ".agents/rules", ".agent", ".agent/rules", ".claude"):
              d = root / sub if sub else root
              if not d.is_dir():
                  continue
              for f in d.iterdir():
                  if f.is_file() and f.name.lower() in ("agents.md", "claude.md", "gemini.md") and f.name not in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
                      errors.append(f"{f} has non-standard casing; use uppercase filename.")

          for rel in ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "GEMINI.md", ".agents/AGENTS.md", ".agents/rules/AGENTS.md", ".agent/AGENTS.md", ".agent/rules/AGENTS.md", ".claude/CLAUDE.md"):
              p = root / rel
              if p.is_file():
                  raw = p.read_bytes()
                  txt = raw.decode("utf-8", errors="ignore")
                  if re.match(r"^---\s*\r?\n.*?\r?\n---", txt, re.DOTALL):
                      errors.append(f"{rel} must not contain YAML frontmatter.")
                  if len(raw) > 24000:
                      errors.append(f"{rel} exceeds 24000-byte limit ({len(raw)} bytes).")

          fence_re = re.compile(r"```.*?```", re.DOTALL)
          link_re = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
          md_targets = [readme] if readme.is_file() else []
          if (root / "docs").is_dir():
              md_targets.extend(sorted((root / "docs").rglob("*.md")))
          for md in md_targets:
              cleaned = fence_re.sub("", md.read_text(encoding="utf-8", errors="ignore"))
              for raw_target in link_re.findall(cleaned):
                  t = raw_target.strip().split()[0].strip("<>")
                  if not t or t.startswith("#") or re.match(r"^(?:https?|mailto|ftp|file|tel|data):", t, re.I):
                      continue
                  rel_path = unquote(t.split("#", 1)[0].split("?", 1)[0])
                  if rel_path:
                      dest = (root / rel_path.lstrip("/")) if rel_path.startswith("/") else (md.parent / rel_path).resolve()
                      if not dest.exists():
                          errors.append(f"{md}: broken local link -> {rel_path}")

          if errors:
              print("\n".join(f"::error::{e}" for e in errors))
              sys.exit(1)
          print("Docs & agent instructions check passed.")
          PY

  release:
    name: GitHub Release & Asset Packaging
    needs: test
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code (Full history for changelog)
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate Release Notes from Commits
        run: |
          VERSION="${GITHUB_REF_NAME}"
          PREV_TAG=$(git describe --tags --abbrev=0 "${VERSION}^" 2>/dev/null || echo "")

          cat << 'EOF' > release_notes.md
          ## 開源供應鏈安全校驗 (Asset Integrity & Verification)

          發布資產附帶 `.sha256` 數位指紋檔案。下載後可在終端執行以下標準指令進行一鍵無人值守校驗：

          ```bash
          sha256sum -c <archive_name>.tar.gz.sha256
          ```

          ---

          ## 本次變更詳情 (What's Changed)

          EOF

          if [ -n "$PREV_TAG" ]; then
            git log "${PREV_TAG}..${VERSION}" --no-merges --pretty=format:"* %s (%h)" >> release_notes.md
          else
            git log "${VERSION}" --no-merges --pretty=format:"* %s (%h)" >> release_notes.md
          fi
          echo "" >> release_notes.md

      - name: Package Release Assets
        run: |
          VERSION="${GITHUB_REF_NAME}"
          REPO_NAME="${{ github.event.repository.name }}"
          ARCHIVE_NAME="${REPO_NAME}-${VERSION}.tar.gz"
          
          # 打包至 /tmp 避免當前目錄檔案正在寫入觸發 "file changed as we read it"
          tar --exclude='.git' --exclude='.github' -czvf "/tmp/${ARCHIVE_NAME}" .
          mv "/tmp/${ARCHIVE_NAME}" .
          sha256sum "${ARCHIVE_NAME}" > "${ARCHIVE_NAME}.sha256"

      - name: Create Release
        uses: softprops/action-gh-release@v2
        with:
          body_path: release_notes.md
          files: |
            *.tar.gz
            *.tar.gz.sha256
            install.sh
          generate_release_notes: true
          draft: false
          prerelease: false
"""


def generate_workflow(target_dir: Path, force: bool = False) -> Path:
    """在指定目錄生成 .github/workflows/ci.yml"""
    workflows_dir = target_dir / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    ci_file = workflows_dir / "ci.yml"
    if ci_file.exists() and not force:
        print(f"ℹ `{ci_file}` 已存在。若需覆蓋請加上 --force。")
        return ci_file

    ci_file.write_text(CI_TEMPLATE, encoding="utf-8")
    print(f"✔ 成功於 `{ci_file}` 注入標準 GitHub Actions CI/CD 流水線！")
    return ci_file


def main():
    parser = argparse.ArgumentParser(description="GitHub Actions CI/CD 流水線生成器")
    parser.add_argument("--target", default=".", help="目標專案目錄（預設當前目錄）")
    parser.add_argument("--force", action="store_true", help="覆蓋已存在的 ci.yml")

    args = parser.parse_args()
    target_path = Path(args.target).resolve()
    generate_workflow(target_path, force=args.force)


if __name__ == "__main__":
    main()
