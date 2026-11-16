#!/usr/bin/env bash
#
# GitHub DevOps & Release Automation Toolkit Installer
# 一鍵部署至全域底座 (~/.gemini/config/plugins/github-devops) 或當前專案工作區 (.agents/plugins/...)
#

set -euo pipefail

PLUGIN_NAME="github-devops"
MODE="global"
LINK_MODE="copy"

for arg in "$@"; do
    case "$arg" in
        -w|--workspace)
            MODE="workspace"
            ;;
        -g|--global)
            MODE="global"
            ;;
        -s|--symlink)
            LINK_MODE="symlink"
            ;;
        -h|--help)
            echo "Usage: install.sh [--global | --workspace] [--symlink]"
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 1
            ;;
    esac
done

if [ "$MODE" = "workspace" ]; then
    TARGET_DIR=".agents/plugins/${PLUGIN_NAME}"
else
    TARGET_DIR="${HOME}/.gemini/config/plugins/${PLUGIN_NAME}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$(dirname "$TARGET_DIR")"

if [ "$LINK_MODE" = "symlink" ]; then
    rm -rf "$TARGET_DIR"
    ln -s "$SCRIPT_DIR" "$TARGET_DIR"
    echo "✔ Symlinked $TARGET_DIR -> $SCRIPT_DIR"
else
    rm -rf "$TARGET_DIR"
    mkdir -p "$TARGET_DIR"
    for item in plugin.json assets hooks.json hooks rules agents skills run_tests.py LICENSE README.md; do
        if [ -e "$SCRIPT_DIR/$item" ]; then
            cp -r "$SCRIPT_DIR/$item" "$TARGET_DIR/"
        fi
    done
    echo "✔ Installed $PLUGIN_NAME to $TARGET_DIR"
fi

if command -v agy >/dev/null 2>&1; then
    agy plugin validate "$TARGET_DIR" --strict || true
fi
