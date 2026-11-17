#!/usr/bin/env python3
"""
Unit tests for Antigravity DevOps Guard Hook (hooks/devops_guard.py)
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import devops_guard


class TestDevopsGuard(unittest.TestCase):

    def test_force_push_detection(self):
        self.assertTrue(bool(devops_guard.check_force_push("git push --force origin main")))
        self.assertTrue(bool(devops_guard.check_force_push("git -C sub push -f origin main")))
        self.assertTrue(bool(devops_guard.check_force_push("git push origin main --force-with-lease")))
        self.assertEqual(devops_guard.check_force_push("git push origin main"), "")
        self.assertEqual(devops_guard.check_force_push("git push -u origin main"), "")
        self.assertEqual(devops_guard.check_force_push("git status"), "")

    def test_secret_leak_sensitive_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            env_file = tmp_path / ".env"
            env_file.write_text("API_KEY=12345\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            reason = devops_guard.check_secret_leak("git commit -m 'add env'", tmp_dir)
            self.assertIn("敏感機密檔案", reason)

    def test_secret_leak_token_in_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            code_file = tmp_path / "config.py"
            code_file.write_text("GITHUB_TOKEN = 'gho_1234567890abcdef1234567890abcdef'\n", encoding="utf-8")
            subprocess.run(["git", "add", "config.py"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_secret_leak("git commit -m 'leak token'", tmp_dir)
            self.assertEqual(decision, "deny")
            self.assertIn("敏感金鑰", reason)

    def test_secret_leak_google_api_key_and_db_uri(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            f = tmp_path / "app.py"
            f.write_text("DB = 'postgres://admin:SuperPass123@db.host:5432/prod'  # devops-guard: ignore\n", encoding="utf-8")  # devops-guard: ignore
            subprocess.run(["git", "add", "app.py"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_secret_leak("git commit -m 'db'", tmp_dir)
            self.assertEqual(decision, "deny")
            self.assertIn("含帳密資料庫連線字串", reason)

    def test_resolve_git_dash_c_subrepo(self):
        with tempfile.TemporaryDirectory() as parent_dir:
            sub = Path(parent_dir) / "subrepo"
            sub.mkdir()
            subprocess.run(["git", "init"], cwd=str(sub), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (sub / ".env").write_text("SECRET=1\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=str(sub), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_secret_leak(
                "git -C subrepo commit -m 'test'",
                parent_dir,
            )
            self.assertEqual(decision, "deny")
            self.assertIn("敏感機密檔案", reason)

    def test_public_repo_warns_on_private_repo_name_and_custom_terms(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            repo_dir = tmp_path / "my-public-repo"
            repo_dir.mkdir()
            subprocess.run(["git", "init"], cwd=str(repo_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/owner/my-public-repo.git"],
                cwd=str(repo_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            (repo_dir / "README.md").write_text("Related: my-secret-private-repo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=str(repo_dir), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            cache_file = tmp_path / "vis.json"
            cache_file.write_text(
                json.dumps({
                    "repos": {
                        "owner/my-public-repo": {"name": "my-public-repo", "private": False},
                        "owner/my-secret-private-repo": {"name": "my-secret-private-repo", "private": True},
                    }
                }),
                encoding="utf-8",
            )
            terms_file = tmp_path / "terms.txt"
            terms_file.write_text("# comment\ninternal-codename-xyz\n", encoding="utf-8")

            old_cache = os.environ.get("ANTIGRAVITY_DEVOPS_CACHE")
            old_terms = os.environ.get("ANTIGRAVITY_SENSITIVE_TERMS_FILE")
            try:
                os.environ["ANTIGRAVITY_DEVOPS_CACHE"] = str(cache_file)
                os.environ["ANTIGRAVITY_SENSITIVE_TERMS_FILE"] = str(terms_file)

                decision, reason = devops_guard.evaluate_secret_leak("git commit -m 'docs'", str(repo_dir))
                self.assertEqual(decision, "force_ask")
                self.assertIn("my-secret-private-repo", reason)
            finally:
                if old_cache is not None:
                    os.environ["ANTIGRAVITY_DEVOPS_CACHE"] = old_cache
                else:
                    os.environ.pop("ANTIGRAVITY_DEVOPS_CACHE", None)
                if old_terms is not None:
                    os.environ["ANTIGRAVITY_SENSITIVE_TERMS_FILE"] = old_terms
                else:
                    os.environ.pop("ANTIGRAVITY_SENSITIVE_TERMS_FILE", None)

    def test_high_entropy_assignment_triggers_force_ask(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (tmp_path / "settings.py").write_text(
                'API_KEY = "xK9mP2vQ8nL4rT7wZ1bC6yF3"\n',  # devops-guard: ignore
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "settings.py"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_secret_leak("git commit -m 'cfg'", tmp_dir)
            self.assertEqual(decision, "force_ask")
            self.assertIn("高隨機度密鑰", reason)

    def test_gitignore_weakening_triggers_force_ask(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            gi = tmp_path / ".gitignore"
            gi.write_text(".env\n*.key\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            gi.write_text("*.key\n", encoding="utf-8")
            subprocess.run(["git", "add", ".gitignore"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            decision, reason = devops_guard.evaluate_secret_leak("git commit -m 'weaken gi'", tmp_dir)
            self.assertEqual(decision, "force_ask")
            self.assertIn(".gitignore", reason)

    def test_pre_push_failing_tests_blocked(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_dir = tmp_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_broken.py").write_text(
                "import unittest\n"
                "class BrokenTest(unittest.TestCase):\n"
                "    def test_fail(self):\n"
                "        self.assertEqual(1, 2)\n",
                encoding="utf-8",
            )

            reason = devops_guard.check_pre_push_tests("git push origin main", tmp_dir)
            self.assertIn("本地單元測試未全數通過", reason)

    def test_pre_push_passing_tests_allowed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_dir = tmp_path / "tests"
            test_dir.mkdir()
            (test_dir / "test_ok.py").write_text(
                "import unittest\n"
                "class OkTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8",
            )

            reason = devops_guard.check_pre_push_tests("git push origin main", tmp_dir)
            self.assertEqual(reason, "")

    def test_docs_and_agents_guard_catches_casing_frontmatter_and_local_md(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (tmp_path / ".agent").mkdir()
            (tmp_path / ".agent" / "Agents.md").write_text("---\ntrigger: always_on\n---\n# Bad\n", encoding="utf-8")
            (tmp_path / "CLAUDE.local.md").write_text("local\n", encoding="utf-8")
            subprocess.run(["git", "add", ".agent/Agents.md", "CLAUDE.local.md"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_docs_and_agents_guard("git commit -m 'docs'", tmp_dir)
            self.assertEqual(decision, "force_ask")
            self.assertIn("AGENTS.md", reason)
            self.assertIn("YAML Frontmatter", reason)
            self.assertIn("CLAUDE.local.md", reason)

    def test_docs_sync_reminder_on_structural_push_without_docs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            (tmp_path / "scripts").mkdir()
            (tmp_path / "scripts" / "new_tool.py").write_text("print('hi')\n", encoding="utf-8")
            subprocess.run(["git", "add", "scripts/new_tool.py"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-m", "add tool"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            decision, reason = devops_guard.evaluate_docs_and_agents_guard("git push origin main", tmp_dir)
            self.assertEqual(decision, "force_ask")
            self.assertIn("README.md", reason)


if __name__ == "__main__":
    unittest.main()
