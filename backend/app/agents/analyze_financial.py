"""
财报分析 Agent
整合财务健康度 + 成长性分析 + 综合评分。
使用 prompts/ 目录下的提示词文件。
"""
from .base import Agent

agent = Agent(
    name="analyze_financial",
    description="综合财务分析：健康度（偿债/运营/现金流）+ 成长性（营收/利润/研发）+ 量化评分",
    category="finance",
    prompt_name="financial_combined",
    input_keys=["symbol", "name", "financial_data", "historical_data", "industry_data"],
    cache_key_pattern="finance:financial_combined:{code}",
    cache_ttl=86400,
    max_tokens=1000,
    temperature=0.3,
)
