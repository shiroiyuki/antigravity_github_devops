#!/usr/bin/env python3
"""Unit tests for github-docs-guard (doc_audit.py)."""

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "doc_audit.py"
spec = importlib.util.spec_from_file_location("doc_audit", SCRIPT_PATH)
doc_audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doc_audit)


class TestDocAudit(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_valid_cross_tool_repo_passes(self):
        (self.test_dir / "README.md").write_text("# Demo\n\nSee [Architecture](docs/architecture.md).\n", encoding="utf-8")
        (self.test_dir / "AGENTS.md").write_text("# Agents\n\n- Run `pytest`\n", encoding="utf-8")
        (self.test_dir / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
        (self.test_dir / "docs").mkdir()
        (self.test_dir / "docs" / "architecture.md").write_text("# Architecture\n", encoding="utf-8")

        report = doc_audit.audit_project(self.test_dir)
        self.assertTrue(report["passed"])
        self.assertEqual(report["errors"], [])
        self.assertIn("AGENTS.md", report["agent_files"])
        self.assertIn("CLAUDE.md", report["agent_files"])
        self.assertEqual(report["docs_files"], ["docs/architecture.md"])

    def test_detects_casing_typo_frontmatter_and_broken_links(self):
        (self.test_dir / ".agent").mkdir()
        (self.test_dir / ".agent" / "Agents.md").write_text("# Bad casing\n", encoding="utf-8")
        (self.test_dir / "AGENTS.md").write_text("---\ntrigger: always_on\n---\n# Bad frontmatter\n", encoding="utf-8")
        (self.test_dir / "README.md").write_text(
            "# Demo\n\nClone `https://github.com/<your-username>/demo.git`.\nSee [Missing](docs/missing.md).\n",
            encoding="utf-8",
        )

        report = doc_audit.audit_project(self.test_dir)
        self.assertFalse(report["passed"])
        joined = "\n".join(report["errors"])
        self.assertIn("non-standard casing", joined)
        self.assertIn("YAML frontmatter", joined)
        self.assertIn("<your-username>", joined)
        self.assertIn("docs/missing.md", joined)
        self.assertTrue(any(".agent/" in w and "legacy" in w for w in report["warnings"]))

    def test_cli_metavariable_repo_name_allowed_while_url_placeholder_caught(self):
        (self.test_dir / "README.md").write_text(
            "# Demo\n\n```bash\nrepo_ctl.py --name <repo-name>\n```\n",
            encoding="utf-8",
        )
        (self.test_dir / "AGENTS.md").write_text("# Agents\n\n- Run `pytest`\n", encoding="utf-8")
        self.assertTrue(doc_audit.audit_project(self.test_dir)["passed"])

        (self.test_dir / "README.md").write_text(
            "# Demo\n\nhttps://github.com/shiroiyuki/<repo-name>\n",
            encoding="utf-8",
        )
        self.assertFalse(doc_audit.audit_project(self.test_dir)["passed"])

    def test_plugin_root_agents_md_rejected(self):
        (self.test_dir / "plugin.json").write_text('{"name": "demo"}', encoding="utf-8")
        (self.test_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.test_dir / "AGENTS.md").write_text("# Wrong place for plugin\n", encoding="utf-8")

        report = doc_audit.audit_project(self.test_dir)
        self.assertFalse(report["passed"])
        self.assertTrue(any("plugin root" in e for e in report["errors"]))

    def test_claude_local_gitignore_warning_and_size_limit(self):
        (self.test_dir / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.test_dir / "CLAUDE.local.md").write_text("private notes\n", encoding="utf-8")
        (self.test_dir / "AGENTS.md").write_text("x" * 24050, encoding="utf-8")

        report = doc_audit.audit_project(self.test_dir)
        self.assertFalse(report["passed"])
        self.assertTrue(any("24000-byte" in e for e in report["errors"]))
        self.assertTrue(any("CLAUDE.local.md" in w for w in report["warnings"]))

    def test_scaffold_agents_claude_bridge_and_docs(self):
        (self.test_dir / "README.md").write_text("# Demo\n\nDocs: [Arch](docs/architecture.md)\n", encoding="utf-8")
        (self.test_dir / "tests").mkdir()

        created = doc_audit.scaffold_agents_md(
            self.test_dir,
            agents_rel_path="AGENTS.md",
            claude_bridge=True,
            init_docs=True,
        )
        self.assertEqual(len(created), 3)
        self.assertIn("python3 -m unittest discover -s tests -v", (self.test_dir / "AGENTS.md").read_text(encoding="utf-8"))
        self.assertEqual((self.test_dir / "CLAUDE.md").read_text(encoding="utf-8").strip(), "@AGENTS.md")

        report = doc_audit.audit_project(self.test_dir)
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
