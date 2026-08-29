# RiskMouse — 财报基本面 × 舆论情绪 · 智能风控

财报分析 · 风险挖掘 · 自选风控 · AI 解读

## Agent 工作流（新增）

RiskMouse 现提供一个可验证的风险分析 Agent 工作流。它不会让模型直接给出结论，而是把请求拆解为工具任务：财务、新闻和股吧舆情任务并发执行，随后由报告任务汇总，并保留每条结论的证据与数据缺失说明。

```text
需求 → Planner → 并发工具调用 → Verifier → 可追溯报告
                  ↓
             SQLite 运行轨迹
```

接口：

| 接口 | 作用 |
|------|------|
| `POST /api/agent/plan` | 仅生成受控任务计划 |
| `POST /api/agent/run` | 异步启动风险分析工作流 |
| `GET /api/agent/runs/{run_id}` | 查询任务状态、耗时、重试、错误和报告 |
| `GET /api/agent/tools` | 查看可调用工具白名单 |

详细的设计和调试命令见 [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md)。

小老鼠还具备会话短期记忆与按需长期记忆：它只会保存用户明确要求记住的稳定风险偏好、关注方向和纠正反馈；每次对话仅注入最近会话内容与最多 5 条相关记忆，避免上下文无限膨胀。

---

## 环境要求

- Python 3.10 或 3.11
- 网络可访问（数据来源 akshare，需能访问 A 股数据接口）

---

## 快速启动

### 1. 克隆仓库

```bash
git clone https://github.com/leier0523/Fengkong.git
cd Fengkong/business_analysis
```

### 2. 安装依赖

```bash
pip install -r backend/requirements.txt
```

> `easyocr` 体积较大（用于截图 OCR 上传自选股），如不需要可跳过：
> ```bash
> pip install fastapi uvicorn akshare pandas openai python-dotenv wordcloud jieba pillow numpy
> ```

### 3. 配置 API Key

复制示例文件并填入你的 DeepSeek Key：

```bash
cp .env.example .env
```

编辑 `.env`，将 `sk-your_deepseek_key_here` 替换为你在 [platform.deepseek.com](https://platform.deepseek.com/api_keys) 申请的 Key：

```
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
```

> DeepSeek 注册后有免费额度，申请后即可使用。

### 4. 启动服务

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 5. 打开浏览器

- 着陆页：http://localhost:8000
- 主平台：http://localhost:8000/app

---

## 功能模块

| 模块 | 说明 |
|------|------|
| 财报分析 | 主营构成、财务趋势、AI 解读 |
| 风险挖掘 | 涨停/龙虎榜热点、股吧舆情、风险评分 |
| 自选风控 | 最多 10 只股票，AI 一键风控测评 |

---

## 项目结构

```
business_analysis/
├── backend/
│   ├── app/          # FastAPI 后端
│   ├── prompts/      # AI Prompt 模板
│   └── requirements.txt
├── frontend/
│   ├── index.html    # 主平台页面
│   ├── timeline.html # 着陆页
│   └── src/          # JS / CSS 资源
└── .env.example      # 环境变量模板
```
