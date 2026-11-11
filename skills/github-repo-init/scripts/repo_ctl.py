#!/usr/bin/env python3
"""
GitHub Repo Controller
直連 GitHub REST API 建立倉庫並綁定本地 origin。
"""

import sys
import os
import argparse
import subprocess
import json
import urllib.request
import urllib.error
from pathlib import Path


def get_github_token() -> tuple[str, str]:
    """獲取 GitHub Token 與 Username"""
    # 1. 優先環境變數
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token, ""

    # 2. 讀取 ~/.config/gh/hosts.yml
    hosts_file = Path.home() / ".config" / "gh" / "hosts.yml"
    if hosts_file.exists():
        try:
            content = hosts_file.read_text(encoding="utf-8")
            token_match = None
            user_match = None
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("oauth_token:"):
                    token_match = line.split(":", 1)[1].strip()
                elif line.startswith("user:"):
                    user_match = line.split(":", 1)[1].strip()
            if token_match:
                return token_match, user_match or ""
        except Exception:
            pass

    return "", ""


def get_current_user(token: str) -> str:
    """透過 API 取得當前使用者名稱"""
    req = urllib.request.Request(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "antigravity-devops-toolkit"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
            return data.get("login", "")
    except Exception as e:
        sys.stderr.write(f"獲取使用者資訊失敗: {e}\n")
        return ""


def create_github_repo(token: str, name: str, description: str = "", private: bool = False) -> dict:
    """呼叫 GitHub REST API 建立遠端倉庫"""
    url = "https://api.github.com/user/repos"
    payload = {
        "name": name,
        "description": description,
        "private": private,
        "auto_init": False
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "antigravity-devops-toolkit"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if e.code == 422 and "name already exists" in err_body:
            # 倉庫已存在
            return {"already_exists": True}
        sys.stderr.write(f"建立遠端倉庫失敗 (HTTP {e.code}): {err_body}\n")
        return {}
    except Exception as e:
        sys.stderr.write(f"網路連線異常: {e}\n")
        return {}


def setup_remote_origin(repo_dir: Path, clone_url: str):
    """關聯或更新 remote origin"""
    res = subprocess.run(["git", "remote"], cwd=str(repo_dir), stdout=subprocess.PIPE, text=True)
    remotes = res.stdout.splitlines()

    if "origin" in remotes:
        subprocess.run(["git", "remote", "set-url", "origin", clone_url], cwd=str(repo_dir), check=True)
        print(f"✔ 已更新 remote 'origin' -> {clone_url}")
    else:
        subprocess.run(["git", "remote", "add", "origin", clone_url], cwd=str(repo_dir), check=True)
        print(f"✔ 已新增 remote 'origin' -> {clone_url}")


def init_local_repo(repo_dir: Path, clone_url: str = ""):
    """初始化本地 git 並可選關聯 origin"""
    # 1. git init (若無)
    if not (repo_dir / ".git").is_dir():
        subprocess.run(["git", "init", "-b", "main"], cwd=str(repo_dir), check=True)
        print("✔ 本地目錄已初始化為 Git 倉庫 (main 分支)")

    # 2. 檢查 remote
    if clone_url:
        setup_remote_origin(repo_dir, clone_url)


def main():
    parser = argparse.ArgumentParser(description="GitHub 倉庫初始化與遠端綁定工具")
    parser.add_argument("--name", help="倉庫名稱（預設為當前目錄名）")
    parser.add_argument("--desc", default="", help="倉庫描述")
    parser.add_argument("--private", action="store_true", help="設為私有倉庫（預設公開）")
    parser.add_argument("--dir", default=".", help="目標工作區目錄")
    parser.add_argument("--dry-run", action="store_true", help="預檢模式，不實際呼叫 API")

    args = parser.parse_args()
    target_dir = Path(args.dir).resolve()

    repo_name = args.name or target_dir.name
    print(f"=== GitHub 倉庫初始化: {repo_name} ===")

    token, user = get_github_token()
    if not token:
        sys.stderr.write("錯誤: 未能檢測到有效的 GitHub Token。請先登入 gh 或配置環境變數 GITHUB_TOKEN。\n")
        sys.exit(1)

    if not user:
        user = get_current_user(token)
    if not user:
        sys.stderr.write("錯誤: 無法確認使用者身份，請檢查 Token 權限。\n")
        sys.exit(1)

    print(f"使用者: {user} | 倉庫目標: {user}/{repo_name}")

    clone_url = f"https://github.com/{user}/{repo_name}.git"

    if args.dry_run:
        print(f"[Dry-run] 將建立遠端倉庫: {clone_url} (private={args.private})")
        print(f"[Dry-run] 將初始化本地目錄: {target_dir} 並關聯 origin")
        return

    # 1. 建立遠端倉庫
    res = create_github_repo(token, repo_name, args.desc, args.private)
    if res.get("already_exists"):
        print(f"ℹ 遠端倉庫 `{user}/{repo_name}` 已經存在，繼續進行本地關聯。")
    elif not res.get("id"):
        sys.stderr.write("中斷: 遠端倉庫建立失敗。\n")
        sys.exit(1)
    else:
        print(f"✔ 成功建立遠端倉庫: {res.get('html_url')}")

    # 2. 本地初始化與 remote 關聯
    init_local_repo(target_dir, clone_url)
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
