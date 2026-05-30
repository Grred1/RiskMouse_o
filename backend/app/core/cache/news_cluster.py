"""
新闻聚类引擎
将相似新闻聚合到同一事件下，减少 LLM 重复分析。

核心逻辑：
  - 每条新闻进来，先跟已有事件摘要做 Jaccard 相似度匹配
  - 相似度 ≥ 阈值 → 合并到现有事件（加链接/更新日期）
  - 相似度 < 阈值 → 创建新事件
  - 去重后的独立事件列表交给 LLM 过滤和时间分析
"""
from __future__ import annotations

import json
import os
import hashlib
import logging
from datetime import datetime
from typing import Optional

from ..config import CACHE_DIR
from .similarity import calculate_similarity, normalize_title

logger = logging.getLogger(__name__)

_CLUSTER_PATH = os.path.join(CACHE_DIR, "news_clusters.json")
_SIMILARITY_THRESHOLD = 0.28


# ── 内部数据结构 ──────────────────────────────────────────────

class NewsCluster:
    """
    单个新闻事件聚类。
    """
    def __init__(self, cluster_id: str, title: str, summary: str,
                 url: str, source: str, date: str):
        self.id = cluster_id
        self.title = title
        self.summary = summary
        self.urls: list[dict] = [{"url": url, "source": source, "date": date}]
        self.sources: list[str] = [source]
        self.dates: list[str] = [date]
        self.first_date = date
        self.last_date = date
        self.hit_count = 1

    def merge(self, url: str, source: str, date: str):
        """合并一条同类新闻到此事件"""
        if not any(u["url"] == url for u in self.urls):
            self.urls.append({"url": url, "source": source, "date": date})
        if source not in self.sources:
            self.sources.append(source)
        if date not in self.dates:
            self.dates.append(date)
        if date < self.first_date:
            self.first_date = date
        if date > self.last_date:
            self.last_date = date
        self.hit_count += 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "summary": self.summary,
            "urls": self.urls,
            "sources": self.sources,
            "first_date": self.first_date,
            "last_date": self.last_date,
            "hit_count": self.hit_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> NewsCluster:
        c = cls.__new__(cls)
        c.id = d["id"]
        c.title = d["title"]
        c.summary = d.get("summary", "")
        c.urls = d.get("urls", [])
        c.sources = d.get("sources", [])
        c.dates = d.get("dates", [])
        c.first_date = d.get("first_date", "")
        c.last_date = d.get("last_date", "")
        c.hit_count = d.get("hit_count", 1)
        return c


# ── 引擎 ──────────────────────────────────────────────────────

class NewsClusterEngine:
    """
    新闻聚类引擎，维护内存 + 文件持久化的事件库。
    """

    def __init__(self, path: str = _CLUSTER_PATH, auto_save: bool = True):
        self._path = path
        self._auto_save = auto_save
        self._clusters: list[NewsCluster] = []
        self._loaded = False

    def _load(self):
        if self._loaded:
            return
        self._loaded = True
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._clusters = [NewsCluster.from_dict(d) for d in data]
            except Exception as e:
                logger.warning("加载 news_clusters.json 失败: %s", e)

    def save(self):
        """保存到文件"""
        if not self._loaded and not self._clusters:
            return
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([c.to_dict() for c in self._clusters],
                          f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("保存 news_clusters.json 失败: %s", e)

    def _make_id(self, title: str) -> str:
        return hashlib.md5(normalize_title(title).encode()).hexdigest()[:16]

    def ingest(self, title: str, summary: str, url: str,
               source: str, date: str) -> NewsCluster:
        """
        摄入一条新闻，返回归属的事件聚类。

        匹配到已有 → 合并并返回
        未匹配到   → 创建新事件并返回
        """
        self._load()

        # 尝试匹配已有事件
        best_idx = -1
        best_score = 0
        for i, cluster in enumerate(self._clusters):
            score = calculate_similarity(title, cluster.title)
            if score > best_score:
                best_score = score
                best_idx = i

        if best_score >= _SIMILARITY_THRESHOLD:
            cluster = self._clusters[best_idx]
            cluster.merge(url, source, date)
            if len(title) > len(cluster.title):
                cluster.title = title
            if summary and len(summary) > len(cluster.summary):
                cluster.summary = summary
            if self._auto_save:
                self.save()
            return cluster
        else:
            cluster_id = self._make_id(title)
            cluster = NewsCluster(cluster_id, title, summary, url, source, date)
            self._clusters.append(cluster)
            if self._auto_save:
                self.save()
            return cluster

    def get_events(self, min_hit: int = 1) -> list[NewsCluster]:
        """获取所有独立事件聚类，按最后发生时间降序"""
        self._load()
        events = [c for c in self._clusters if c.hit_count >= min_hit]
        events.sort(key=lambda c: c.last_date, reverse=True)
        return events

    def to_llm_items(self, min_hit: int = 1) -> list[dict]:
        """将事件聚类转为 LLM 可处理的 dict 列表（替代 raw news）"""
        events = self.get_events(min_hit)
        result = []
        for c in events:
            # 取最新一条 URL 作为主链接
            main_url = ""
            main_source = ""
            if c.urls:
                sorted_urls = sorted(c.urls, key=lambda u: u["date"], reverse=True)
                main_url = sorted_urls[0]["url"]
                main_source = sorted_urls[0]["source"]
            result.append({
                "title": c.title,
                "summary": c.summary,
                "date": c.last_date,
                "url": main_url,
                "source": main_source,
                "cluster_hit_count": c.hit_count,
                "cluster_sources": c.sources,
                "cluster_urls": [u["url"] for u in c.urls],
            })
        return result

    def clear(self):
        """清空所有聚类（用于测试/手动重置）"""
        self._clusters.clear()
        self.save()

    def size(self) -> int:
        self._load()
        return len(self._clusters)
