"""
主营构成分析 Agent
分析股票的主营构成数据，判断业务稳定性和收入集中度风险。
"""
from .base import Agent

agent = Agent(
    name="analyze_zygc",
    description="分析股票的主营构成，判断业务稳定性和收入集中度风险",
    category="finance",
    prompt_name="zygc_analysis",
    input_keys=["symbol", "industry_data", "product_data", "region_data"],
    cache_key_pattern="finance:zygc_analysis:{code}",
    cache_ttl=86400,
    max_tokens=500,
    temperature=0.3,
)
