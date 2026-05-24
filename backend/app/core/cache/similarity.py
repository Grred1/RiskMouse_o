"""
新闻标题相似度工具
使用多策略（字符级 + bigram + 关键词）计算中文标题相似度。
"""
from __future__ import annotations

import re

import jieba

jieba.setLogLevel(20)


_SKIP_PREFIXES = [
    "快讯", "速递", "盘中", "突发", "最新", "早报", "晚报",
    "午评", "收评", "综述", "解读", "评论", "观点",
]
_SKIP_SUFFIXES = [
    "报道", "记者", "编辑", "作者",
]


def normalize_title(title: str) -> str:
    t = title.lower()
    for p in _SKIP_PREFIXES:
        if t.startswith(p):
            t = t[len(p):]
    for s in _SKIP_SUFFIXES:
        if t.endswith(s):
            t = t[:-len(s)]
    t = re.sub(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日号]?', '', t)
    t = re.sub(r'\d{1,2}[-/月]\d{1,2}[日号]?', '', t)
    t = re.sub(r'\d{1,2}[点时]\d{0,2}分?', '', t)
    t = re.sub(r'\d+[\.,]?\d*%', '', t)
    t = re.sub(r'\d+[\.,]?\d*', '', t)
    for org in ['高盛', '摩根', '瑞银', '摩根士丹利', '美银', '中信', '国泰',
                '华尔街', '市场', '全球', '国际', '国内']:
        t = t.replace(org.lower(), '')
    t = re.sub(r'[^\w\u4e00-\u9fff]', '', t)
    return t.strip()


def _bigrams(text: str, n: int = 2) -> set[str]:
    if len(text) < n:
        return {text}
    return {text[i:i+n] for i in range(len(text) - n + 1)}


def _dice(s1: set, s2: set) -> float:
    intersection = s1 & s2
    if not intersection:
        return 0.0
    return 2.0 * len(intersection) / (len(s1) + len(s2))


def _jaccard(s1: set, s2: set) -> float:
    union = s1 | s2
    if not union:
        return 0.0
    return len(s1 & s2) / len(union)


def _extract_keywords(text: str) -> set[str]:
    """jieba 分词，返回 ≥2 字的关键词"""
    words = jieba.lcut(text)
    return {w for w in words if len(w) >= 2}


def calculate_similarity(title1: str, title2: str) -> float:
    n1 = normalize_title(title1)
    n2 = normalize_title(title2)

    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0

    char_set1 = set(n1)
    char_set2 = set(n2)

    # 策略1: 字符级 Dice
    char_d = _dice(char_set1, char_set2)

    # 策略2: Bigram/Trigram Dice（保留原文顺序）
    ngram1 = _bigrams(n1, 2) | _bigrams(n1, 3)
    ngram2 = _bigrams(n2, 2) | _bigrams(n2, 3)
    ngram_d = _dice(ngram1, ngram2)

    # 策略3: 关键词 Jaccard（jieba 分词）
    kw1 = _extract_keywords(n1)
    kw2 = _extract_keywords(n2)
    kw_j = _jaccard(kw1, kw2) if kw1 and kw2 else 0.0

    # 策略4: 长关键词奖励（≥4 字关键词说明是同一事件）
    shared_kw = kw1 & kw2 if kw1 and kw2 else set()
    longest_shared = max((w for w in shared_kw if len(w) >= 4), key=len, default="")
    kw_bonus = 0.35 if len(longest_shared) >= 4 else 0.0

    score = char_d * 0.1 + ngram_d * 0.25 + kw_j * 0.3 + kw_bonus
    return round(min(score, 1.0), 4)
