#!/usr/bin/env python3
"""
Unit tests for github-release-manager
"""

import unittest
import tempfile
import os
import shutil
import subprocess
from pathlib import Path

# 動態加載 release_helper
import importlib.util
HELPER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "release_helper.py"
spec = importlib.util.spec_from_file_location("release_helper", HELPER_PATH)
release_helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_helper)


class TestReleaseHelper(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_calculate_sha256_and_generate_file(self):
        sample_file = self.test_path / "package.tar.gz"
        sample_file.write_bytes(b"Hello Antigravity DevOps!")

        # 預期 hash
        import hashlib
        expected_hash = hashlib.sha256(b"Hello Antigravity DevOps!").hexdigest()

        calc_hash = release_helper.calculate_sha256(sample_file)
        self.assertEqual(calc_hash, expected_hash)

        sha_file = release_helper.generate_sha256_file(sample_file)
        self.assertTrue(sha_file.exists())
        self.assertEqual(sha_file.name, "package.tar.gz.sha256")

        content = sha_file.read_text(encoding="utf-8")
        self.assertEqual(content, f"{expected_hash}  package.tar.gz\n")

    def test_generate_release_notes_empty_repo(self):
        # 測試在無 git commit 的目錄中回退
        notes = release_helper.generate_release_notes(cwd=str(self.test_path))
        self.assertIn("## What's Changed", notes)
        self.assertIn("No functional changes detected", notes)

    def test_git_tag_lifecycle(self):
        # 初始化臨時 git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=self.test_dir, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.name", "Tester"], cwd=self.test_dir)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir)

        # 建立初次提交
        test_file = self.test_path / "README.md"
        test_file.write_text("# Test Repo", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.test_dir)
        subprocess.run(["git", "commit", "-m", "feat: initial commit"], cwd=self.test_dir, stdout=subprocess.DEVNULL)

        # 1. 成功建立 tag
        success = release_helper.create_git_tag("v1.0.0", message="First release", cwd=self.test_dir)
        self.assertTrue(success)

        # 2. 重複建立相同 tag 應失敗
        success_dup = release_helper.create_git_tag("v1.0.0", cwd=self.test_dir)
        self.assertFalse(success_dup)

        # 3. 測試 notes 提取
        notes = release_helper.generate_release_notes(cwd=self.test_dir)
        self.assertIn("feat: initial commit", notes)


if __name__ == "__main__":
    unittest.main()
