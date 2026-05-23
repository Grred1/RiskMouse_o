# 企业风控系统

## 项目概述

企业风险监控系统，从财报和舆论两个维度挖掘企业经营风险。

## 技术栈

- **前端**: 原生 JavaScript (ES6+ 模块化)
- **后端**: FastAPI + akshare
- **AI**: Coze SDK (coze-coding-dev-sdk)
- **数据源**: AKShare 金融数据库

## 目录结构

```
business_analysis/
├── frontend/                    # 前端
│   └── src/
│       ├── app.js              # 入口文件
│       ├── services/
│       │   └── api.js          # API 调用层
│       └── components/
│           ├── macro/          # 宏观日历组件
│           ├── finance/        # 财报分析组件
│           └── sentiment/      # 舆论风险组件
│
├── backend/                     # 后端
│   ├── app/
│   │   ├── main.py             # FastAPI 入口
│   │   ├── api/                # API 路由
│   │   │   ├── finance.py      # 财报相关 API
│   │   │   └── sentiment.py    # 舆论相关 API
│   │   ├── core/              # 核心配置
│   │   │   ├── config.py      # 配置和工具函数
│   │   │   └── llm.py         # LLM 调用封装
│   │   ├── services/          # 业务逻辑
│   │   └── schemas/           # 数据模型
│   ├── prompts/               # AI 提示词
│   └── requirements.txt
│
├── cache/                      # 数据缓存
├── css/                        # 样式文件
├── scripts/                    # 脚本
│   ├── coze-preview-build.sh
│   └── coze-preview-run.sh
└── index.html                  # 前端入口
```

## 多人协作分工建议

| 模块 | 负责文件 | 说明 |
|------|----------|------|
| 宏观日历 | `frontend/src/components/macro/` | 前端展示 |
| 财报风险 | `frontend/src/components/finance/` + `backend/app/api/finance.py` | 前后端联动 |
| 舆论风险 | `frontend/src/components/sentiment/` + `backend/app/api/sentiment.py` | 前后端联动 |
| AI 能力 | `backend/app/core/llm.py` | LLM 调用封装 |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 首页 |
| `/api/zygc` | GET | 获取主营构成 |
| `/api/financial` | GET | 获取财务数据 |
| `/api/analyze/zygc` | POST | AI 解读主营构成 |
| `/api/zt/pool` | GET | 获取涨停池 |
| `/api/zt/analyze` | POST | AI 风险分析 |

## 启动方式

```bash
# 安装依赖
pip install -r backend/requirements.txt

# 开发模式
uvicorn backend.app.main:app --reload --port 5000

# 或使用脚本
bash scripts/coze-preview-run.sh
```

## 注意事项

- 后端入口: `backend.app.main:app`
- Prompts 目录已迁移到 `backend/prompts/`
- 前端使用 ES6 模块，需要通过 HTTP 服务访问
