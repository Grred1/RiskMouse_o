"""
AKShare 数据接口统一封装层
所有 AKShare 调用统一入口，统一错误处理 + 统一异常返回格式
"""
from __future__ import annotations

import logging

import akshare as ak

logger = logging.getLogger(__name__)


# ── 主营构成 ────────────────────────────────────────────────────

def get_stock_zygc(symbol: str):
    """获取主营构成数据"""
    try:
        return ak.stock_zygc_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_zygc_em(%s) 失败: %s", symbol, e)
        return None


# ── 三张报表 ────────────────────────────────────────────────────

def get_profit_sheet(symbol: str):
    """获取利润表"""
    try:
        return ak.stock_profit_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_profit_sheet_by_report_em(%s) 失败: %s", symbol, e)
        return None


def get_balance_sheet(symbol: str):
    """获取资产负债表"""
    try:
        return ak.stock_balance_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_balance_sheet_by_report_em(%s) 失败: %s", symbol, e)
        return None


def get_cash_flow_sheet(symbol: str):
    """获取现金流量表"""
    try:
        return ak.stock_cash_flow_sheet_by_report_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_cash_flow_sheet_by_report_em(%s) 失败: %s", symbol, e)
        return None


# ── 财务摘要 ────────────────────────────────────────────────────

def get_financial_abstract(symbol: str):
    """获取财务摘要（同花顺）"""
    try:
        return ak.stock_financial_abstract_ths(symbol=symbol)
    except Exception as e:
        logger.warning("stock_financial_abstract_ths(%s) 失败: %s", symbol, e)
        return None


# ── 涨停 / 龙虎榜 ────────────────────────────────────────────────

def get_zt_pool(date: str):
    """获取涨停板池"""
    try:
        return ak.stock_zt_pool_em(date=date)
    except Exception as e:
        logger.warning("stock_zt_pool_em(%s) 失败: %s", date, e)
        return None


def get_lhb_detail():
    """获取龙虎榜明细"""
    try:
        return ak.stock_lhb_detail_em()
    except Exception as e:
        logger.warning("stock_lhb_detail_em() 失败: %s", e)
        return None


# ── 新闻 / 评论 ──────────────────────────────────────────────────

def get_stock_news(symbol: str):
    """获取个股新闻"""
    try:
        return ak.stock_news_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_news_em(%s) 失败: %s", symbol, e)
        return None


def get_stock_comments(symbol: str):
    """获取个股股吧评论"""
    try:
        return ak.stock_comments_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_comments_em(%s) 失败: %s", symbol, e)
        return None


# ── 股吧热度 ──────────────────────────────────────────────────────

def get_hot_keywords(symbol: str):
    """获取热门关键词（概念热度）"""
    try:
        return ak.stock_hot_keyword_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_hot_keyword_em(%s) 失败: %s", symbol, e)
        return None


def get_hot_rank_latest(symbol: str):
    """获取最新人气排名"""
    try:
        return ak.stock_hot_rank_latest_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_hot_rank_latest_em(%s) 失败: %s", symbol, e)
        return None


def get_hot_rank_relate(symbol: str):
    """获取人气相关股票"""
    try:
        return ak.stock_hot_rank_relate_em(symbol=symbol)
    except Exception as e:
        logger.warning("stock_hot_rank_relate_em(%s) 失败: %s", symbol, e)
        return None


def get_hot_rank_latest_all():
    """获取全市场人气排名"""
    try:
        return ak.stock_hot_rank_latest_em()
    except Exception as e:
        logger.warning("stock_hot_rank_latest_em() 失败: %s", e)
        return None


# ── K线行情 ──────────────────────────────────────────────────────

def get_stock_history(symbol: str, period: str = "daily",
                      start_date: str = "", end_date: str = "",
                      adjust: str = "qfq"):
    """获取历史行情"""
    try:
        return ak.stock_zh_a_hist(
            symbol=symbol, period=period,
            start_date=start_date, end_date=end_date, adjust=adjust,
        )
    except Exception as e:
        logger.warning("stock_zh_a_hist(%s) 失败: %s", symbol, e)
        return None


# ── 宏观经济 ────────────────────────────────────────────────────

def get_cpi_yearly():
    """获取年度 CPI 数据"""
    try:
        return ak.macro_china_cpi_yearly()
    except Exception as e:
        logger.warning("macro_china_cpi_yearly() 失败: %s", e)
        return None


def get_gdp():
    """获取 GDP 数据"""
    try:
        return ak.macro_china_gdp()
    except Exception as e:
        logger.warning("macro_china_gdp() 失败: %s", e)
        return None


def get_pmi():
    """获取 PMI 数据"""
    try:
        return ak.macro_china_pmi()
    except Exception as e:
        logger.warning("macro_china_pmi() 失败: %s", e)
        return None
