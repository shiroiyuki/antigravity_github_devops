#!/usr/bin/env python3
"""
Unit tests for Antigravity DevOps Guard Hook (hooks/devops_guard.py)
"""

import unittest
import tempfile
import os
import sys
import json
import subprocess
from pathlib import Path

# Add hooks directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
import devops_guard


class TestDevopsGuard(unittest.TestCase):

    def test_force_push_detection(self):
        # 應攔截
        self.assertTrue(bool(devops_guard.check_force_push("git push --force origin main")))
        self.assertTrue(bool(devops_guard.check_force_push("git push -f origin main")))
        self.assertTrue(bool(devops_guard.check_force_push("git push origin main --force-with-lease")))
        # 不應攔截
        self.assertEqual(devops_guard.check_force_push("git push origin main"), "")
        self.assertEqual(devops_guard.check_force_push("git push -u origin main"), "")
        self.assertEqual(devops_guard.check_force_push("git status"), "")

    def test_secret_leak_sensitive_filename(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            # 初始化 git repo
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # 建立敏感檔案
            env_file = tmp_path / ".env"
            env_file.write_text("API_KEY=12345\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            reason = devops_guard.check_secret_leak("git commit -m 'add env'", tmp_dir)
            self.assertTrue("敏感機密檔案" in reason)

    def test_secret_leak_token_in_content(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            subprocess.run(["git", "init"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            code_file = tmp_path / "config.py"
            # 寫入洩漏的 GitHub OAuth token
            code_file.write_text("GITHUB_TOKEN = 'gho_1234567890abcdef1234567890abcdef'\n", encoding="utf-8")
            subprocess.run(["git", "add", "config.py"], cwd=tmp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            reason = devops_guard.check_secret_leak("git commit -m 'leak token'", tmp_dir)
            self.assertTrue("敏感金鑰" in reason)

    def test_pre_push_failing_tests_blocked(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_dir = tmp_path / "tests"
            test_dir.mkdir()
            bad_test = test_dir / "test_broken.py"
            bad_test.write_text(
                "import unittest\n"
                "class BrokenTest(unittest.TestCase):\n"
                "    def test_fail(self):\n"
                "        self.assertEqual(1, 2)\n",
                encoding="utf-8"
            )

            reason = devops_guard.check_pre_push_tests("git push origin main", tmp_dir)
            self.assertTrue("本地單元測試未全數通過" in reason)

    def test_pre_push_passing_tests_allowed(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            test_dir = tmp_path / "tests"
            test_dir.mkdir()
            good_test = test_dir / "test_ok.py"
            good_test.write_text(
                "import unittest\n"
                "class OkTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(1, 1)\n",
                encoding="utf-8"
            )

            reason = devops_guard.check_pre_push_tests("git push origin main", tmp_dir)
            self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()
