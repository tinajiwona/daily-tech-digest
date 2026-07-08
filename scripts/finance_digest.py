#!/usr/bin/env python3
"""
每日财经简报生成器
整合全球财经媒体 RSS 源，使用 OpenAI 或 Claude/GLM 生成简报
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import feedparser
import pytz
import requests
from bs4 import BeautifulSoup


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    """加载配置文件"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_rss_feeds(config: dict) -> list[dict]:
    """获取 RSS 源内容"""
    feeds_config = config["rss_feeds"]
    result = []

    def fetch_single_feed(name, feed_info):
        try:
            response = requests.get(
                feed_info["url"],
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; DailyFinanceDigest/1.0; +https://github.com/tinajiwona/daily-tech-digest)"
                },
                timeout=20,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            items = []
            for entry in feed.entries[:15]:  # 每个源最多15条
                items.append({
                    "title": entry.get("title", ""),
                    "url": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "summary": BeautifulSoup(
                        entry.get("summary", "")[:300], "html.parser"
                    ).get_text()[:200],
                    "source": feed_info["name"],
                    "category": feed_info["category"]
                })
            return items
        except Exception as e:
            print(f"[警告] RSS {name} 抓取失败: {e}")
            return []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_single_feed, name, info): name
            for name, info in feeds_config.items()
        }
        for future in as_completed(futures):
            items = future.result()
            result.extend(items)

    return result


def format_money(value) -> str:
    """格式化金额，尽量兼容 akshare 返回的字符串或数字。"""
    if value in (None, ""):
        return "未知"

    if isinstance(value, str):
        return value

    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)

    if math.isnan(number):
        return "未知"

    if abs(number) >= 100000000:
        return f"{number / 100000000:.2f}亿"
    if abs(number) >= 10000:
        return f"{number / 10000:.2f}万"
    return f"{number:.2f}"


def parse_number(value) -> Optional[float]:
    """把 akshare 返回的数字、百分比或金额字符串转成 float。"""
    if value in (None, ""):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        return None if math.isnan(number) else number

    text = str(value).strip().replace(",", "")
    if not text or text.lower() == "nan":
        return None

    multiplier = 1.0
    if text.endswith("亿"):
        multiplier = 100000000.0
        text = text[:-1]
    elif text.endswith("万"):
        multiplier = 10000.0
        text = text[:-1]
    if text.endswith("%"):
        text = text[:-1]

    try:
        number = float(text) * multiplier
        return None if math.isnan(number) else number
    except ValueError:
        return None


def format_percent(value) -> str:
    number = parse_number(value)
    if number is None:
        return str(value) if value not in (None, "") else "未知"
    return f"{number:.2f}%"


def eastmoney_market_prefix(code: str) -> str:
    """东方财富个股链接使用 sh/sz/bj 前缀。"""
    if not code:
        return ""
    if code.startswith(("6", "9")):
        return "sh"
    if code.startswith(("0", "2", "3")):
        return "sz"
    if code.startswith(("4", "8")):
        return "bj"
    return ""


def eastmoney_stock_url(code: str) -> str:
    prefix = eastmoney_market_prefix(code)
    if not prefix or not code:
        return ""
    return f"https://quote.eastmoney.com/{prefix}{code}.html"


def first_existing(row, names: list[str], default=""):
    """从 pandas row 中读取第一个存在的字段。"""
    for name in names:
        if name in row:
            value = row[name]
            if value is not None and str(value) != "nan":
                return value
    return default


def normalize_sector_rows(df, source: str) -> list[dict]:
    """规范化 akshare 板块资金流 DataFrame。"""
    rows = []
    if df is None or df.empty:
        return rows

    for _, row in df.iterrows():
        name = first_existing(row, ["名称", "板块名称", "行业", "概念"], "未知板块")
        change = first_existing(row, ["今日涨跌幅", "涨跌幅", "最新涨跌幅"], "未知")
        main_net = first_existing(
            row,
            ["今日主力净流入-净额", "主力净流入-净额", "主力净流入", "净额", "资金净流入"],
            "",
        )
        super_net = first_existing(
            row,
            ["今日超大单净流入-净额", "超大单净流入-净额", "超大单净流入"],
            "",
        )
        big_net = first_existing(
            row,
            ["今日大单净流入-净额", "大单净流入-净额", "大单净流入"],
            "",
        )
        medium_net = first_existing(
            row,
            ["今日中单净流入-净额", "中单净流入-净额", "中单净流入"],
            "",
        )
        small_net = first_existing(
            row,
            ["今日小单净流入-净额", "小单净流入-净额", "小单净流入"],
            "",
        )

        rows.append(
            {
                "source": source,
                "name": str(name),
                "change": format_percent(change),
                "change_raw": parse_number(change),
                "main_net": format_money(main_net),
                "main_net_raw": parse_number(main_net),
                "super_net": format_money(super_net),
                "super_net_raw": parse_number(super_net),
                "big_net": format_money(big_net),
                "big_net_raw": parse_number(big_net),
                "medium_net": format_money(medium_net),
                "medium_net_raw": parse_number(medium_net),
                "small_net": format_money(small_net),
                "small_net_raw": parse_number(small_net),
            }
        )

    return rows


def select_extreme_sector_rows(rows: list[dict], limit: int) -> list[dict]:
    """保留净流入和净流出两端，避免只看到上涨或只看到下跌。"""
    valid_rows = [row for row in rows if row.get("main_net_raw") is not None]
    if not valid_rows:
        return rows[:limit]

    half = max(1, limit // 2)
    positive = sorted(valid_rows, key=lambda x: x["main_net_raw"], reverse=True)[:half]
    negative = sorted(valid_rows, key=lambda x: x["main_net_raw"])[: limit - len(positive)]
    seen = set()
    selected = []
    for row in positive + negative:
        key = (row["source"], row["name"])
        if key in seen:
            continue
        seen.add(key)
        selected.append(row)
    return selected


def fetch_sector_fund_flow(config: dict) -> dict:
    """抓取 A 股行业/概念板块资金流向。"""
    sector_config = config.get("sector_fund_flow", {})
    if not sector_config.get("enabled", True):
        return {"industry": [], "concept": []}

    try:
        import akshare as ak
    except Exception as exc:
        print(f"[警告] akshare 不可用，跳过板块资金流抓取: {exc}")
        return {"industry": [], "concept": []}

    indicator = sector_config.get("indicator", "今日")
    limit = int(sector_config.get("limit", 12))
    result = {"industry": [], "concept": [], "industry_all": [], "concept_all": []}

    targets = [
        ("industry", "行业资金流", "行业板块"),
        ("concept", "概念资金流", "概念板块"),
    ]

    for key, sector_type, label in targets:
        try:
            df = ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)
            rows = normalize_sector_rows(df, label)
            result[f"{key}_all"] = rows
            result[key] = select_extreme_sector_rows(rows, limit)
            print(f"[完成] 获取 {label} 资金流 {len(result[key])} 条")
        except Exception as exc:
            print(f"[警告] {label}资金流抓取失败: {exc}")

    return result


def match_watchlist_sectors(config: dict, sector_data: dict) -> list[dict]:
    """把配置的重点赛道和板块资金流做模糊匹配。"""
    all_rows = (
        sector_data.get("industry_all")
        or sector_data.get("industry", [])
    ) + (
        sector_data.get("concept_all")
        or sector_data.get("concept", [])
    )

    report = []
    for item in config.get("sector_watchlist", []):
        aliases = [item.get("name", ""), *item.get("aliases", [])]
        matches = []
        for row in all_rows:
            row_name = row.get("name", "")
            if any(alias and (alias.lower() in row_name.lower() or row_name.lower() in alias.lower()) for alias in aliases):
                matches.append(row)
        matches.sort(key=lambda x: abs(x.get("main_net_raw") or 0), reverse=True)
        report.append(
            {
                "name": item.get("name", ""),
                "aliases": item.get("aliases", []),
                "leaders": item.get("leaders", []),
                "matches": matches[:5],
                "leader_quotes": [],
            }
        )

    return report


def normalize_stock_spot_row(row) -> dict:
    name = first_existing(row, ["名称", "股票简称"], "")
    code = first_existing(row, ["代码", "股票代码"], "")
    price = first_existing(row, ["最新价", "最新", "现价"], "")
    change = first_existing(row, ["涨跌幅", "涨幅"], "")
    amount = first_existing(row, ["成交额"], "")
    market_value = first_existing(row, ["总市值", "流通市值"], "")
    turnover = first_existing(row, ["换手率"], "")
    pe = first_existing(row, ["市盈率-动态", "市盈率", "动态市盈率"], "")

    return {
        "name": str(name),
        "code": str(code),
        "url": eastmoney_stock_url(str(code)),
        "price": str(price) if price not in (None, "") else "未知",
        "change": format_percent(change),
        "change_raw": parse_number(change),
        "amount": format_money(amount),
        "market_value": format_money(market_value),
        "turnover": format_percent(turnover),
        "pe": str(pe) if pe not in (None, "") else "未知",
        "trade_date": "实时/最新",
    }


def normalize_history_row(row, fallback: dict) -> dict:
    close = first_existing(row, ["收盘", "收盘价"], fallback.get("price", "未知"))
    change = first_existing(row, ["涨跌幅"], fallback.get("change", "未知"))
    amount = first_existing(row, ["成交额"], fallback.get("amount", "未知"))
    turnover = first_existing(row, ["换手率"], fallback.get("turnover", "未知"))
    trade_date = first_existing(row, ["日期"], "前一交易日")

    return {
        **fallback,
        "price": str(close) if close not in (None, "") else fallback.get("price", "未知"),
        "change": format_percent(change),
        "change_raw": parse_number(change),
        "amount": format_money(amount),
        "turnover": format_percent(turnover),
        "trade_date": str(trade_date),
    }


def fetch_previous_daily_quote(ak, quote: dict, today: str) -> dict:
    """从日线中取早于今天的最近一个交易日，避免盘中价格扰动。"""
    code = quote.get("code", "")
    if not code:
        return quote

    try:
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="")
    except Exception as exc:
        print(f"[警告] {quote.get('name', code)} 前一交易日日线抓取失败: {exc}")
        return quote

    if df is None or df.empty:
        return quote

    rows = []
    for _, row in df.iterrows():
        date_value = first_existing(row, ["日期"], "")
        if date_value and str(date_value) < today:
            rows.append(row)

    if not rows:
        return quote

    return normalize_history_row(rows[-1], quote)


def fetch_leader_stock_quotes(config: dict) -> dict:
    """抓取重点赛道龙头股的前一交易日行情，并附上东方财富链接。"""
    if not config.get("leader_stock_snapshot", {}).get("enabled", True):
        return {}

    names = []
    for item in config.get("sector_watchlist", []):
        names.extend(item.get("leaders", []))
    names = sorted(set(names))
    if not names:
        return {}

    try:
        import akshare as ak
    except Exception as exc:
        print(f"[警告] akshare 不可用，跳过龙头股行情抓取: {exc}")
        return {}

    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as exc:
        print(f"[警告] 龙头股行情抓取失败: {exc}")
        return {}

    today = datetime.now(pytz.timezone("Asia/Shanghai")).strftime("%Y-%m-%d")
    quotes = {}
    for _, row in df.iterrows():
        quote = normalize_stock_spot_row(row)
        if quote["name"] in names:
            quotes[quote["name"]] = fetch_previous_daily_quote(ak, quote, today)

    print(f"[完成] 获取重点龙头股行情 {len(quotes)}/{len(names)} 条")
    return quotes


def attach_leader_quotes(watchlist_report: list[dict], leader_quotes: dict) -> list[dict]:
    for item in watchlist_report:
        item["leader_quotes"] = [
            leader_quotes.get(name)
            or {
                "name": name,
                "code": "",
                "url": "",
                "price": "未匹配",
                "change": "未知",
                "amount": "未知",
                "market_value": "未知",
                "turnover": "未知",
                "pe": "未知",
                "trade_date": "未知",
            }
            for name in item.get("leaders", [])
        ]
    return watchlist_report


def render_watchlist_report(watchlist_report: list[dict], data_label: str = "") -> str:
    if not watchlist_report:
        return "## 重点赛道跟踪\n- 暂无配置"

    header = "## 重点赛道跟踪（必须逐项覆盖）"
    if data_label:
        header += f"\n- 数据口径: {data_label}"
    sections = [header]
    for item in watchlist_report:
        lines = [f"### {item['name']}"]
        if item.get("matches"):
            for match in item["matches"]:
                lines.append(
                    f"- 板块资金: {match['source']} / {match['name']} | 涨跌幅: {match['change']} | 主力: {match['main_net']} | 超大单: {match['super_net']} | 大单: {match['big_net']} | 中单: {match['medium_net']} | 小单: {match['small_net']}"
                )
        else:
            aliases = "、".join(item.get("aliases", []))
            lines.append(f"- 板块资金: 暂未匹配到同名板块资金流；可用关键词继续人工核对: {aliases}")

        if item.get("leader_quotes"):
            leader_lines = []
            for quote in item["leader_quotes"]:
                stock_name = quote["name"]
                if quote.get("url"):
                    stock_name = f"[{stock_name}]({quote['url']})"
                leader_lines.append(
                    f"{stock_name}({quote.get('code', '')}) 日期:{quote.get('trade_date', '前一交易日')} 收盘:{quote['price']} 涨跌幅:{quote['change']} 成交额:{quote['amount']} 换手率:{quote['turnover']} PE:{quote.get('pe', '未知')}"
                )
            lines.append("- 龙头股前一交易日数据与链接: " + "；".join(leader_lines))

        lines.append("- 输出要求: 写清细分流向、前一交易日龙头表现、利好、利空、短线观察信号，不允许省略该赛道。")
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


def render_sector_fund_flow(sector_data: dict) -> str:
    """把板块资金流数据渲染给 AI。"""
    sections = []
    for key, title in [("industry", "行业板块资金流"), ("concept", "概念板块资金流")]:
        rows = sector_data.get(key, [])
        if not rows:
            sections.append(f"## {title}\n- 暂无可用数据")
            continue

        lines = []
        for index, item in enumerate(rows, start=1):
            lines.append(
                f"{index}. {item['name']} | 涨跌幅: {item['change']} | 主力: {item['main_net']} | 超大单: {item['super_net']} | 大单: {item['big_net']} | 中单: {item['medium_net']} | 小单: {item['small_net']}"
            )
        sections.append(f"## {title}\n" + "\n".join(lines))

    return "\n\n".join(sections)


def build_fallback_content(config: dict) -> str:
    """RSS 源暂不可用时仍生成一份可发布到网站的简报。"""
    sources = []
    for feed_info in config["rss_feeds"].values():
        sources.append(
            f"- [{feed_info['name']}]({feed_info['url']}) [{feed_info['category']}]"
        )

    return "\n".join(
        [
            "## 数据源状态",
            "今日 GitHub Actions 运行时未能稳定抓取 RSS 条目。请生成一份简短的财经监控简报，明确说明数据源暂不可用，并提醒读者以正式市场数据为准。",
            "",
            "## 已配置数据源",
            *sources,
        ]
    )


def prepare_content_for_ai(config: dict, rss: list, sector_data: dict = None, watchlist_report: list[dict] = None) -> str:
    """准备发送给 AI 的内容"""
    sections = []

    if sector_data:
        sections.append(render_sector_fund_flow(sector_data))

    if watchlist_report:
        data_label = config.get("sector_fund_flow", {}).get("display_label", "")
        sections.append(render_watchlist_report(watchlist_report, data_label))

    # RSS 部分 - 按分类分组
    if rss:
        by_category = {}
        for item in rss:
            cat = item.get("category", "其他")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(item)

        for cat, items in by_category.items():
            cat_items = []
            for item in items[:10]:  # 每分类最多10条
                cat_items.append(f"- [{item['title']}]({item['url']}) [{item['source']}]")
            sections.append(f"## {cat}\n" + "\n".join(cat_items))

    return "\n\n".join(sections)


def get_anthropic_api_key() -> str:
    """获取 Anthropic/智谱兼容 API Key, 兼容多种环境变量名称"""
    api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("请设置 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY 环境变量")
    return api_key


def build_digest_prompt(content: str, today: str) -> str:
    """财经简报专属 Prompt"""
    return f"""你是一位资深财经编辑，需要根据以下原始内容生成一份精炼的中文财经简报。

今天日期: {today}

原始内容:
{content}

## 生成要求:

### 1. 热点筛选标准
优先选择符合以下特征的内容:
- **高影响力**: 影响股市、债市、商品市场或政策方向
- **大众关切**: 普通投资者和公众关心的话题
- **传播性强**: 具有话题性、争议性或突破性
- **时效性强**: 24小时内的最新动态

### 2. 板块结构（严格按以下顺序）

**🔥 今日热点（5条）**
- 从所有来源中筛选最重要、最受关注的5条
- 每条包含: 标题 + 链接 + **看点**（为什么重要 + 影响）
- 看点控制在50字内

**📈 市场动态（3-5条）**
- **必须包含A股**（放在首位），其次是港股、美股
- A股部分: 上证指数、深证成指、创业板指、热门板块
- 热门板块建议: 新能源、半导体、消费、医药、金融地产
- 大宗商品: 黄金、原油、铜、锂电池相关
- **每条必须包含**: [标题](链接) + **数据 + 变化幅度 + 点评**
- 点评要说明对普通投资者的意义
- 每条至少150字

**🎯 重点赛道资金雷达（必须重点写，合并“板块资金流向”和“赛道雷达”）**
- 必须覆盖原始内容中“重点赛道跟踪”的每一个赛道，尤其是: 存储芯片、CPO、PCB、先进封装、光纤光缆、MLCC、大科技、海外基建/出海链
- 不要再单独生成“今日板块资金流向”或“重点赛道雷达”两个重复板块，本节就是板块资金流向分析
- 数据口径说明必须写清楚: 板块资金来自东方财富/AkShare 最新可得资金流；龙头股使用“前一交易日/最近收盘”数据，并提供东方财富链接，实时价格读者可点链接查看
- 每个赛道必须按以下格式写:
  - **赛道**:
  - **细分资金流向**: 匹配到的板块名称、涨跌幅、主力、超大单、大单、中单、小单；如果暂未匹配，写“暂未匹配到同名板块资金流”，并列出可人工核对关键词，不能直接跳过
  - **龙头股前一交易日**: 列出配置里的龙头股，必须保留股票链接，写收盘价、涨跌幅、成交额、换手率、PE/估值字段
  - **今日事件/催化**: 从新闻、政策、产业趋势、订单、价格、海外映射中提炼1-2条；如果原始新闻没有直接证据，要标注“待验证”
  - **利空/风险**: 资金流出、涨幅过大、业绩兑现、海外政策、供应链、估值、监管等
  - **明日盯盘信号**: 1-2个可观察指标，例如板块资金是否回流、龙头是否放量、估值是否过热、海外映射是否延续
- 不要编造开盘价、收盘价或实时价格；原始内容没有的数据必须写“暂无”

**💰 宏观与政策（3条）**
- 央行政策、财政政策、金融监管
- **每条必须包含**: [标题](链接) + **政策内容 + 背景 + 影响分析**
- 说明政策对普通人钱包的影响
- 每条至少150字

**🏢 行业观察（3条）**
- 特定行业动态、龙头企业、行业数据
- **每条必须包含**: [标题](链接) + **行业动态 + 数据支撑 + 影响分析**
- 说明对投资者和消费者的意义
- 每条至少150字

**🌍 国际视野（2-3条）**
- 美联储、欧央行政策
- 国际大宗商品价格
- 全球经济数据
- **每条必须包含**: [标题](链接) + **事件描述 + 影响分析**
- 说明对国内市场和普通人的影响
- 每条至少150字

**💡 投资洞察（2条）**
- 知名机构或投资者观点
- 券商研报核心观点
- **每条必须包含**: [标题](链接) + **观点内容 + 出处 + 投资建议**
- 说明为什么值得参考
- 每条至少150字

**⚡ 明日板块观察清单（5条）**
- 输出5个明天最值得盯盘的板块
- 每条包含: 触发因素 + 观察指标 + 偏利好/偏利空/中性
- 只做信息跟踪，不给买卖建议

**🎯 选题灵感（3-5条）**
为财经博主推荐选题方向:
- **选题类型**: "选题标题"
  - 理由: 为什么适合做内容
  - 切入点: 从哪个角度写更容易火

选题类型: 深度选题、热点解读、数据解读、投资教育、行业分析

**📚 延伸阅读（5条）**
- 深度分析文章
- 保留原始链接

### 3. 风险提示（必须包含）
```
⚠️ **风险提示**: 本简报仅供参考，不构成投资建议。市场有风险，投资需谨慎。
```

### 4. 语言风格
- 专业性与可读性平衡
- **每条内容控制在150-200字**
- 数据导向，多用具体数字和案例
- 中立客观，但要有明确观点
- 深入分析，避免泛泛而谈

### 5. 格式要求
- 使用Markdown格式
- 导语100字以内，概括当日核心主题
- **所有内容板块（除选题灵感外）必须附上原始链接**
- 总长度控制在3500-5000字
- 使用加粗、列表等方式提升可读性

直接输出简报内容，不需要额外说明。"""


def generate_digest_with_anthropic(content: str, config: dict, today: str) -> str:
    """使用 Claude/GLM 生成财经简报"""
    import anthropic

    api_key = get_anthropic_api_key()
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    client = (
        anthropic.Anthropic(api_key=api_key, base_url=base_url)
        if base_url
        else anthropic.Anthropic(api_key=api_key)
    )
    prompt = build_digest_prompt(content, today)

    message = client.messages.create(
        model=config["claude"]["model"],
        max_tokens=config["claude"]["max_tokens"],
        temperature=config.get("claude", {}).get("temperature", 0.3),
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return message.content[0].text


def extract_openai_text(payload: dict) -> str:
    """兼容 Responses API 的文本提取。"""
    if payload.get("output_text"):
        return payload["output_text"]

    chunks = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                chunks.append(content["text"])

    return "\n".join(chunks).strip()


def generate_digest_with_openai(content: str, config: dict, today: str) -> str:
    """使用 OpenAI Responses API 生成财经简报。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("请设置 OPENAI_API_KEY 环境变量")

    openai_config = config.get("openai", {})
    model = os.environ.get("OPENAI_MODEL") or openai_config.get("model", "gpt-4.1-mini")
    max_tokens = int(openai_config.get("max_output_tokens", config["claude"]["max_tokens"]))
    temperature = float(openai_config.get("temperature", config["claude"].get("temperature", 0.3)))
    timeout_seconds = int(openai_config.get("timeout_seconds", 300))
    prompt = build_digest_prompt(content, today)

    print(f"[信息] 调用 OpenAI: model={model}, max_output_tokens={max_tokens}, timeout={timeout_seconds}s")
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "max_output_tokens": max_tokens,
                "temperature": temperature,
                "input": [
                    {
                        "role": "developer",
                        "content": "你是资深财经编辑。请严格按用户要求输出中文 Markdown 财经简报。",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
            },
            timeout=timeout_seconds,
        )
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(f"OpenAI API 请求超时（{timeout_seconds}s），可以调低 OPENAI_MODEL 或 max_output_tokens 后重试。") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"OpenAI API 返回了非 JSON 响应，HTTP {response.status_code}") from exc
    if not response.ok:
        message = payload.get("error", {}).get("message", "OpenAI API 请求失败")
        raise RuntimeError(message)

    text = extract_openai_text(payload)
    if not text:
        raise RuntimeError("OpenAI API 没有返回可用文本")

    print(f"[信息] 已使用 OpenAI 模型生成: {model}")
    return text


def generate_digest(content: str, config: dict, today: str) -> str:
    """优先使用 OpenAI；未配置时回退到 Claude/GLM 兼容接口。"""
    if os.environ.get("OPENAI_API_KEY"):
        return generate_digest_with_openai(content, config, today)

    print("[信息] 未检测到 OPENAI_API_KEY，回退到 Anthropic/GLM 兼容接口")
    return generate_digest_with_anthropic(content, config, today)


def save_digest(content: str, config: dict, today: str):
    """保存简报文件"""
    digests_dir = PROJECT_ROOT / config["output"]["digests_dir"]
    digests_dir.mkdir(exist_ok=True)

    # 保存日期文件
    date_file = digests_dir / f"{today}.md"
    with open(date_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[完成] 已保存: {date_file}")

    # 更新 latest.md
    latest_file = digests_dir / "latest.md"
    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[完成] 已更新: {latest_file}")


def main():
    """主函数"""
    print("=" * 50)
    print("每日财经简报生成器")
    print("=" * 50)

    # 加载配置
    config = load_config()

    # 获取北京时间日期
    tz = pytz.timezone("Asia/Shanghai")
    today = datetime.now(tz).strftime(config["output"]["date_format"])
    print(f"\n日期: {today}")

    # 抓取数据
    print("\n[1/4] 正在抓取财经媒体 RSS 源...")
    rss = fetch_rss_feeds(config)
    print(f"      获取 {len(rss)} 条")

    print("\n[2/4] 正在抓取 A 股板块资金流...")
    sector_data = fetch_sector_fund_flow(config)
    sector_count = len(sector_data.get("industry", [])) + len(sector_data.get("concept", []))
    print(f"      获取 {sector_count} 条板块资金流")

    print("\n[3/4] 正在匹配重点赛道和龙头股...")
    watchlist_report = match_watchlist_sectors(config, sector_data)
    leader_quotes = fetch_leader_stock_quotes(config)
    watchlist_report = attach_leader_quotes(watchlist_report, leader_quotes)
    print(f"      跟踪 {len(watchlist_report)} 个重点赛道")

    # 检查是否有内容
    if not rss and not sector_count:
        print("\n[警告] 未获取到任何 RSS 和板块资金流内容，将使用兜底内容生成简报，确保网站更新链路可验证。")
        data_label = config.get("sector_fund_flow", {}).get("display_label", "")
        raw_content = build_fallback_content(config) + "\n\n" + render_watchlist_report(watchlist_report, data_label)
    else:
        raw_content = prepare_content_for_ai(config, rss, sector_data, watchlist_report)


    # 生成简报
    print("[4/4] 正在使用 AI 生成财经简报...")
    digest = generate_digest(raw_content, config, today)

    # 保存
    print("[保存] 正在保存简报...")
    save_digest(digest, config, today)

    print("\n" + "=" * 50)
    print("生成完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
