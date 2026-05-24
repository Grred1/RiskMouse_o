# 企业风控系统

财报分析 · 风险挖掘 · 自选风控 · AI 解读

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
