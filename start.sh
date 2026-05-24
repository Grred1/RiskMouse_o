#!/usr/bin/env bash
set -e

# ── 企业风控系统 ── 一键启动脚本 ──────────────────────────────────
# 用法: bash start.sh [port]
# 默认端口: 8787

PORT="${1:-8787}"
DIR="$(cd "$(dirname "$0")" && pwd)"

cd "$DIR"

# 1. 检查 .env 是否存在
if [ ! -f .env ]; then
    echo "⚠️  未检测到 .env 文件，正在从 .env.example 复制..."
    cp .env.example .env
    echo "✅ 已创建 .env，请编辑填入你的 API Key 后重新运行"
    exit 1
fi

# 2. 检查虚拟环境
if [ ! -f .venv/bin/uvicorn ]; then
    echo "📦 虚拟环境未就绪，正在创建..."
    python3 -m venv .venv
    echo "📦 安装依赖..."
    .venv/bin/pip install -r requirements.txt -q
    echo "✅ 依赖安装完成"
fi

# 3. 启动服务
echo "🚀 启动服务 (端口 $PORT)..."
exec .venv/bin/uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
