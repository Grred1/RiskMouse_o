from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

# 将项目根目录加入 path，以便引入 config
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Coze SDK 导入
from coze_coding_dev_sdk import LLMClient
from coze_coding_utils.runtime_ctx.context import new_context
from langchain_core.messages import HumanMessage

CACHE_DIR = os.path.join(_current_dir, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)


# ── 工具函数 ──────────────────────────────────────────

def normalize_symbol(code: str) -> str:
    code = code.strip()
    if code.startswith(("SH", "SZ", "BJ")):
        return code
    if code.startswith(("6", "5")):
        return f"SH{code}"
    elif code.startswith(("0", "3")):
        return f"SZ{code}"
    elif code.startswith(("4", "8")):
        return f"BJ{code}"
    raise ValueError(f"无法识别的股票代码: {code}")


def extract_pure_code(symbol: str) -> str:
    return symbol.strip().upper().lstrip("SH").lstrip("SZ").lstrip("BJ")


def format_num(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    return round(float(val), 2)


def format_pct(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0
    return round(float(val) * 100, 2)


def call_coze(prompt: str, max_tokens: int = 1200) -> str:
    """使用 Coze SDK 调用大语言模型"""
    try:
        ctx = new_context(method="invoke")
        client = LLMClient(ctx=ctx)
        messages = [HumanMessage(content=prompt)]
        response = client.invoke(
            messages=messages,
            temperature=0.7,
            max_completion_tokens=max_tokens,
        )
        # 处理可能的响应格式
        content = response.content
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            if content and isinstance(content[0], str):
                return " ".join(content)
            else:
                text_parts = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
                return " ".join(text_parts)
        return str(content)
    except Exception as e:
        return f"AI 解读请求失败: {str(e)}"
    except Exception as e:
        return f"请求失败: {str(e)}"


# ── 第一步：获取今日涨停列表 ─────────────────────────

def fetch_today_zt_pool() -> pd.DataFrame | None:
    today = datetime.now().strftime("%Y%m%d")
    print(f"正在获取 {today} 涨停数据...")
    try:
        df = ak.stock_zt_pool_em(date=today)
        if df is not None and not df.empty:
            print(f"✅ 获取成功，今日共 {len(df)} 只涨停")
            return df
    except Exception:
        pass
    # 往前回溯，找最近交易日
    for i in range(1, 10):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
        try:
            df = ak.stock_zt_pool_em(date=d)
            if df is not None and not df.empty:
                print(f"✅ 无今日数据，使用最近交易日 {d}，共 {len(df)} 只涨停")
                return df
        except Exception:
            continue
    print("❌ 无法获取涨停数据")
    return None


# ── 第二步：获取主营构成 ─────────────────────────────

def get_zyg_data(code: str) -> list[dict] | None:
    symbol = normalize_symbol(code)
    try:
        df = ak.stock_zygc_em(symbol=symbol)
        if df is None or df.empty:
            return None
        records = []
        for _, row in df.iterrows():
            records.append({
                "报告日期": str(row["报告日期"]),
                "分类类型": str(row["分类类型"]),
                "主营构成": str(row["主营构成"]),
                "主营收入": format_num(row["主营收入"]),
                "收入比例": format_pct(row["收入比例"]),
                "主营利润": format_num(row["主营利润"]),
                "利润比例": format_pct(row["利润比例"]),
                "毛利率": format_pct(row["毛利率"]),
            })
        return records
    except Exception:
        return None


def summarize_zygc(records: list[dict]) -> str:
    lines = []
    report_dates = sorted(set(r["报告日期"] for r in records), reverse=True)
    latest = report_dates[0] if report_dates else "未知"
    lines.append(f"最新报告期: {latest}")

    for cat_type in ("按行业分类", "按产品分类"):
        items = [
            r for r in records
            if r["报告日期"] == latest and r["分类类型"] == cat_type
        ]
        if items:
            lines.append(f"\n{cat_type}:")
            for item in sorted(items, key=lambda x: x["收入比例"], reverse=True):
                lines.append(
                    f"  {item['主营构成']}: 收入占比 {item['收入比例']}%, "
                    f"毛利率 {item['毛利率']}%"
                )
    return "\n".join(lines)


# ── 第三步：搜索上涨逻辑（这里由用户自行搜索后提供，预留接口） ──
# 由于搜索需要手动处理，这里返回占位结构，供用户补充

BOARD_LOGICS: dict[str, list[str]] = {}


def set_board_logics(logics: dict[str, list[str]]):
    global BOARD_LOGICS
    BOARD_LOGICS.update(logics)


# ── 第四步：调用 AI 做风险评估 ───────────────────────

RISK_PROMPT_TPL = """你是一位专业的证券分析师。请对以下二板涨停股票进行**全面的风险评估**，结合其主营业务基本面和市场炒作逻辑，给出客观的风险提示。

======== 股票基本信息 ========
名称: {name}({code})
连板数: {board}连板
所属行业: {industry}

======== 主营构成（最新报告期） ========
{zygc}

======== 市场上涨逻辑（网络搜集） ========
{logic}

======== 分析要求 ========
请从以下几个维度进行风险评估（600字以内）：

1. **基本面风险**：主营业务的盈利能力、成长性、可持续性如何？是否有隐忧？
2. **炒作逻辑风险**：市场炒作的逻辑是否扎实？是否有被证伪的可能？
3. **估值风险**：连续大涨后估值是否合理？是否存在泡沫？
4. **资金面风险**：封板力度、换手率、炸板情况等反映的资金博弈状况
5. **综合风险评级**：给出 低风险/中低风险/中高风险/高风险 评级，并给出简要理由

请务必客观中立，不构成投资建议，仅为风险分析参考。"""


def analyze_risk(
    code: str,
    name: str,
    board: int,
    industry: str,
    zygc_summary: str,
    logic_lines: list[str],
) -> str:
    prompt = RISK_PROMPT_TPL.format(
        name=name,
        code=code,
        board=board,
        industry=industry,
        zygc=zygc_summary,
        logic="\n".join(f"{i+1}. {line}" for i, line in enumerate(logic_lines)),
    )
    return call_coze(prompt, max_tokens=1200)


# ── 主流程 ────────────────────────────────────────────

def run_analysis(board_logics: dict[str, list[str]] | None = None):
    set_board_logics(board_logics or {})

    # 1. 获取涨停池
    df = fetch_today_zt_pool()
    if df is None:
        return

    # 2. 筛选二板以上
    zt_pool = df.to_dict("records")
    multi_board = [s for s in zt_pool if int(s.get("连板数", 0)) >= 2]

    if not multi_board:
        print("\n今日无二板以上股票")
        return

    print(f"\n📊 二板以上股票共 {len(multi_board)} 只:")
    print(f"{'代码':<8} {'名称':<8} {'连板数':<6} {'行业':<12}")
    print("-" * 40)
    for s in multi_board:
        print(f"{s['代码']:<8} {s['名称']:<8} {s['连板数']:<6} {s['所属行业']:<12}")

    # 3. 逐只分析
    results = []
    for s in multi_board:
        code = str(s["代码"]).strip().zfill(6)
        name = s["名称"]
        board = int(s["连板数"])
        industry = s["所属行业"]

        print(f"\n{'='*70}")
        print(f"📌 {name}({code}) — {board}连板 — {industry}")
        print(f"{'='*70}")

        # 主营构成
        print("  正在获取主营构成...")
        recs = get_zyg_data(code)
        if recs:
            zygc_summary = summarize_zygc(recs)
            print(f"  ✅ 主营构成获取成功")
            print(f"  {zygc_summary.replace(chr(10), chr(10)+'  ')}")
        else:
            zygc_summary = "未获取到主营构成数据"
            print(f"  ⚠️ 未获取到主营构成数据")

        # 上涨逻辑
        logic = BOARD_LOGICS.get(code, ["（无网络搜索数据，待补充）"])
        print(f"\n  上涨逻辑:")
        for line in logic:
            print(f"    • {line}")

        # AI 风险分析
        print(f"\n  🤖 AI 风险分析中...")
        analysis = analyze_risk(
            code=code,
            name=name,
            board=board,
            industry=industry,
            zygc_summary=zygc_summary,
            logic_lines=logic,
        )
        print(f"\n{analysis}")

        results.append({
            "code": code,
            "name": name,
            "board": board,
            "industry": industry,
            "zygc": zygc_summary,
            "logic": logic,
            "ai_risk_analysis": analysis,
        })

    # 4. 保存结果
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(CACHE_DIR, f"zt_board_analysis_{timestamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_zt": len(zt_pool),
                "total_multi_board": len(multi_board),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"\n{'='*70}")
    print(f"✅ 分析完成！结果已保存至: {out_path}")
    print(f"{'='*70}")

    return results


# ── 命令行入口 ────────────────────────────────────────

if __name__ == "__main__":
    # 这里预填今日搜集到的上涨逻辑（每天运行前可手动更新）
    default_logics = {
        "300069": [
            "跨界收购商业航天标的(中科西光82.5%股权)，涉足高光谱遥感卫星领域，开辟第二增长曲线",
            "核心玻璃绝缘子业务受益特高压电网投资，浙江扩产已投产，山西新项目预计2026年投产，总产能翻倍",
            "2026年5月20日发布非公开增发预案，拟向控股股东等募资",
            "2026年Q1业绩扭亏为盈(净利润303.96万)",
            "停牌前股价已连续7日上涨，4月涨幅45.16%，存在内幕消息泄露嫌疑",
            "标的公司中科西光2024年营收仅888万，2025年营收4915万，体量较小，业绩存不确定性",
        ],
        "603779": [
            "淄博国资入主: 齐信数科(淄博财政局)以股抵债方式受让23.12%股份，成为控股股东",
            "国资承诺36个月不减持，带来信用背书和资金支持",
            "产品结构升级，有机葡萄酒占营收超6成，布局白兰地新品类",
            "获批银行综合授信，短期资金压力缓解",
            "公司已连亏: 2025年营收3.63亿(-18.36%)，净亏0.63亿；2026Q1再亏749.94万(-186.05%)",
            "公司紧急辟谣: 无算力资产注入计划，市值严重偏离行业(市净率9.84 vs 行业3.98)",
            "国资入主尚需多项审批，实控人涉案、股份冻结存在重大不确定性",
            "7天暴涨94.9%，换手率42.63%，纯情绪炒作风险极高",
        ],
        "000518": [
            "2026年5月20日起撤销退市风险警示(摘帽)，由*ST四环变更为四环生物",
            "摘帽条件靠的是绿化工程业务营收暴增(2025年苗木营收1.59亿，同比增长近38倍)，而非医药主业回暖",
            "2025年全年营收3.44亿(+69.22%)，刚过3亿摘帽门槛",
            "医药业务(EPO、G-CSF等)毛利率高但营收占比仅53.65%",
            "绿化工程毛利率极低(苗木3.55%)，可持续性存疑",
            "公司曾因内部控制问题被出具否定意见审计报告，治理风险仍需关注",
        ],
        "600611": [
            "'两翼四柱'战略转型，数智交通+数据算力业务占比超70%",
            "特斯拉FSD入华催化无人驾驶/智能网联板块情绪",
            "参股基金间接持有长江存储约0.051%股份，长江存储IPO辅导备案引发关注",
            "与百度智行联合获智能网联汽车示范运营牌照，萝卜快跑在浦东落地",
            "经营性现金流9.78亿(+17.4%)，流动性充裕",
            "累计获45亿债务融资注册额度，已发行6亿低成本债券",
            "2026Q1归母净利润-1.66亿(-360.62%)，业绩大幅下滑",
            "交通运输主业毛利率仅11.71%，盈利能力较弱",
        ],
        "002442": [
            "炭黑行业景气度回升，90天内炭黑价格涨6.32%、白炭黑涨3.70%",
            "全国产能布局完成，总产能居行业前三，高端新产品产值率达78%",
            "董事长刘鹏达5月15日增持164.81万股，真金白银彰显信心",
            "2025年经营现金流由负转正超2亿元，资产负债率下降",
            "绿色转型契合政策导向，PVDF概念、新能源车概念加持",
            "炭黑毛利率仅4.99%，主业盈利能力极弱，对价格波动敏感",
            "连续两日涨幅偏离值超20%，已发布股价异动公告",
        ],
        "603316": [
            "从传统生态环境成功转型'生态+半导体存储'双主业，半导体营收占比67.25%",
            "半导体存储业务收入同比增长超200%，转型落地超预期",
            "近1亿元定增募资落地，用于嵌入式存储芯片扩产",
            "2026年Q1营收翻倍、扭亏为盈",
            "长江存储、长鑫科技IPO加速，国产替代情绪升温，半导体存储板块联动",
            "转型前曾连续亏损，对外担保规模大",
            "环境建设业务毛利率-10.61%仍在拖累整体盈利",
            "存储业务毛利率14.91%偏低，在半导体行业中竞争力待观察",
        ],
    }

    run_analysis(board_logics=default_logics)
