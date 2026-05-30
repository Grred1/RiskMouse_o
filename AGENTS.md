# RiskMouse — 财报基本面 × 舆论情绪 · 智能风控

## 项目概述

企业风险监控系统，从**财报基本面**和**舆论情绪**两个维度挖掘 A 股企业经营风险。系统集成了宏观日历、财报深度分析、热门关注风险挖掘、自选股组合风控，以及一个名为"小老鼠"的 AI 自动化巡检助手。

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| **前端** | 原生 JavaScript (ES6+, ECharts 图表, Web Component) |
| **后端** | Python FastAPI |
| **AI** | DeepSeek API (本地开发) / Coze SDK (Coze 平台部署) |
| **金融数据** | AKShare 开源金融数据库 |
| **持久化** | SQLite (自选股 + 分析缓存) |
| **本地 RAG** | JSON 文件缓存 → 内存知识库 |
| **其他** | jieba 分词 + wordcloud 词云 + easyocr 截图识别 |

## 目录结构

```
├── frontend/                        # 前端静态文件
│   ├── index.html                   # 单页应用入口（平台主界面）
│   ├── timeline.html                # 着陆页
│   └── src/
│       ├── js/
│       │   ├── common.js            # 通用工具函数
│       │   ├── finance.js           # 财报分析交互（主营构成 + 财务图表）
│       │   ├── risk.js              # 风险挖掘交互（涨停池 + 龙虎榜）
│       │   ├── macro.js             # 宏观日历交互
│       │   ├── watchlist.js         # 自选风控交互
│       │   └── mouse-agent.js       # 小老鼠 AI 助手 Web Component
│       ├── styles/                  # 各模块 CSS
│       │   ├── common.css
│       │   ├── finance.css
│       │   ├── mouse-agent.css
│       │   ├── watchlist.css
│       │   └── zt.css
│       └── images/                  # 小老鼠角色动画素材
│           ├── mouse-idle.png
│           ├── mouse-thinking.png
│           ├── mouse-surfing.png
│           └── mouse-alert.png
│
├── backend/                         # 后端 Python 服务
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口（路由注册 + CORS + 静态文件挂载）
│   │   ├── db.py                    # SQLite 持久化层（自选股 + 分析结果缓存）
│   │   ├── risk_engine.py           # 纯算法风险评分引擎（无需 AI）
│   │   ├── api/
│   │   │   ├── finance.py           # 财报风险 API（主营构成、利润表/资产负债表/现金流、AI 分析）
│   │   │   ├── sentiment.py         # 风险挖掘 API（涨停池 + 龙虎榜 + AI 结构化评分）
│   │   │   ├── watchlist.py         # 自选风控 API（CRUD、四维评分、词云、新闻、截图OCR、风险日记）
│   │   │   └── mouse_agent.py       # 小老鼠 Agent API（聊天、网上冲浪、通知、邮件、RAG、定时巡检）
│   │   └── core/
│   │       ├── config.py            # 核心配置（缓存路径、股票代码标准化、名称查询、Prompt 加载）
│   │       ├── llm.py               # LLM 统一调用（DeepSeek / Coze 双模式切换）
│   │       ├── coze_agent.py        # Coze Stream Agent 调用封装 + 新闻真伪鉴定
│   │       ├── cache_rag.py         # 本地缓存 RAG 引擎（扫描 cache/ JSON → 内存知识库）
│   │       └── usage_doc.py         # 使用文档（供小老鼠 Agent 回复用户功能问题时引用）
│   └── prompts/                     # AI Prompt 模板
│       ├── zygc_analysis.txt        # 主营构成 AI 分析
│       ├── financial_combined.txt   # 财务健康+增长综合分析
│       ├── zt_risk.txt              # 涨停/龙虎榜风险分析
│       ├── watchlist_risk.txt       # 自选股 AI 解读
│       ├── narrative_extract.txt    # 叙事实体提取
│       └── narrative_verify.txt     # 叙事真伪验证
│
├── scripts/
│   ├── coze-preview-build.sh
│   └── coze-preview-run.sh
│
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量示例
├── start.sh                         # 一键启动脚本
├── .gitignore
├── AGENTS.md                        # 项目文档
├── README.md                        # 项目说明
└── 版本修改.md                      # 变更日志
```

## 核心功能模块

| 模块 | 前端文件 | 后端文件 | 功能说明 |
|------|----------|----------|----------|
| 📅 **宏观日历** | `macro.js` | — | 全年宏观数据发布日程表，重要/关注/常规三级标记 |
| 📊 **财报风险** | `finance.js` | `api/finance.py` | 主营构成（行业/产品/地区维度）+ 财务全景（利润表、资产负债表、现金流）+ 7 个预定义 ECharts 图表（营收趋势、研发投入、费用率、资产扩张、盈利能力、资产结构、现金流），数据缺失时自动隐藏面板 + AI 四维评分 |
| 📰 **风险挖掘** | `risk.js` | `api/sentiment.py` | 涨停池 + 龙虎榜热门关注列表 + AI 三维结构化评分（逻辑匹配度/财务健康度/估值泡沫度 1-5分），前端评分条 + 星标胶囊可视化 |
| 🛡️ **自选风控** | `watchlist.js` | `api/watchlist.py` | 自选股管理 + 图片 OCR 识别 + 四维算法评分 + 新闻词云 + 风险日记 |
| 🐭 **小老鼠 Agent** | `mouse-agent.js` (Web Component) | `api/mouse_agent.py` | 自动定时巡检 + 股吧真伪鉴定 + RAG 问答 + 邮件通知 |

## 风险评分体系

系统提供两套评分机制：

### 1. 算法评分（`risk_engine.py`，零 AI 依赖）

| 维度 | 说明 | 主要指标 |
|------|------|----------|
| 基本面评分 | 财务健康度打分 1-5★ | 营收增速、净利增速、毛利率、ROE、资产负债率 |
| 新闻情绪评分 | 新闻文本风险打分 1-5★ | 高危词库（立案/退市/造假）→ 负面；正面词库（中标/回购/增长）→ 正面 |
| 风险等级 | 综合风险打分 1-5★（越高越危险） | 负债 40% + 新闻负面 35% + 盈利稳定 25% |
| 综合评分 | 整体质量打分 1-5★ | 基本面 40% + 新闻 30% + 低风险 30% |

### 2. AI 评分（LLM 驱动）

- **财报 AI 分析**：偿债能力 / 营运能力 / 盈利能力 / 成长能力 四维评分，可视化星级展示
- **风险挖掘 AI 评分**：JSON 结构化输出（逻辑匹配度、财务健康度、估值泡沫度 1-5分），前端以评分条 + 星标胶囊可视化展示
- **旧版文本回退**：LLM 未输出 JSON 时自动按旧格式（【综合风险评分】【各维度评分】【核心风险点】【风险结论】）解析并结构化渲染

## API 接口一览

| 接口 | 方法 | 所属模块 | 说明 |
|------|------|----------|------|
| `/` | GET | 首页 | 返回前端 SPA 页面 |
| `/api/zygc` | GET | 财报风险 | 获取主营构成数据 |
| `/api/financial` | GET | 财报风险 | 获取财务数据（三表 + 摘要） |
| `/api/analyze/zygc` | POST | 财报风险 | AI 解读主营构成 |
| `/api/analyze/financial` | POST | 财报风险 | AI 财务综合分析（健康+增长） |
| `/api/risk/pool` | GET | 风险挖掘 | 获取热门关注池（涨停板 + 龙虎榜） |
| `/api/risk/analyze` | POST | 风险挖掘 | AI 结构化评分（逻辑匹配度/财务健康度/估值泡沫度 1-5分 + 综合结论 JSON） |
| `/api/watchlist/list` | GET | 自选风控 | 获取自选股列表 |
| `/api/watchlist/add` | POST | 自选风控 | 添加自选股 |
| `/api/watchlist/remove` | POST | 自选风控 | 移除自选股 |
| `/api/watchlist/detail/{code}` | GET | 自选风控 | 单股完整分析（四维评分 + 词云 + 新闻 + AI 解读） |
| `/api/watchlist/assess` | POST | 自选风控 | 批量评估所有自选股 |
| `/api/watchlist/parse-image` | POST | 自选风控 | 截图 OCR 识别股票代码 |
| `/api/watchlist/diary` | GET/POST | 自选风控 | 风险日记 CRUD |
| `/api/agent/status` | GET | 小老鼠 | 获取 Agent 状态 |
| `/api/agent/surf` | POST | 小老鼠 | 触发立即巡检 |
| `/api/agent/chat` | POST | 小老鼠 | 对话提问 |
| `/api/agent/notifications` | GET | 小老鼠 | 获取通知列表 |
| `/api/agent/email-config` | GET/POST | 小老鼠 | 邮件通知配置 |
| `/api/agent/timer-start/stop` | GET | 小老鼠 | 定时任务启停 |
| `/api/agent/rag-info` | GET | 小老鼠 | RAG 知识库状态 |

## 启动方式

```bash
# 方式一：一键启动（推荐）
bash start.sh          # 默认端口 8787
bash start.sh 5000    # 或指定端口

# 方式二：手动启动
cd /path/to/Fengkong
source .venv/bin/activate        # 激活虚拟环境
cp .env.example .env             # 首次需配置环境变量
pip install -r requirements.txt  # 首次需安装依赖
uvicorn backend.app.main:app --reload --port 8787
```

服务启动后访问:
- 着陆页: http://localhost:8787
- 平台主界面: http://localhost:8787/app

## 架构要点

- **后端入口**: `backend.app.main:app`，FastAPI 应用从项目根目录启动（`uvicorn backend.app.main:app`）
- **缓存机制**: 数据缓存 `cache/` 目录自动生成，AI 分析结果缓存避免重复调用 LLM
- **缓存控制**: HTML 响应加 `Cache-Control: no-cache` 头，JS/CSS 通过 `?v=N` 版本号控制缓存更新
- **本地 RAG**: `cache_rag.py` 自动索引 `cache/` 下所有 JSON 文件，供小老鼠 Agent 闲聊时检索
- **LLM 双模式**: 通过 `LLM_PROVIDER` 环境变量切换 DeepSeek (本地开发) / Coze (平台部署)
- **双轨评分**: 算法评分即时响应（无 AI 依赖），AI 评分提供深度解读（需 LLM 调用）
- **小老鼠 Agent**: Web Component `<mouse-assistant>` 自包含，自动定时巡检（每 10 分钟）+ 首次加载 5 秒后自动冲浪

## 注意事项

- 前端使用 ES6 模块 + ECharts CDN，需要通过 HTTP 服务访问（不能直接 `file://` 打开）
- Prompts 目录位于 `backend/prompts/`
- easyocr 为可选依赖，未安装时截图 OCR 功能不可用
- 词云功能依赖中文字体，Windows 下会自动查找 `msyh.ttc`/`simhei.ttf`
- 系统所有 AI 分析仅供风险参考，**不构成投资建议**
- 数据来源于东方财富、同花顺等公开数据平台，可能存在延迟
