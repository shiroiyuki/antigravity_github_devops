#!/usr/bin/env python3
"""
Antigravity DevOps PreToolUse Guard
底層生命週期防線：
1. 嚴禁 git force push（--force / -f / --force-with-lease）破壞遠端歷史。
2. 嚴禁提交/推送敏感機密檔案、金鑰 Token、含帳密 URI 與個人本機路徑（deny）。
3. 針對 Public 倉庫進行 Private 倉庫名稱、自訂敏感詞與高熵值疑似密碼提醒（force_ask）。
4. 支援解析 git -C / cd 子目錄，嚴格落實 Pre-push 單元測試守門。
"""

import json
import math
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


SENSITIVE_FILENAME_PATTERNS = [
    r"^\.env(\..+)?$",
    r".*hosts\.ya?ml$",
    r".*secret.*",
    r".*credential.*",
    r".*id_rsa.*",
    r".*\.pem$",
    r".*\.key$",
    r"^\.?netrc$",
    r".*\.cookie$",
    r"^cookies\.txt$",
]

SENSITIVE_CONTENT_PATTERNS = [
    (r"gho_[A-Za-z0-9_]{30,}", "GitHub OAuth Token"),
    (r"ghp_[A-Za-z0-9_]{30,}", "GitHub Personal Access Token"),
    (r"github_pat_[A-Za-z0-9_]{30,}", "GitHub Fine-grained PAT"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私鑰標頭"),
    (r"AIzaSy[0-9A-Za-z_-]{33}", "Google API Key"),
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "Anthropic API Key"),
    (r"sk-proj-[A-Za-z0-9_-]{20,}", "OpenAI Project API Key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS Access Key ID"),
    (r"(?:postgres|mysql|mongodb(?:\+srv)?|redis)://[^/\s:@]+:[^/\s@]+@", "含帳密資料庫連線字串"),
    (r"PHPSESSID=[A-Za-z0-9,_-]{16,}", "Pixiv/Web Session Cookie"),
    (r"(?:/home/(?!username\b)[a-zA-Z0-9._-]+/|/Users/(?!username\b)[a-zA-Z0-9._-]+/|C:\\\\Users\\\\(?!username\b)[a-zA-Z0-9._-]+)", "個人絕對路徑"),
]

HIGH_ENTROPY_ASSIGN_RE = re.compile(
    r"""(?i)\b(?:password|passwd|secret|token|api_key|apikey|cookie|private_key)\b\s*[:=]\s*["']([A-Za-z0-9+/=_-]{16,})["']"""
)
PRIVATE_LAN_IP_RE = re.compile(r"\b(?:192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
PLACEHOLDER_WORDS = ("example", "dummy", "placeholder", "your_", "sample", "changeme", "test_")
CRITICAL_GITIGNORE_RULES = (
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
    "hosts.yml",
    "hosts.yaml",
    ".netrc",
    "*.cookie",
    "cookies.txt",
)


def shannon_entropy(text: str) -> float:
    """計算字串香農熵以辨別高隨機度疑似金鑰"""
    if not text:
        return 0.0
    freq: Dict[str, int] = {}
    for ch in text:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(text)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def get_visibility_cache_path() -> Path:
    """動態解析倉庫可見度快取路徑"""
    explicit = os.environ.get("ANTIGRAVITY_DEVOPS_CACHE", "").strip()
    if explicit:
        return Path(os.path.expanduser(explicit))
    xdg_cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(os.path.expanduser(xdg_cache)) if xdg_cache else Path.home() / ".cache"
    return base / "antigravity" / "github_repo_visibility.json"


def get_sensitive_terms_path() -> Path:
    """動態解析個人敏感詞黑名單路徑"""
    explicit = os.environ.get("ANTIGRAVITY_SENSITIVE_TERMS_FILE", "").strip()
    if explicit:
        return Path(os.path.expanduser(explicit))
    xdg_config = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(os.path.expanduser(xdg_config)) if xdg_config else Path.home() / ".config"
    return base / "antigravity" / "sensitive_terms.txt"


def load_visibility_cache() -> Dict[str, dict]:
    """讀取本機倉庫可見度快取（純本地讀取，不連網）"""
    cache_path = get_visibility_cache_path()
    if not cache_path.is_file():
        return {}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        repos = data.get("repos", {})
        return repos if isinstance(repos, dict) else {}
    except Exception:
        return {}


def load_sensitive_terms() -> List[str]:
    """讀取本機自訂敏感詞黑名單"""
    terms_path = get_sensitive_terms_path()
    if not terms_path.is_file():
        return []
    try:
        terms = []
        for line in terms_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                terms.append(stripped)
        return terms
    except Exception:
        return []


def resolve_target_git_root(cmd: str, cwd: str) -> Optional[Path]:
    """從指令中的 git -C / cd 或 cwd 動態解析目標 Git 倉庫根目錄（純本地 Path 檢查）"""
    base_dir = Path(cwd).resolve()
    candidate_dir = base_dir

    # 1. 解析 leading `cd <dir>`
    cd_match = re.match(r"^\s*cd\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))\s*(?:&&|;)", cmd)
    if cd_match:
        raw_cd = cd_match.group(1) or cd_match.group(2) or cd_match.group(3)
        p = Path(os.path.expanduser(raw_cd))
        candidate_dir = p if p.is_absolute() else (base_dir / p)

    # 2. 解析 `git -C <dir>`（優先於 cd）
    try:
        tokens = shlex.split(cmd)
        for idx, tok in enumerate(tokens):
            if tok == "git":
                j = idx + 1
                while j < len(tokens) - 1:
                    if tokens[j] == "-C":
                        p = Path(os.path.expanduser(tokens[j + 1]))
                        candidate_dir = p if p.is_absolute() else (candidate_dir / p)
                        break
                    if tokens[j].startswith("-"):
                        j += 1
                        continue
                    break
                break
    except ValueError:
        c_match = re.search(r"\bgit\s+-C\s+(?:\"([^\"]+)\"|'([^']+)'|(\S+))", cmd)
        if c_match:
            raw_c = c_match.group(1) or c_match.group(2) or c_match.group(3)
            p = Path(os.path.expanduser(raw_c))
            candidate_dir = p if p.is_absolute() else (candidate_dir / p)

    candidate_dir = candidate_dir.resolve()
    for parent in [candidate_dir, *candidate_dir.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def read_github_slug(repo_root: Optional[Path]) -> str:
    """直接從 .git/config 讀取 origin 之 owner/repo 識別碼"""
    if repo_root is None:
        return ""
    git_entry = repo_root / ".git"
    config_file = git_entry / "config" if git_entry.is_dir() else None
    if config_file is None or not config_file.is_file():
        return ""
    try:
        content = config_file.read_text(encoding="utf-8", errors="ignore")
        in_origin = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_origin = stripped == '[remote "origin"]'
                continue
            if in_origin and stripped.startswith("url"):
                url = stripped.split("=", 1)[1].strip()
                m = re.search(r"github\.com[:/]([^/]+/[^/\s]+?)(?:\.git)?$", url)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return ""


def parse_diff_added_lines(diff_text: str) -> List[Tuple[str, str]]:
    """從 git diff 提取新增行及其所屬相對檔案路徑"""
    added: List[Tuple[str, str]] = []
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                current_file = parts[1].strip()
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
        elif line.startswith("+") and not line.startswith("+++"):
            added.append((current_file, line[1:]))
    return added


def parse_diff_removed_lines(diff_text: str) -> List[Tuple[str, str]]:
    """從 git diff 提取刪除行及其所屬相對檔案路徑"""
    removed: List[Tuple[str, str]] = []
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/", 1)
            if len(parts) == 2:
                current_file = parts[1].strip()
        elif line.startswith("+++ b/"):
            current_file = line[6:].strip()
        elif line.startswith("-") and not line.startswith("---"):
            removed.append((current_file, line[1:]))
    return removed


def is_test_filepath(filepath: str) -> bool:
    """判斷是否為測試目錄或單元測試檔案"""
    norm = filepath.replace("\\", "/")
    name = Path(norm).name
    return "/tests/" in f"/{norm}" or "/test/" in f"/{norm}" or name.startswith("test_")


def collect_git_diff(repo_root: Path, is_push: bool) -> Tuple[List[str], str]:
    """收集 commit 暫存區或 push 待推範圍之變更檔名與 diff"""
    if not is_push:
        res_files = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        res_diff = subprocess.run(
            ["git", "diff", "--cached"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        files = res_files.stdout.splitlines() if res_files.returncode == 0 else []
        diff = res_diff.stdout if res_diff.returncode == 0 else ""
        return files, diff

    # Push 模式：優先檢查 @{u}..HEAD，無上游時回退 origin/main..HEAD 或 HEAD 最後一次提交
    diff_range = None
    for candidate in ("@{u}..HEAD", "origin/main..HEAD"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", candidate.split("..")[0]],
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if probe.returncode == 0:
            diff_range = candidate
            break

    if diff_range:
        res_files = subprocess.run(
            ["git", "diff", "--name-only", diff_range],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        res_diff = subprocess.run(
            ["git", "diff", diff_range],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    else:
        res_files = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        res_diff = subprocess.run(
            ["git", "show", "--format=", "HEAD"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )

    files = [f for f in res_files.stdout.splitlines() if f.strip()] if res_files.returncode == 0 else []
    diff = res_diff.stdout if res_diff.returncode == 0 else ""
    return files, diff


def check_force_push(cmd: str) -> str:
    """檢查是否為危險的 Force Push 操作"""
    if re.search(r"\bgit\b.*\bpush\b", cmd):
        if re.search(r"(?:^|\s)(?:-f|--force|--force-with-lease)(?:$|\s)", cmd):
            return "【安全攔截】嚴禁使用 Force Push（--force / -f）！此操作會破壞遠端歷史，請使用常規 merge 或 rebase。"
    return ""


def evaluate_secret_leak(cmd: str, cwd: str) -> Tuple[str, str]:
    """評估 commit / push 是否包含敏感檔案、金鑰或 Public 倉庫洩漏風險，回傳 (decision, reason)"""
    is_commit = bool(re.search(r"\bgit\b.*\bcommit\b", cmd))
    is_push = bool(re.search(r"\bgit\b.*\bpush\b", cmd) and "--dry-run" not in cmd)
    if not is_commit and not is_push:
        return "allow", ""

    repo_root = resolve_target_git_root(cmd, cwd)
    if repo_root is None:
        return "allow", ""

    try:
        changed_files, diff_text = collect_git_diff(repo_root, is_push=is_push)
    except Exception:
        return "allow", ""

    # 1. 敏感檔名硬性阻斷
    for f in changed_files:
        f_name = Path(f.strip()).name
        for pattern in SENSITIVE_FILENAME_PATTERNS:
            if re.match(pattern, f_name, re.IGNORECASE):
                return (
                    "deny",
                    f"【安全攔截】即將提交或推送敏感機密檔案: `{f}`！已強制阻斷。請先移除該檔案並加入 .gitignore。",
                )

    added_lines = parse_diff_added_lines(diff_text)
    removed_lines = parse_diff_removed_lines(diff_text)
    ask_reasons: List[str] = []

    # 1.5 檢查是否從 .gitignore 移除機密保護規則
    for filepath, line in removed_lines:
        if Path(filepath).name == ".gitignore":
            stripped = line.strip()
            if any(rule in stripped for rule in CRITICAL_GITIGNORE_RULES):
                ask_reasons.append(f"偵測到從 `{filepath}` 移除機密保護規則 `{stripped}`")

    # 2. 確定性金鑰與個人路徑掃描
    for filepath, line in added_lines:
        in_test_file = is_test_filepath(filepath)
        if in_test_file and "devops-guard: ignore" in line:
            continue
        for pattern, label in SENSITIVE_CONTENT_PATTERNS:
            if re.search(pattern, line):
                if in_test_file:
                    ask_reasons.append(f"測試檔案 `{filepath}` 出現疑似 {label}")
                else:
                    return (
                        "deny",
                        f"【安全攔截】變更內容包含敏感金鑰或隱私資料（{label}，位於 `{filepath or 'staged diff'}`）！已強制阻斷，防止機密洩漏至遠端倉庫。",
                    )

        # 3. 高熵疑似密碼賦值（ask）
        for match in HIGH_ENTROPY_ASSIGN_RE.finditer(line):
            val = match.group(1)
            lower_val = val.lower()
            if any(w in lower_val for w in PLACEHOLDER_WORDS):
                continue
            if shannon_entropy(val) >= 3.5:
                ask_reasons.append(f"`{filepath}` 疑似含高隨機度密鑰/密碼賦值")

    # 4. Public 倉庫額外警戒：檢查 Private 倉庫名、自訂敏感詞與內網 IP
    slug = read_github_slug(repo_root)
    vis_cache = load_visibility_cache()
    repo_info = vis_cache.get(slug) if slug else None
    is_public_repo = isinstance(repo_info, dict) and repo_info.get("private") is False

    if is_public_repo:
        current_name = slug.split("/")[-1]
        private_names = [
            info.get("name") or full.split("/")[-1]
            for full, info in vis_cache.items()
            if isinstance(info, dict) and info.get("private") is True
        ]
        sensitive_terms = load_sensitive_terms()

        for filepath, line in added_lines:
            if is_test_filepath(filepath) and "devops-guard: ignore" in line:
                continue
            for priv_name in private_names:
                if not priv_name or len(priv_name) < 4 or priv_name == current_name:
                    continue
                if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(priv_name)}(?![A-Za-z0-9_-])", line):
                    ask_reasons.append(f"Public 倉庫 `{slug}` 出現 Private 倉庫名稱 `{priv_name}`（於 `{filepath}`）")
            for term in sensitive_terms:
                if term in line:
                    ask_reasons.append(f"Public 倉庫 `{slug}` 命中本機敏感詞黑名單（於 `{filepath}`）")
            if PRIVATE_LAN_IP_RE.search(line):
                ask_reasons.append(f"Public 倉庫 `{slug}` 出現內網 IP（於 `{filepath}`）")

    if ask_reasons:
        unique_reasons = list(dict.fromkeys(ask_reasons))[:3]
        return (
            "force_ask",
            "【安全確認】偵測到疑似敏感資訊，請確認是否仍要繼續：\n- " + "\n- ".join(unique_reasons),
        )

    return "allow", ""


def check_secret_leak(cmd: str, cwd: str) -> str:
    """向後相容介面：回傳安全攔截原因字串（無風險回傳空字串）"""
    _, reason = evaluate_secret_leak(cmd, cwd)
    return reason


def _collect_push_name_status(repo_root: Path) -> List[Tuple[str, str]]:
    """收集即將推送的變更狀態 [(status, path)]"""
    diff_range = None
    for candidate in ("@{u}..HEAD", "origin/main..HEAD"):
        probe = subprocess.run(
            ["git", "rev-parse", "--verify", candidate.split("..")[0]],
            cwd=str(repo_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        if probe.returncode == 0:
            diff_range = candidate
            break

    cmd_args = ["git", "diff", "--name-status", diff_range] if diff_range else ["git", "show", "--name-status", "--format=", "HEAD"]
    res = subprocess.run(
        cmd_args,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
    )
    entries: List[Tuple[str, str]] = []
    if res.returncode == 0:
        for line in res.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                entries.append((parts[0].strip(), parts[-1].strip()))
    return entries


def evaluate_docs_and_agents_guard(cmd: str, cwd: str) -> Tuple[str, str]:
    """檢查 AGENTS.md / CLAUDE.md / GEMINI.md 規範與結構變更時的文件同步提醒"""
    is_commit = bool(re.search(r"\bgit\b.*\bcommit\b", cmd))
    is_push = bool(re.search(r"\bgit\b.*\bpush\b", cmd) and "--dry-run" not in cmd)
    if not is_commit and not is_push:
        return "allow", ""

    repo_root = resolve_target_git_root(cmd, cwd)
    if repo_root is None:
        return "allow", ""

    try:
        changed_files, _ = collect_git_diff(repo_root, is_push=is_push)
    except Exception:
        return "allow", ""

    reasons: List[str] = []
    canonical_upper = {
        "agents.md": "AGENTS.md",
        "agents.override.md": "AGENTS.override.md",
        "claude.md": "CLAUDE.md",
        "gemini.md": "GEMINI.md",
    }

    for f in changed_files:
        norm = f.strip().replace("\\", "/")
        fname = Path(norm).name
        low = fname.lower()

        if low == "claude.local.md":
            reasons.append(f"偵測到個人覆蓋檔 `{norm}`（建議加入 .gitignore，不提交至共享倉庫）")
            continue

        expected = canonical_upper.get(low)
        if expected:
            if fname != expected:
                reasons.append(f"`{norm}` 檔名大小寫不符開放標準，請改為全大寫 `{expected}`")
            fpath = repo_root / norm
            if fpath.is_file():
                raw = fpath.read_bytes()
                txt = raw.decode("utf-8", errors="ignore")
                if re.match(r"^---\s*\r?\n.*?\r?\n---", txt, re.DOTALL):
                    reasons.append(f"`{norm}` 誤含 YAML Frontmatter (`---`)；AGENTS.md / CLAUDE.md / GEMINI.md 應為純 Markdown")
                if len(raw) > 24000:
                    reasons.append(f"`{norm}` 大小 {len(raw)} bytes 超過 24,000 bytes 上限")

    if is_push:
        status_entries = _collect_push_name_status(repo_root)
        doc_touched = any(
            Path(p).name in ("README.md", "AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "GEMINI.md")
            or p.startswith("docs/")
            for _, p in status_entries
        )
        structural_change = any(
            st[:1] in ("A", "D")
            and any(p.startswith(prefix) for prefix in ("scripts/", "bin/", "src/", "skills/", "agents/", "hooks/", "tests/"))
            for st, p in status_entries
        )
        if structural_change and not doc_touched:
            reasons.append("本次推送包含新增或刪除程式/測試模組，但未同步更新 `README.md`、`docs/` 或 `AGENTS.md`")

    if reasons:
        return (
            "force_ask",
            "【文件與 AI 指引確認】偵測到以下需要注意事項，確認繼續嗎：\n- " + "\n- ".join(dict.fromkeys(reasons)),
        )
    return "allow", ""


def check_pre_push_tests(cmd: str, cwd: str) -> str:
    """檢查 git push 時目標倉庫本地單元測試是否通過"""
    if not re.search(r"\bgit\b.*\bpush\b", cmd):
        return ""

    if "--dry-run" in cmd:
        return ""

    repo_root = resolve_target_git_root(cmd, cwd) or Path(cwd).resolve()
    test_dir = None
    if (repo_root / "tests").is_dir():
        test_dir = "tests"
    elif (repo_root / "test").is_dir():
        test_dir = "test"

    if not test_dir:
        return ""

    py_exec = sys.executable or "python3"
    try:
        res = subprocess.run(
            [py_exec, "-m", "unittest", "discover", test_dir],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15,
        )
        if res.returncode != 0:
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

        if tool_name != "run_command" or not cmd:
            sys.stdout.write(json.dumps({"decision": "allow"}))
            return

        # 快速路徑：非 git commit/push 指令立即放行
        if not re.search(r"\bgit\b.*\b(?:commit|push)\b", cmd):
            sys.stdout.write(json.dumps({"decision": "allow"}))
            return

        # 1. Force push 檢測（最高優先硬攔）
        reason = check_force_push(cmd)
        if reason:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": reason}, ensure_ascii=False))
            return

        # 2. 敏感資料與金鑰掃描（區分 deny 與 force_ask）
        sec_decision, sec_reason = evaluate_secret_leak(cmd, cwd)
        if sec_decision == "deny":
            sys.stdout.write(json.dumps({"decision": "deny", "reason": sec_reason}, ensure_ascii=False))
            return

        # 3. Pre-push 單元測試守門（hard deny）
        test_reason = check_pre_push_tests(cmd, cwd)
        if test_reason:
            sys.stdout.write(json.dumps({"decision": "deny", "reason": test_reason}, ensure_ascii=False))
            return

        # 4. 文件與 AI 指引規範檢查（force_ask）
        doc_decision, doc_reason = evaluate_docs_and_agents_guard(cmd, cwd)

        # 5. 疑似敏感資料或文件提醒跳人工確認（force_ask）
        if sec_decision == "force_ask" and doc_decision == "force_ask":
            sys.stdout.write(json.dumps({"decision": "force_ask", "reason": f"{sec_reason}\n\n{doc_reason}"}, ensure_ascii=False))
            return
        if sec_decision == "force_ask":
            sys.stdout.write(json.dumps({"decision": "force_ask", "reason": sec_reason}, ensure_ascii=False))
            return
        if doc_decision == "force_ask":
            sys.stdout.write(json.dumps({"decision": "force_ask", "reason": doc_reason}, ensure_ascii=False))
            return

        sys.stdout.write(json.dumps({"decision": "allow"}))
    except Exception as e:
        sys.stdout.write(json.dumps({"decision": "allow", "reason": f"Guard error: {e}"}))


if __name__ == "__main__":
    main()
