#!/usr/bin/env python3
"""
Antigravity DevOps PreToolUse Guard
底層生命週期防線：
1. 嚴禁 git force push（--force / -f）破壞遠端歷史。
2. 嚴禁提交敏感金鑰、Token 與機密檔案（.env, hosts.yml, 私鑰）。
3. 嚴格落實 Pre-push 測試守門（單元測試未全綠前硬性阻斷 push）。
"""

import sys
import json
import re
import os
import subprocess
from pathlib import Path


SENSITIVE_FILENAME_PATTERNS = [
    r"^\.env(\..+)?$",
    r".*hosts\.ya?ml$",
    r".*secret.*",
    r".*credential.*",
    r".*id_rsa.*",
    r".*\.pem$",
    r".*\.key$",
]

SENSITIVE_CONTENT_PATTERNS = [
    r"gho_[A-Za-z0-9_]{30,}",
    r"ghp_[A-Za-z0-9_]{30,}",
    r"github_pat_[A-Za-z0-9_]{30,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
]


def check_force_push(cmd: str) -> str:
    """檢查是否為危險的 Force Push 操作"""
    if re.search(r"\bgit\s+push\b", cmd):
        if re.search(r"(?:^|\s)(?:-f|--force|--force-with-lease)(?:$|\s)", cmd):
            return "【安全攔截】嚴禁使用 Force Push（--force / -f）！此操作會破壞遠端歷史，請使用常規 merge 或 rebase。"
    return ""


def check_secret_leak(cmd: str, cwd: str) -> str:
    """檢查 git commit 時暫存區是否包含金鑰或敏感檔案"""
    if not re.search(r"\bgit\s+commit\b", cmd):
        return ""

    try:
        # 1. 檢查暫存檔名
        res_files = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if res_files.returncode == 0:
            for f in res_files.stdout.splitlines():
                f_name = Path(f.strip()).name
                for pattern in SENSITIVE_FILENAME_PATTERNS:
                    if re.match(pattern, f_name, re.IGNORECASE):
                        return f"【安全攔截】暫存區即將提交敏感機密檔案: `{f}`！已強制阻斷提交。請先執行 git reset HEAD <file> 移除該檔案。"

        # 2. 檢查暫存內容中的 Token / 私鑰
        res_diff = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5
        )
        if res_diff.returncode == 0:
            diff_text = res_diff.stdout
            for pattern in SENSITIVE_CONTENT_PATTERNS:
                if re.search(pattern, diff_text):
                    return "【安全攔截】暫存區內容包含敏感金鑰（GitHub Token 或私鑰標頭）！已強制阻斷提交，防止機密洩漏至遠端倉庫。"
    except Exception:
        # 外部查詢異常不阻礙常規提交
        pass

    return ""


def check_pre_push_tests(cmd: str, cwd: str) -> str:
    """檢查 git push 時本地單元測試是否通過"""
    if not re.search(r"\bgit\s+push\b", cmd):
        return ""

    # 排除 dry-run 測試
    if "--dry-run" in cmd:
        return ""

    cwd_path = Path(cwd)
    # 偵測是否有測試目錄
    test_dir = None
    if (cwd_path / "tests").is_dir():
        test_dir = "tests"
    elif (cwd_path / "test").is_dir():
        test_dir = "test"

    if not test_dir:
        return ""

    # 解析可用的 Python 直譯器（同源直譯器優先，防禦性回退系統 python3）
    py_exec = sys.executable or "python3"

    try:
        res = subprocess.run(
            [py_exec, "-m", "unittest", "discover", test_dir],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )
        if res.returncode != 0:
            # 擷取失敗輸出前 5 行精華
            err_output = res.stderr or res.stdout
            lines = [line.strip() for line in err_output.splitlines() if line.strip()][:5]
            summary = "\n".join(lines)
            return (
                f"【品質攔截】本地單元測試未全數通過，底層強制阻斷 git push！\n"
                f"請先修復單元測試代碼再推送。\n"
                f"測試報錯摘要:\n{summary}"
            )
    except subprocess.TimeoutExpired:
        return "【品質攔截】本地單元測試執行超時（超過 15 秒），已阻斷 git push。請確認測試套件未發生死鎖。"
    except Exception:
        pass

    return ""


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.stdout.write(json.dumps({"decision": "allow"}))
            return

        payload = json.loads(input_data)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})
        cmd = args.get("CommandLine", "")
        cwd = payload.get("cwd", os.getcwd())

        # 僅對 run_command 進行檢測
        if tool_name != "run_command" or not cmd:
            sys.stdout.write(json.dumps({"decision": "allow"}))
            return

        # 1. Force push 檢測
        reason = check_force_push(cmd)
        if reason:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}))
            return

        # 2. 金鑰與機密洩漏檢測
        reason = check_secret_leak(cmd, cwd)
        if reason:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}))
            return

        # 3. Pre-push 單元測試守門
        reason = check_pre_push_tests(cmd, cwd)
        if reason:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}))
            return

        sys.stdout.write(json.dumps({"decision": "allow"}))
    except Exception as e:
        # 異常情況下容錯放行，避免阻礙主進程
        sys.stdout.write(json.dumps({"decision": "allow", "reason": f"Guard error: {e}"}))


if __name__ == "__main__":
    main()
