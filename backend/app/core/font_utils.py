"""
中文字体智能查找工具
查找优先级：matplotlib font_manager → 系统已知路径 → 自动下载缓存
"""
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 项目内嵌字体目录
FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fonts")

# 跨平台已知中文字体路径（备选）
SYSTEM_FONT_PATHS = [
    # macOS
    "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    # Linux (常见发行版)
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]

# matplotlib 中文字体名称关键词（按优先级排序）
MATPLOTLIB_CHINESE_NAMES = [
    "PingFang SC", "PingFang HK", "PingFang",
    "Heiti TC", "Heiti SC", "STHeiti",
    "Microsoft YaHei", "Microsoft YaHei UI",
    "SimHei", "Noto Sans CJK SC", "Noto Sans CJK",
    "Noto Sans SC", "Source Han Sans CN", "Source Han Sans SC",
    "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
    "AR PL UMing CN", "AR PL UKai CN",
    "Droid Sans Fallback",
]


def find_chinese_font() -> Optional[str]:
    """查找可用的中文字体路径，返回 None 表示未找到"""

    # 1. 检查项目内嵌字体目录
    if os.path.isdir(FONTS_DIR):
        for fname in sorted(os.listdir(FONTS_DIR)):
            if fname.endswith((".ttf", ".ttc", ".otf")):
                fp = os.path.join(FONTS_DIR, fname)
                logger.info("使用项目内嵌字体: %s (%dKB)", fname, os.path.getsize(fp) // 1024)
                return fp

    # 2. matplotlib font_manager 精确查找
    try:
        import matplotlib.font_manager as fm
        for name in MATPLOTLIB_CHINESE_NAMES:
            try:
                fp = fm.findfont(name, fallback_to_default=False)
                if fp and os.path.exists(fp) and os.path.getsize(fp) > 10000:
                    logger.info("matplotlib 找到字体: %s -> %s (%dKB)",
                                name, fp, os.path.getsize(fp) // 1024)
                    return fp
            except Exception:
                continue

        # 遍历所有字体，模糊匹配
        for font in fm.fontManager.ttflist:
            for name in MATPLOTLIB_CHINESE_NAMES:
                if name.lower() in font.name.lower():
                    if os.path.exists(font.fname) and os.path.getsize(font.fname) > 10000:
                        logger.info("matplotlib 模糊匹配字体: %s -> %s", font.name, font.fname)
                        return font.fname
    except Exception as e:
        logger.warning("matplotlib font_manager 查找失败: %s", e)

    # 3. 硬编码系统路径
    for path in SYSTEM_FONT_PATHS:
        if os.path.exists(path):
            logger.info("系统路径找到字体: %s", path)
            return path

    # 4. 尝试自动下载并缓存
    try:
        fp = _download_and_cache_font()
        if fp:
            return fp
    except Exception as e:
        logger.warning("自动下载字体失败: %s", e)

    logger.warning("未找到任何中文字体，词云中文将无法正常显示")
    return None


def _download_and_cache_font() -> Optional[str]:
    """尝试从 CDN 下载中文字体并缓存到 fonts 目录"""
    import requests

    os.makedirs(FONTS_DIR, exist_ok=True)

    urls = [
        ("https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf", "NotoSansSC-Regular.otf"),
        ("https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf", "NotoSansSC-Regular.otf"),
        ("https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf", "NotoSansSC-Regular.otf"),
    ]

    for url, fname in urls:
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 200 and len(r.content) > 500000:
                dst = os.path.join(FONTS_DIR, fname)
                with open(dst, "wb") as f:
                    f.write(r.content)
                logger.info("自动下载字体成功: %s (%dKB)", fname, len(r.content) // 1024)
                return dst
        except Exception:
            continue

    return None
