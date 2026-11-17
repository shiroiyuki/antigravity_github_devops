#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Tool Documentation & Agent Instruction Auditor / Scaffolder
Supports OpenAI Codex AGENTS.md, Anthropic Claude Code CLAUDE.md,
Google Antigravity (.agents/AGENTS.md, GEMINI.md), docs/, and README.md.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import unquote


AGENT_CANONICAL_PATHS = (
    "AGENTS.md",
    "AGENTS.override.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".agents/AGENTS.md",
    ".agents/rules/AGENTS.md",
    ".agent/AGENTS.md",
    ".agent/rules/AGENTS.md",
    ".claude/CLAUDE.md",
)

CASE_TYPO_DIRS = ("", ".agents", ".agents/rules", ".agent", ".agent/rules", ".claude")
CASE_CANONICAL_NAMES = {
    "agents.md": "AGENTS.md",
    "agents.override.md": "AGENTS.override.md",
    "claude.md": "CLAUDE.md",
    "claude.local.md": "CLAUDE.local.md",
    "gemini.md": "GEMINI.md",
}

PLACEHOLDER_PATTERNS = (
    "<your-username>",
    "<owner>",
    "<your-org>",
)
URL_PLACEHOLDER_RE = re.compile(r"github\.com[:/][^/\s]+/<repo-name>", re.IGNORECASE)

MD_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
AGY_BYTE_CAP = 24000
CONCISE_LINE_ADVISORY = 200


def has_yaml_frontmatter(text: str) -> bool:
    """Returns True if markdown starts with a YAML frontmatter block."""
    return bool(re.match(r"^---\s*\r?\n.*?\r?\n---(?:\s*\r?\n|\s*$)", text, re.DOTALL))


def extract_local_links(md_text: str) -> List[str]:
    """Extracts relative local file targets from markdown links outside fenced code blocks."""
    cleaned = FENCE_RE.sub("", md_text)
    links: List[str] = []
    for raw in MD_LINK_RE.findall(cleaned):
        target = raw.strip().split()[0].strip("<>")
        if not target or target.startswith("#"):
            continue
        if re.match(r"^(?:https?|mailto|ftp|file|tel|data):", target, re.IGNORECASE):
            continue
        path_only = target.split("#", 1)[0].split("?", 1)[0]
        if path_only:
            links.append(unquote(path_only))
    return links


def check_broken_links(md_path: Path, repo_root: Path) -> List[str]:
    """Checks relative links in a markdown file against disk."""
    broken: List[str] = []
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return broken

    for rel in extract_local_links(text):
        if rel.startswith("/"):
            candidate = repo_root / rel.lstrip("/")
        else:
            candidate = (md_path.parent / rel).resolve()
        if not candidate.exists():
            broken.append(rel)
    return broken


def detect_case_typos(repo_root: Path) -> List[Tuple[str, str]]:
    """Detects mis-cased instruction files like .agent/Agents.md or agents.md."""
    typos: List[Tuple[str, str]] = []
    for sub in CASE_TYPO_DIRS:
        parent = repo_root / sub if sub else repo_root
        if not parent.is_dir():
            continue
        for child in parent.iterdir():
            if not child.is_file():
                continue
            low = child.name.lower()
            expected = CASE_CANONICAL_NAMES.get(low)
            if expected and child.name != expected:
                rel = str(child.relative_to(repo_root))
                typos.append((rel, expected))
    return typos


def _is_gitignored(repo_root: Path, filename: str) -> bool:
    gi = repo_root / ".gitignore"
    if not gi.is_file():
        return False
    lines = [ln.strip() for ln in gi.read_text(encoding="utf-8", errors="ignore").splitlines()]
    return any(ln == filename or ln == f"/{filename}" or ln == f"*{filename}" for ln in lines if ln and not ln.startswith("#"))


def audit_project(target_dir: Path) -> Dict[str, object]:
    """Audits AGENTS.md/CLAUDE.md/GEMINI.md, docs/, and README.md in target_dir."""
    root = target_dir.resolve()
    errors: List[str] = []
    warnings: List[str] = []

    is_plugin = (root / "plugin.json").is_file()

    # 1. Agent Instruction Files (OpenAI AGENTS.md, Claude CLAUDE.md, AGY GEMINI.md)
    found_agent_files: List[str] = []
    for rel in AGENT_CANONICAL_PATHS:
        fpath = root / rel
        if fpath.is_file():
            found_agent_files.append(rel)
            if is_plugin and rel == "AGENTS.md":
                errors.append(
                    "AGENTS.md at plugin root is not loaded by Antigravity plugins and fails `agy plugin validate --strict`; move plugin rules to `rules/AGENTS.md` or contributor guides to `docs/`."
                )
            raw_bytes = fpath.read_bytes()
            text = raw_bytes.decode("utf-8", errors="ignore")
            line_count = len(text.splitlines())

            if has_yaml_frontmatter(text):
                errors.append(
                    f"{rel}: contains YAML frontmatter (---). AGENTS.md/CLAUDE.md/GEMINI.md must be plain Markdown without trigger frontmatter."
                )
            if len(raw_bytes) > AGY_BYTE_CAP:
                errors.append(
                    f"{rel}: size {len(raw_bytes)} bytes exceeds {AGY_BYTE_CAP}-byte limit (risks truncation in Antigravity / context bloat in Codex)."
                )
            elif line_count > CONCISE_LINE_ADVISORY:
                warnings.append(
                    f"{rel}: {line_count} lines exceeds concise guideline ({CONCISE_LINE_ADVISORY} lines); move deep specs into docs/."
                )

            for link in check_broken_links(fpath, root):
                errors.append(f"{rel}: broken local link -> {link}")

    for typo_rel, expected in detect_case_typos(root):
        errors.append(
            f"{typo_rel}: non-standard casing; rename to uppercase `{expected}` for Linux/Codex/Claude/Antigravity compatibility."
        )

    if (root / ".agent").is_dir():
        warnings.append(
            "`.agent/` is an old legacy directory style (not read by OpenAI Codex or Claude Code); migrate to root `AGENTS.md` and `.agents/`."
        )

    if (root / "CLAUDE.local.md").is_file() and not _is_gitignored(root, "CLAUDE.local.md"):
        warnings.append("CLAUDE.local.md exists but is not listed in .gitignore.")

    if not found_agent_files and not is_plugin:
        warnings.append("No AGENTS.md, CLAUDE.md, or GEMINI.md found (recommended: root AGENTS.md).")

    # 2. Human Documentation (docs/)
    docs_files: List[str] = []
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for md in sorted(docs_dir.rglob("*.md")):
            rel = str(md.relative_to(root))
            docs_files.append(rel)
            for link in check_broken_links(md, root):
                errors.append(f"{rel}: broken local link -> {link}")

    # 3. README.md (Project Intro & Guide)
    readme_path = root / "README.md"
    if not readme_path.is_file():
        errors.append("README.md is missing.")
    else:
        readme_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        if not readme_text.strip():
            errors.append("README.md is empty.")
        for ph in PLACEHOLDER_PATTERNS:
            if ph in readme_text:
                errors.append(f"README.md contains unreplaced placeholder `{ph}`.")
        if URL_PLACEHOLDER_RE.search(readme_text):
            errors.append("README.md contains unreplaced repository URL placeholder `<repo-name>`.")
        for link in check_broken_links(readme_path, root):
            errors.append(f"README.md: broken local link -> {link}")
        if docs_files and "docs/" not in readme_text:
            warnings.append("docs/ contains markdown files, but README.md does not reference `docs/`.")

    return {
        "target": str(root),
        "agent_files": found_agent_files,
        "docs_files": docs_files,
        "has_readme": readme_path.is_file(),
        "errors": errors,
        "warnings": warnings,
        "passed": len(errors) == 0,
    }


def _detect_commands(root: Path) -> Tuple[List[str], List[str]]:
    """Detects realistic setup and test commands from project files."""
    setup_cmds: List[str] = []
    test_cmds: List[str] = []

    if (root / "requirements.txt").is_file():
        setup_cmds.append("pip install -r requirements.txt")
    if (root / "pyproject.toml").is_file():
        setup_cmds.append("pip install -e .")
        test_cmds.append("pytest")
    if (root / "package.json").is_file():
        setup_cmds.append("npm install")
        test_cmds.append("npm test")
    if (root / "Cargo.toml").is_file():
        test_cmds.append("cargo test")
    if (root / "go.mod").is_file():
        test_cmds.append("go test ./...")

    if (root / "run_tests.py").is_file():
        test_cmds.append("python3 run_tests.py")
    elif (root / "tests").is_dir():
        test_cmds.append("python3 -m unittest discover -s tests -v")
    elif (root / "test").is_dir():
        test_cmds.append("python3 -m unittest discover -s test -v")

    if (root / "scripts").is_dir():
        for val in sorted((root / "scripts").glob("validate*.py")):
            test_cmds.append(f"python3 scripts/{val.name}")

    if (root / "plugin.json").is_file():
        test_cmds.append("agy plugin validate . --strict")

    if not setup_cmds:
        setup_cmds.append("# Inspect project manifest before installing dependencies")
    if not test_cmds:
        test_cmds.append("# Add project unit tests under tests/ and run them before committing")

    return setup_cmds, list(dict.fromkeys(test_cmds))


def scaffold_agents_md(
    target_dir: Path,
    agents_rel_path: str = "AGENTS.md",
    claude_bridge: bool = False,
    init_docs: bool = False,
    force: bool = False,
) -> List[Path]:
    """Generates cross-tool AGENTS.md (and optional CLAUDE.md bridge / docs starter)."""
    root = target_dir.resolve()
    created: List[Path] = []
    setup_cmds, test_cmds = _detect_commands(root)

    agents_dest = root / agents_rel_path
    if not agents_dest.exists() or force:
        agents_dest.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"# {root.name} — Agent Working Instructions",
            "",
            "Concise operational rules for AI coding agents (OpenAI Codex, Claude Code, Antigravity).",
            "Keep project introductions in `README.md` and deep architecture guides in `docs/`.",
            "",
            "## Setup & Build",
            *[f"- `{c}`" for c in setup_cmds],
            "",
            "## Testing & Validation",
            "- Always run the relevant checks below before reporting work complete:",
            *[f"  - `{c}`" for c in test_cmds],
            "",
            "## Code & Modification Conventions",
            "- Read target code and surrounding scope before editing; keep functions small and single-purpose.",
            "- Never hardcode personal absolute paths, secrets, tokens, or credentials.",
            "- Update `README.md` or `docs/` whenever CLI flags, public interfaces, or directory layouts change.",
            "",
            "## Safety Boundaries",
            "- Never commit `.env`, private keys, tokens, or `CLAUDE.local.md`.",
            "- Never force-push (`git push --force` / `-f`) or push release tags (`v*`) without explicit approval.",
            "",
        ]
        agents_dest.write_text("\n".join(lines), encoding="utf-8")
        created.append(agents_dest)

    if claude_bridge:
        claude_dest = root / "CLAUDE.md"
        if not claude_dest.exists() or force:
            rel_import = agents_rel_path.replace("\\", "/")
            claude_dest.write_text(f"@{rel_import}\n", encoding="utf-8")
            created.append(claude_dest)

    if init_docs:
        arch_dest = root / "docs" / "architecture.md"
        if not arch_dest.exists() or force:
            arch_dest.parent.mkdir(parents=True, exist_ok=True)
            arch_dest.write_text(
                f"# {root.name} Architecture\n\n"
                "Human-readable system overview, design decisions, and operational guides.\n",
                encoding="utf-8",
            )
            created.append(arch_dest)

    return created


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-tool AGENTS.md / CLAUDE.md / docs / README auditor")
    parser.add_argument("--target", default=".", help="Target repository directory (default: .)")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 if any errors are found")
    parser.add_argument("--json", action="store_true", help="Output structured JSON report")
    parser.add_argument("--init-agents", action="store_true", help="Generate AGENTS.md from detected project structure")
    parser.add_argument("--agents-path", default="AGENTS.md", help="Relative path for generated AGENTS.md")
    parser.add_argument("--claude-bridge", action="store_true", help="Also generate CLAUDE.md importing @AGENTS.md")
    parser.add_argument("--init-docs", action="store_true", help="Also create docs/architecture.md starter")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scaffolded files")
    args = parser.parse_args(argv)

    target = Path(args.target).resolve()
    if args.init_agents or args.claude_bridge or args.init_docs:
        created = scaffold_agents_md(
            target,
            agents_rel_path=args.agents_path,
            claude_bridge=args.claude_bridge,
            init_docs=args.init_docs,
            force=args.force,
        )
        for p in created:
            print(f"✔ Generated: {p}")

    report = audit_project(target)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"=== Docs & Agent Instructions Audit: {report['target']} ===")
        print(f"Agent files : {', '.join(report['agent_files']) or '(none)'}")
        print(f"Human docs  : {', '.join(report['docs_files']) or '(none)'}")
        print(f"README.md   : {'present' if report['has_readme'] else 'MISSING'}")
        for err in report["errors"]:
            print(f"[ERROR] {err}")
        for warn in report["warnings"]:
            print(f"[WARN]  {warn}")
        if report["passed"]:
            print("✔ Audit passed.")

    if args.strict and not report["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
