## 项目概述
股票主营构成分析工具，提供涨停板池分析、财务健康度分析、主营构成解读等功能。

## 技术栈
- **后端**：FastAPI + uvicorn
- **数据源**：akshare（东方财富股票数据）
- **AI 集成**：coze-coding-dev-sdk
- **前端**：静态 HTML + JS + CSS

## 目录结构
```
business_analysis/
├── main.py              # FastAPI 主应用
├── zt_board_analysis.py # 涨停板分析脚本
├── prompts/             # AI 提示词模板
├── css/                 # 样式文件
├── js/                  # 前端脚本
├── cache/               # 数据缓存
└── scripts/            # 预览脚本
    ├── coze-preview-build.sh
    └── coze-preview-run.sh
```

## 预览入口
- `build`：安装 Python 依赖（akshare, pandas, fastapi, uvicorn, coze-coding-dev-sdk）
- `run`：启动 uvicorn 服务，绑定 `0.0.0.0:5000`

## AI 调用
通过 Coze SDK 调用大语言模型：
```python
from coze_coding_dev_sdk import LLMClient
from langchain_core.messages import HumanMessage

client = LLMClient(ctx=new_context(method="invoke"))
response = client.invoke(messages=[HumanMessage(content=prompt)])
```

## 关键入口
- `/` - 首页
- `/api/zygc?symbol=xxx` - 主营构成数据
- `/api/analyze` - AI 解读主营构成
- `/api/financial` - 财务分析
- `/api/zt/pool` - 涨停池
