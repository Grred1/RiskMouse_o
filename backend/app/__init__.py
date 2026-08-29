"""
Backend 模块
"""

# 保持包初始化无副作用。数据源依赖与数据库只应在实际使用模块时加载，
# 这样 Planner / Verifier 等离线评测不需要安装 AKShare 或启动数据库。
