#!/usr/bin/env python3
"""
每日财经简报生成器
整合全球财经媒体 RSS 源，使用 OpenAI 或 Claude/GLM 生成简报
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
            feed = feedparser.parse(feed_info["url"])
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


def prepare_content_for_ai(rss: list) -> str:
    """准备发送给 AI 的内容"""
    sections = []

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
- 总长度控制在3000-4000字
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
    prompt = build_digest_prompt(content, today)

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
        timeout=120,
    )

    payload = response.json()
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
    print("\n[1/3] 正在抓取财经媒体 RSS 源...")
    rss = fetch_rss_feeds(config)
    print(f"      获取 {len(rss)} 条")

    # 检查是否有内容
    if not rss:
        print("\n[错误] 未获取到任何内容，退出")
        sys.exit(1)

    # 准备内容
    raw_content = prepare_content_for_ai(rss)

    # 生成简报
    print("[2/3] 正在使用 AI 生成财经简报...")
    digest = generate_digest(raw_content, config, today)

    # 保存
    print("[3/3] 正在保存简报...")
    save_digest(digest, config, today)

    print("\n" + "=" * 50)
    print("生成完成!")
    print("=" * 50)


if __name__ == "__main__":
    main()
