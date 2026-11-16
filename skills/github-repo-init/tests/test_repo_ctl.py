#!/usr/bin/env python3
"""
Unit tests for github-repo-init
"""

import unittest
import tempfile
import os
import shutil
import subprocess
from pathlib import Path

# 動態加載 repo_ctl
import importlib.util
SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "repo_ctl.py"
spec = importlib.util.spec_from_file_location("repo_ctl", SCRIPT_PATH)
repo_ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repo_ctl)


class TestRepoCtl(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_get_github_token_env(self):
        old_token = os.environ.get("GITHUB_TOKEN")
        try:
            os.environ["GITHUB_TOKEN"] = "test_env_token_123"
            token, user = repo_ctl.get_github_token()
            self.assertEqual(token, "test_env_token_123")
        finally:
            if old_token is not None:
                os.environ["GITHUB_TOKEN"] = old_token
            else:
                os.environ.pop("GITHUB_TOKEN", None)

    def test_get_github_token_hosts_file_xdg(self):
        old_token = os.environ.pop("GITHUB_TOKEN", None)
        old_gh_config = os.environ.get("GH_CONFIG_DIR")
        old_xdg = os.environ.get("XDG_CONFIG_HOME")
        try:
            # 測試 GH_CONFIG_DIR
            custom_gh_dir = self.test_path / "custom_gh"
            custom_gh_dir.mkdir()
            hosts_file = custom_gh_dir / "hosts.yml"
            hosts_file.write_text("github.com:\n  user: testuser\n  oauth_token: gho_test_custom_token\n", encoding="utf-8")
            
            os.environ["GH_CONFIG_DIR"] = str(custom_gh_dir)
            token, user = repo_ctl.get_github_token()
            self.assertEqual(token, "gho_test_custom_token")
            self.assertEqual(user, "testuser")

            # 測試 XDG_CONFIG_HOME
            os.environ.pop("GH_CONFIG_DIR", None)
            xdg_dir = self.test_path / "xdg"
            (xdg_dir / "gh").mkdir(parents=True)
            (xdg_dir / "gh" / "hosts.yml").write_text("github.com:\n  user: xdguser\n  oauth_token: gho_xdg_token\n", encoding="utf-8")
            os.environ["XDG_CONFIG_HOME"] = str(xdg_dir)
            token, user = repo_ctl.get_github_token()
            self.assertEqual(token, "gho_xdg_token")
            self.assertEqual(user, "xdguser")
        finally:
            if old_token is not None:
                os.environ["GITHUB_TOKEN"] = old_token
            if old_gh_config is not None:
                os.environ["GH_CONFIG_DIR"] = old_gh_config
            else:
                os.environ.pop("GH_CONFIG_DIR", None)
            if old_xdg is not None:
                os.environ["XDG_CONFIG_HOME"] = old_xdg
            else:
                os.environ.pop("XDG_CONFIG_HOME", None)

    def test_init_local_git_repo(self):
        # 測試在空目錄初始化 git
        repo_ctl.init_local_repo(self.test_path)
        git_dir = self.test_path / ".git"
        self.assertTrue(git_dir.is_dir())
        gi = self.test_path / ".gitignore"
        self.assertTrue(gi.is_file())
        self.assertIn(".env", gi.read_text(encoding="utf-8"))

        # 自訂 .gitignore 後再次執行不覆蓋
        gi.write_text("# custom\n", encoding="utf-8")
        repo_ctl.init_local_repo(self.test_path)
        self.assertTrue(git_dir.is_dir())
        self.assertEqual(gi.read_text(encoding="utf-8"), "# custom\n")

    def test_setup_remote_origin(self):
        repo_ctl.init_local_repo(self.test_path)
        remote_url = "https://github.com/example/test_repo.git"
        
        # 初次綁定
        repo_ctl.setup_remote_origin(self.test_path, remote_url)
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=self.test_dir, stdout=subprocess.PIPE, text=True)
        self.assertEqual(res.stdout.strip(), remote_url)

        # 覆蓋已存在的 remote
        new_url = "https://github.com/example/new_repo.git"
        repo_ctl.setup_remote_origin(self.test_path, new_url)
        res = subprocess.run(["git", "remote", "get-url", "origin"], cwd=self.test_dir, stdout=subprocess.PIPE, text=True)
        self.assertEqual(res.stdout.strip(), new_url)

    def test_update_visibility_cache_env(self):
        import json
        cache_file = self.test_path / "cache" / "visibility.json"
        old_cache = os.environ.get("ANTIGRAVITY_DEVOPS_CACHE")
        try:
            os.environ["ANTIGRAVITY_DEVOPS_CACHE"] = str(cache_file)
            repo_ctl.update_visibility_cache({"owner/pub": {"name": "pub", "private": False}})
            repo_ctl.update_visibility_cache({"owner/priv": {"name": "priv", "private": True}})
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            self.assertFalse(data["repos"]["owner/pub"]["private"])
            self.assertTrue(data["repos"]["owner/priv"]["private"])
        finally:
            if old_cache is not None:
                os.environ["ANTIGRAVITY_DEVOPS_CACHE"] = old_cache
            else:
                os.environ.pop("ANTIGRAVITY_DEVOPS_CACHE", None)


if __name__ == "__main__":
    unittest.main()
