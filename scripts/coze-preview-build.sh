#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 安装 Python 依赖
pip install -q akshare pandas fastapi uvicorn coze-coding-dev-sdk coze-coding-utils langchain-core
