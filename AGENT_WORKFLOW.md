# RiskMouse Agent 工作流

## 目标

将“分析一只股票的近期风险”拆解为可观察、可重试、可验证的任务，而不是一次不可控的大模型调用。

## 运行链路

```text
POST /api/agent/plan 或 /api/agent/run
  → 规则式 Planner 生成任务 DAG
  → Orchestrator 并发执行独立工具任务
  → Verifier 以证据和局限性约束最终报告
  → GET /api/agent/runs/{run_id} 查询全量执行轨迹
```

当前计划：`financial`、`news`、`sentiment` 并发执行，全部完成后执行 `report`。

## 工程约束

- Planner 只能生成注册表中的工具，避免模型获得任意代码执行能力。
- 每个任务记录状态、耗时、调用次数、输出或错误。
- 单个工具失败不会终止其余无依赖任务；报告会保留数据缺失说明。
- 报告必须携带 `evidence`，无有效证据时风险等级为 `needs_review`。

## 全局任务编排

RiskMouse 参考 Claude Code 的统一任务状态机思路：分析工作流与深度巡检都通过同一个 `WorkflowStore` 创建 `run_id`，共享 `pending → running → succeeded / failed / skipped` 生命周期、任务级重试、超时、SQLite 审计记录与前端轮询接口。

- `POST /api/agent/run`：单股风险分析 DAG。
- `POST /api/agent/patrol`：宏观新闻 + 自选股股吧的全局巡检。
- `POST /api/agent/surf`：兼容旧入口，内部转入全局巡检任务。

任务创建时可附带 `session_id`，使任务目标能够进入该会话的短期工作上下文。

## 小老鼠记忆

设计借鉴 Claude Code 的“会话摘要 + 按需相关记忆”模式，但面向金融场景做了更严格的收敛：

| 层级 | 保存内容 | 用法 |
|------|----------|------|
| 短期记忆 | 最近 8 轮消息、当前会话摘要、活动目标 | 每轮聊天注入，自动压缩而非无限堆积 |
| 长期记忆 | 风险偏好、关注标的、明确反馈、项目规则、外部参考 | 关键词相关性排序后最多注入 5 条 |

长期记忆只在用户明确说“记住……”或显式调用 API 时写入。不会自动保存临时行情、聊天流水、密码、API Key 或 Token。中文检索采用“词组 + 双字片段”匹配，避免“新能源板块”和“新能源风险”无法召回的问题。

记忆 API：

- `GET /api/agent/memory/session/{session_id}`：查看当前会话短期记忆。
- `GET /api/agent/memory`：查看长期记忆。
- `POST /api/agent/memory`：显式保存长期记忆。

## 调试示例

```bash
curl -X POST http://localhost:8787/api/agent/plan \
  -H "Content-Type: application/json" \
  -d '{"question":"分析比亚迪近期风险","symbol":"002594"}'

curl -X POST http://localhost:8787/api/agent/run \
  -H "Content-Type: application/json" \
  -d '{"question":"分析比亚迪近期风险","symbol":"002594"}'
```

使用返回的 `run_id` 请求 `GET /api/agent/runs/{run_id}`。运行记录同时保存在 SQLite，服务重启后仍可用于审计。

## 离线评测

`backend/tests/test_agent_runtime.py` 覆盖两类必须稳定的行为：Planner 只能产出白名单工具；当数据源全空时，Verifier 必须返回 `needs_review`，而不是伪造风险结论。

```bash
python -m unittest backend.tests.test_agent_runtime
```
