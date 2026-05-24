#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 显式声明关键环境变量
export PORT=5000
export LLM_PROVIDER=coze

# 启动 FastAPI 服务
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 5000
