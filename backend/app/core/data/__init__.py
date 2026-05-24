"""
统一数据接口层

集中管理所有数据源调用（AKShare / 股吧爬虫 / 新闻爬虫），
API 层通过此模块访问数据，避免重复代码和散落的 try/except。
"""
from . import akshare
from . import guba
from . import news

__all__ = [
    "akshare",
    "guba",
    "news",
]
