#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub README Generator
自動掃描專案或 Antigravity Plugin 結構並生成標準化 README.md。
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_frontmatter(text: str) -> Dict[str, str]:
    """解析 Markdown YAML Frontmatter 基礎欄位"""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    meta: Dict[str, str] = {}
    lines = match.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" "):
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if val in (">", ">-", "|", "|-"):
                buf = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                    buf.append(lines[i].strip())
                    i += 1
                meta[key] = " ".join(p for p in buf if p)
                continue
            meta[key] = val.strip('"').strip("'")
        i += 1
    return meta


def detect_github_slug(repo_dir: Path) -> Tuple[str, str]:
    """從 git remote origin 提取 (owner, repo_name)"""
    res = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=str(repo_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if res.returncode == 0:
        url = res.stdout.strip()
        m = re.search(r"github\.com[:/]([^/]+)/([^/\s]+?)(?:\.git)?$", url)
        if m:
            return m.group(1), m.group(2)
    return "<owner>", repo_dir.name


def scan_project(target_dir: Path) -> dict:
    """掃描目標目錄結構與 Antigravity 組件元數據"""
    pjson_path = target_dir / "plugin.json"
    plugin_meta = {}
    if pjson_path.is_file():
        try:
            plugin_meta = json.loads(pjson_path.read_text(encoding="utf-8"))
        except Exception:
            plugin_meta = {}

    owner, repo_name = detect_github_slug(target_dir)
    plugin_name = plugin_meta.get("name") or repo_name
    display_name = plugin_meta.get("displayName") or plugin_name
    description = plugin_meta.get("description") or f"{display_name} repository."

    skills = []
    skills_dir = target_dir / "skills"
    if skills_dir.is_dir():
        for sdir in sorted(skills_dir.iterdir()):
            sfile = sdir / "SKILL.md"
            if sdir.is_dir() and sfile.is_file():
                fm = parse_frontmatter(sfile.read_text(encoding="utf-8"))
                skills.append({
                    "dir": sdir.name,
                    "name": fm.get("name", sdir.name),
                    "description": fm.get("description", ""),
                })

    rules = []
    rules_dir = target_dir / "rules"
    if rules_dir.is_dir():
        for rfile in sorted(rules_dir.glob("*.md")):
            if rfile.name == "README.md":
                continue
            fm = parse_frontmatter(rfile.read_text(encoding="utf-8"))
            trig = "always_on" if rfile.name in ("AGENTS.md", "GEMINI.md") else fm.get("trigger", "model_decision")
            rules.append({
                "file": rfile.name,
                "trigger": trig,
                "description": fm.get("description", ""),
            })

    agents = []
    agents_dir = target_dir / "agents"
    if agents_dir.is_dir():
        for adir in sorted(agents_dir.iterdir()):
            afile = adir / "agent.md"
            if adir.is_dir() and afile.is_file():
                fm = parse_frontmatter(afile.read_text(encoding="utf-8"))
                agents.append({
                    "dir": adir.name,
                    "name": fm.get("name", adir.name),
                    "model": fm.get("model", "inherit"),
                    "description": fm.get("description", ""),
                })

    has_hooks = (target_dir / "hooks.json").is_file()
    has_ci = (target_dir / ".github" / "workflows" / "ci.yml").is_file()
    has_install = (target_dir / "install.sh").is_file()
    has_run_tests = (target_dir / "run_tests.py").is_file()
    validators = sorted(str(p.relative_to(target_dir)) for p in (target_dir / "scripts").glob("validate*.py")) if (target_dir / "scripts").is_dir() else []
    docs = sorted(str(p.relative_to(target_dir)) for p in (target_dir / "docs").rglob("*.md")) if (target_dir / "docs").is_dir() else []
    agent_docs = [
        rel for rel in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".agents/AGENTS.md", ".agents/rules/AGENTS.md", ".claude/CLAUDE.md")
        if (target_dir / rel).is_file()
    ]

    return {
        "is_plugin": bool(plugin_meta),
        "plugin_name": plugin_name,
        "display_name": display_name,
        "version": plugin_meta.get("version", "0.1.0"),
        "description": description,
        "owner": owner,
        "repo_name": repo_name,
        "skills": skills,
        "rules": rules,
        "agents": agents,
        "docs": docs,
        "agent_docs": agent_docs,
        "has_hooks": has_hooks,
        "has_ci": has_ci,
        "has_install": has_install,
        "has_run_tests": has_run_tests,
        "validators": validators,
        "has_requirements": (target_dir / "requirements.txt").is_file(),
        "has_license": (target_dir / "LICENSE").is_file(),
    }


def build_tree_lines(meta: dict) -> List[str]:
    """生成專案目錄結構樹"""
    lines = [f"{meta['repo_name']}/"]
    if meta["is_plugin"]:
        lines.append(f"├── plugin.json                      # 外掛套件清單 (v{meta['version']})")
    if meta["has_hooks"]:
        lines.append("├── hooks.json                       # 生命週期事件註冊")
    if meta["rules"]:
        lines.append("├── rules/")
        for idx, r in enumerate(meta["rules"]):
            branch = "└──" if idx == len(meta["rules"]) - 1 else "├──"
            lines.append(f"│   {branch} {r['file']:<28} # {r['trigger']}")
    if meta["agents"]:
        lines.append("├── agents/")
        for idx, a in enumerate(meta["agents"]):
            branch = "└──" if idx == len(meta["agents"]) - 1 else "├──"
            lines.append(f"│   {branch} {a['dir']}/agent.md")
    if meta["skills"]:
        lines.append("├── skills/")
        for idx, s in enumerate(meta["skills"]):
            branch = "└──" if idx == len(meta["skills"]) - 1 else "├──"
            lines.append(f"│   {branch} {s['dir']}/")
    if meta["docs"]:
        lines.append("├── docs/                            # 人類技術文件與指南")
    for adoc in meta["agent_docs"]:
        lines.append(f"├── {adoc:<32} # AI Agent 工程操作規範")
    if meta["has_install"]:
        lines.append("├── install.sh                       # 一鍵部署安裝腳本")
    if meta["has_run_tests"]:
        lines.append("├── run_tests.py                     # 單元測試執行器")
    if meta["validators"]:
        lines.append(f"├── {meta['validators'][0]:<32} # 規範與抗硬編碼驗證器")
    if meta["has_ci"]:
        lines.append("└── .github/workflows/ci.yml         # CI/CD 雙軌測試與 Release 流水線")
    else:
        lines.append("└── README.md")
    return lines


def render_readme(meta: dict) -> str:
    """依據掃描結果渲染標準 README Markdown"""
    owner = meta["owner"]
    repo = meta["repo_name"]
    title = f"{meta['display_name']} (`{meta['plugin_name']}`)" if meta["is_plugin"] and meta["display_name"] != meta["plugin_name"] else meta["display_name"]

    badges = []
    if meta["has_ci"]:
        badges.append(
            f"[![CI & Release](https://github.com/{owner}/{repo}/actions/workflows/ci.yml/badge.svg)]"
            f"(https://github.com/{owner}/{repo}/actions/workflows/ci.yml)"
        )
    badges.append(
        f"[![Release](https://img.shields.io/github/v/release/{owner}/{repo})]"
        f"(https://github.com/{owner}/{repo}/releases)"
    )
    if meta["has_license"]:
        badges.append("[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)")
    if meta["is_plugin"]:
        badges.append("[![Platform](https://img.shields.io/badge/Platform-Google%20Antigravity-blue.svg)](https://antigravity.google)")

    sections = [
        f"# {title}\n",
        "\n".join(badges) + "\n",
        f"{meta['description']}\n",
        "---\n",
        "## 核心架構與目錄結構 (Architecture)\n",
        "```text\n" + "\n".join(build_tree_lines(meta)) + "\n```\n",
        "---\n",
    ]

    if meta["skills"]:
        rows = [
            "| 技能名稱 | 用途說明 |",
            "| :--- | :--- |",
        ]
        for s in meta["skills"]:
            desc = s["description"].replace("|", "\\|")
            rows.append(f"| **`{s['name']}`** | {desc} |")
        sections.append("## 核心技能清單 (Skills)\n\n" + "\n".join(rows) + "\n\n---\n")

    if meta["rules"] or meta["agents"]:
        extra = ["## 規範與子代理組件 (Rules & Agents)\n"]
        for r in meta["rules"]:
            extra.append(f"- **Rule** `rules/{r['file']}` (`{r['trigger']}`): {r['description']}")
        for a in meta["agents"]:
            extra.append(f"- **Agent** `agents/{a['dir']}/agent.md` (`model: {a['model']}`): {a['description']}")
        sections.append("\n".join(extra) + "\n\n---\n")

    if meta["docs"] or meta["agent_docs"]:
        doc_lines = ["## 文件與開發指引 (Documentation & AI Guidelines)\n"]
        for d in meta["docs"]:
            doc_lines.append(f"- [{d}]({d})")
        for adoc in meta["agent_docs"]:
            doc_lines.append(f"- [{adoc}]({adoc}) — AI coding, modification & testing conventions")
        sections.append("\n".join(doc_lines) + "\n\n---\n")

    if meta["is_plugin"]:
        pname = meta["plugin_name"]
        sections.append(
            "## 零硬編碼動態調用範例 (Dynamic Path Resolution)\n\n"
            "```bash\n"
            f'PLUGIN_ROOT="$([ -d .agents/plugins/{pname} ] && echo .agents/plugins/{pname} || echo ~/.gemini/config/plugins/{pname})"\n'
            "```\n\n---\n"
        )

    install_lines = ["## 安裝指南 (Installation)\n"]
    if meta["has_install"]:
        install_lines.extend([
            "```bash",
            "# 全域安裝（預設）",
            "./install.sh --global",
            "",
            "# 開發模式軟連結安裝",
            "./install.sh --global --symlink",
            "",
            "# 僅安裝至當前專案工作區",
            "./install.sh --workspace",
            "```",
        ])
    elif meta["is_plugin"]:
        install_lines.extend([
            "```bash",
            f"git clone https://github.com/{owner}/{repo}.git ~/.gemini/config/plugins/{meta['plugin_name']}",
            "```",
        ])
    if meta["has_requirements"]:
        install_lines.extend([
            "",
            "安裝 Python 相依套件：",
            "```bash",
            "pip install -r requirements.txt",
            "```",
        ])
    sections.append("\n".join(install_lines) + "\n\n---\n")

    test_cmds = []
    if meta["has_run_tests"]:
        test_cmds.append("python3 run_tests.py")
    else:
        test_cmds.append("python3 -m unittest discover tests")
    for val in meta["validators"]:
        test_cmds.append(f"python3 {val}")
    if meta["is_plugin"]:
        test_cmds.append("agy plugin validate . --strict")
    sections.append(
        "## 單元測試與規範驗證 (Testing & Validation)\n\n```bash\n"
        + "\n".join(test_cmds)
        + "\n```\n\n---\n"
    )

    sections.append(
        "## 發布與供應鏈安全校驗 (Release & Supply Chain Integrity)\n\n"
        "發布版本時推送 `v*` 標籤即可觸發自動化打包與 `.sha256` 校驗檔生成：\n\n"
        "```bash\n"
        f"sha256sum -c {repo}-v{meta['version']}.tar.gz.sha256\n"
        "```\n\n---\n"
    )

    sections.append("## License\n\n本專案採用 [MIT License](LICENSE) 開源授權。\n")
    return "\n".join(sections)


def generate_readme(target_dir: Path, output_path: Optional[Path] = None, force: bool = False, dry_run: bool = False) -> Path:
    """掃描目標專案並寫入 README.md"""
    dest = output_path or (target_dir / "README.md")
    if dest.exists() and not force and not dry_run:
        print(f"ℹ `{dest}` 已存在。若需覆蓋請加上 --force。")
        return dest

    meta = scan_project(target_dir)
    content = render_readme(meta)
    if dry_run:
        sys.stdout.write(content)
        return dest

    dest.write_text(content, encoding="utf-8")
    print(f"✔ 成功生成標準 README: {dest}")
    return dest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="GitHub & Antigravity 標準 README 生成器")
    parser.add_argument("--target", default=".", help="目標專案目錄（預設當前目錄）")
    parser.add_argument("-o", "--output", help="輸出檔案路徑（預設 <target>/README.md）")
    parser.add_argument("--force", action="store_true", help="覆蓋已存在的 README.md")
    parser.add_argument("--dry-run", action="store_true", help="僅輸出預覽，不寫入檔案")
    args = parser.parse_args(argv)

    target_dir = Path(args.target).resolve()
    out = Path(args.output).resolve() if args.output else None
    generate_readme(target_dir, output_path=out, force=args.force, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
