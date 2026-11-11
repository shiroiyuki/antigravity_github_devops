#!/usr/bin/env python3
"""
GitHub Release Helper
提供開源 Release 自動化輔助功能：
1. notes: 動態抓取 Git Commits 並生成 Markdown 變更日誌。
2. hash: 計算發布壓縮檔之 SHA256 並生成相容 `sha256sum -c` 的校驗檔。
3. tag: 安全建立與驗證 Git 版本標籤。
"""

import sys
import os
import argparse
import subprocess
import hashlib
from pathlib import Path


def get_git_commits(from_ref: str = None, to_ref: str = "HEAD", cwd: str = None) -> list[dict]:
    """獲取兩個 ref 之間的 commit 列表（排除 merge commits）"""
    target_cwd = cwd or os.getcwd()
    
    # 若未指定 from_ref，自動偵測前一個 tag
    if not from_ref:
        res = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0", f"{to_ref}^"],
            cwd=target_cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            from_ref = res.stdout.strip()

    git_range = f"{from_ref}..{to_ref}" if from_ref else to_ref
    
    cmd = ["git", "log", "--no-merges", "--pretty=format:%h%x09%s%x09%an", git_range]
    res = subprocess.run(cmd, cwd=target_cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        return []

    commits = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            short_hash = parts[0]
            subject = parts[1]
            author = parts[2] if len(parts) > 2 else ""
            commits.append({"hash": short_hash, "subject": subject, "author": author})
    return commits


def generate_release_notes(from_ref: str = None, to_ref: str = "HEAD", cwd: str = None) -> str:
    """生成 Markdown 格式的變更日誌"""
    commits = get_git_commits(from_ref, to_ref, cwd)
    if not commits:
        return "## What's Changed\n\n* No functional changes detected.\n"

    lines = ["## What's Changed\n"]
    for c in commits:
        lines.append(f"* {c['subject']} ({c['hash']})")
    lines.append("")
    return "\n".join(lines)


def calculate_sha256(filepath: Path) -> str:
    """計算指定檔案的 SHA256 雜湊值"""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_sha256_file(filepath: Path, output_path: Path = None) -> Path:
    """生成符合 sha256sum -c 規範的校驗檔案（<hash>  <filename>）"""
    if not filepath.exists():
        raise FileNotFoundError(f"檔案不存在: {filepath}")

    sha256_hash = calculate_sha256(filepath)
    target_out = output_path or filepath.with_name(f"{filepath.name}.sha256")
    
    # 遵循 sha256sum 規範：使用檔案 basename，雙空格分隔
    content = f"{sha256_hash}  {filepath.name}\n"
    target_out.write_text(content, encoding="utf-8")
    return target_out


def create_git_tag(tag_name: str, message: str = "", push: bool = False, allow_dirty: bool = False, cwd: str = None) -> bool:
    """建立並可選推送 Git 標籤"""
    target_cwd = cwd or os.getcwd()

    # 1. 檢查 working tree 是否 dirty
    if not allow_dirty:
        res = subprocess.run(["git", "status", "--porcelain"], cwd=target_cwd, stdout=subprocess.PIPE, text=True)
        if res.stdout.strip():
            sys.stderr.write("錯誤: 工作區存在未提交的變更，請先提交或 stash，或使用 --allow-dirty。\n")
            return False

    # 2. 檢查 tag 是否已存在
    res = subprocess.run(["git", "tag", "-l", tag_name], cwd=target_cwd, stdout=subprocess.PIPE, text=True)
    if res.stdout.strip():
        sys.stderr.write(f"錯誤: 標籤 `{tag_name}` 已經存在！\n")
        return False

    # 3. 建立 tag
    tag_msg = message or f"Release {tag_name}"
    res = subprocess.run(["git", "tag", "-a", tag_name, "-m", tag_msg], cwd=target_cwd)
    if res.returncode != 0:
        sys.stderr.write(f"建立標籤 `{tag_name}` 失敗。\n")
        return False

    print(f"成功建立標籤: {tag_name}")

    # 4. 推送 tag
    if push:
        res = subprocess.run(["git", "push", "origin", tag_name], cwd=target_cwd)
        if res.returncode != 0:
            sys.stderr.write(f"推送標籤 `{tag_name}` 失敗。\n")
            return False
        print(f"成功推送標籤: {tag_name} -> origin")

    return True


def main():
    parser = argparse.ArgumentParser(description="GitHub Release Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. notes 子命令
    p_notes = subparsers.add_parser("notes", help="生成 Release Notes")
    p_notes.add_argument("--from-ref", help="起始 ref 或 tag")
    p_notes.add_argument("--to-ref", default="HEAD", help="結束 ref 或 tag (預設 HEAD)")
    p_notes.add_argument("--cwd", help="Git 倉庫工作目錄")
    p_notes.add_argument("-o", "--output", help="輸出檔案路徑 (若未指定則輸出至 stdout)")

    # 2. hash 子命令
    p_hash = subparsers.add_parser("hash", help="計算 SHA256 並生成校驗檔")
    p_hash.add_argument("file", help="目標檔案路徑")
    p_hash.add_argument("-o", "--output", help="校驗檔輸出路徑 (預設 <file>.sha256)")

    # 3. tag 子命令
    p_tag = subparsers.add_parser("tag", help="建立與推送 Git Tag")
    p_tag.add_argument("tag_name", help="標籤名稱 (如 v1.0.0)")
    p_tag.add_argument("-m", "--message", help="標籤說明訊息")
    p_tag.add_argument("--push", action="store_true", help="建立後自動推送到遠端 origin")
    p_tag.add_argument("--allow-dirty", action="store_true", help="允許工作區存在未提交變更")
    p_tag.add_argument("--cwd", help="Git 倉庫工作目錄")

    args = parser.parse_args()

    if args.command == "notes":
        content = generate_release_notes(args.from_ref, args.to_ref, args.cwd)
        if args.output:
            Path(args.output).write_text(content, encoding="utf-8")
            print(f"Release notes 已寫入: {args.output}")
        else:
            sys.stdout.write(content)

    elif args.command == "hash":
        target = Path(args.file).resolve()
        out = Path(args.output).resolve() if args.output else None
        res_file = generate_sha256_file(target, out)
        print(f"SHA256 校驗檔已生成: {res_file}")

    elif args.command == "tag":
        success = create_git_tag(args.tag_name, args.message, args.push, args.allow_dirty, args.cwd)
        if not success:
            sys.exit(1)


if __name__ == "__main__":
    main()
