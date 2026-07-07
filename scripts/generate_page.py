#!/usr/bin/env python3
"""
生成 GitHub Pages 首页。

首页重点展示最新财经简报，并保留最近归档入口。
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

import pytz

try:
    import markdown
except ImportError:
    markdown = None


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = Path(__file__).parent / "config.json"
REPO_URL = "https://github.com/tinajiwona/daily-tech-digest"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def plain_text(markdown_text: str) -> str:
    text = re.sub(r"```.*?```", "", markdown_text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_`~-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def extract_lede(content: str) -> str:
    quote = re.search(r"^>\s*(.+)$", content, re.MULTILINE)
    source = quote.group(1) if quote else plain_text(content)
    return source[:180] + ("..." if len(source) > 180 else "")


def extract_sections(content: str) -> list[str]:
    return [item.strip() for item in re.findall(r"^##\s+(.+)$", content, re.MULTILINE)]


def markdown_to_html(md_content: str) -> str:
    if markdown:
        md = markdown.Markdown(
            extensions=["extra", "tables", "fenced_code", "sane_lists"],
            output_format="html5",
        )
        return md.convert(md_content)

    html_lines = []
    in_list = False

    for raw_line in md_content.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if re.match(r"^#{1,4}\s+", line):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            level = min(len(re.match(r"^#+", line).group()), 4)
            text = render_inline(line.lstrip("#").strip())
            html_lines.append(f"<h{level}>{text}</h{level}>")
            continue

        if line.startswith(">"):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<blockquote>{render_inline(line.lstrip('> ').strip())}</blockquote>")
            continue

        if line in {"---", "***"}:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr>")
            continue

        if line.startswith(("- ", "* ")) or re.match(r"^\d+\.\s+", line):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            text = re.sub(r"^(-|\*|\d+\.)\s+", "", line)
            html_lines.append(f"<li>{render_inline(text)}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False
        html_lines.append(f"<p>{render_inline(line)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def render_inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def get_digest_files(digests_dir: Path) -> list[dict]:
    files = []
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

    for file in digests_dir.glob("*.md"):
        if not pattern.match(file.name):
            continue

        content = file.read_text(encoding="utf-8")
        files.append(
            {
                "date": file.stem,
                "filename": file.name,
                "title": extract_title(content, f"{file.stem} 财经简报"),
                "lede": extract_lede(content),
                "sections": extract_sections(content),
                "content": content,
                "words": len(plain_text(content)),
            }
        )

    files.sort(key=lambda x: x["date"], reverse=True)
    return files


def section_nav(sections: list[str]) -> str:
    if not sections:
        return ""

    items = "".join(f"<span>{html.escape(section)}</span>" for section in sections[:8])
    return f'<div class="section-nav">{items}</div>'


def archive_cards(files: list[dict]) -> str:
    cards = []
    for item in files[:12]:
        cards.append(
            f"""
            <a class="archive-card" href="digests/{html.escape(item['filename'])}">
                <span>{html.escape(item['date'])}</span>
                <strong>{html.escape(item['title'])}</strong>
                <p>{html.escape(item['lede'])}</p>
            </a>
            """
        )
    return "\n".join(cards) if cards else '<p class="empty">暂无简报</p>'


def generate_page(files: list[dict], output_path: Path):
    tz = pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz).strftime("%Y年%m月%d日 %H:%M")
    latest = files[0] if files else None

    latest_title = html.escape(latest["title"]) if latest else "每日财经简报"
    latest_date = html.escape(latest["date"]) if latest else now
    latest_lede = html.escape(latest["lede"]) if latest else "等待首次生成财经简报。"
    latest_content = markdown_to_html(latest["content"]) if latest else ""
    latest_sections = section_nav(latest["sections"] if latest else [])
    latest_words = f"{latest['words']:,}" if latest else "0"
    archive_html = archive_cards(files[1:] if len(files) > 1 else files)
    sector_chart_path = PROJECT_ROOT / "digests" / "sector-flow.svg"
    sector_chart_html = ""
    if sector_chart_path.exists():
        sector_chart_html = """
        <section class="chart-panel" aria-label="板块资金流向图">
            <img src="digests/sector-flow.svg" alt="板块资金流向图">
        </section>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日财经简报 | Daily Finance Digest</title>
    <style>
        :root {{
            --bg: #f7f4ed;
            --surface: #fffdf8;
            --surface-alt: #f0eee6;
            --ink: #201f1b;
            --muted: #6e6a60;
            --line: #ddd5c7;
            --accent: #0f766e;
            --accent-strong: #134e4a;
            --warn: #b45309;
            --shadow: 0 18px 46px rgba(39, 35, 26, 0.1);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", Arial, sans-serif;
            line-height: 1.7;
        }}

        a {{
            color: var(--accent);
            text-decoration: none;
        }}

        .shell {{
            max-width: 1180px;
            margin: 0 auto;
            padding: 28px 20px 56px;
        }}

        .topbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 18px;
            margin-bottom: 28px;
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 800;
            font-size: 20px;
        }}

        .brand-mark {{
            display: grid;
            place-items: center;
            width: 40px;
            height: 40px;
            border-radius: 8px;
            background: var(--accent-strong);
            color: #fff;
        }}

        .top-actions {{
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--muted);
            font-size: 14px;
        }}

        .button {{
            display: inline-flex;
            align-items: center;
            min-height: 38px;
            padding: 0 14px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            color: var(--ink);
            font-weight: 700;
        }}

        .hero {{
            display: grid;
            grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
            gap: 22px;
            align-items: stretch;
            margin-bottom: 24px;
        }}

        .hero-main,
        .metric-panel,
        .article,
        .archive-card {{
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            box-shadow: var(--shadow);
        }}

        .hero-main {{
            padding: 34px;
        }}

        .eyebrow {{
            margin: 0 0 10px;
            color: var(--accent-strong);
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        h1 {{
            margin: 0;
            font-size: clamp(34px, 6vw, 64px);
            line-height: 1.02;
            letter-spacing: 0;
        }}

        .lede {{
            max-width: 760px;
            margin: 18px 0 0;
            color: var(--muted);
            font-size: 17px;
        }}

        .meta-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            margin-top: 22px;
        }}

        .pill {{
            display: inline-flex;
            align-items: center;
            min-height: 32px;
            padding: 0 11px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface-alt);
            color: var(--muted);
            font-size: 13px;
            font-weight: 700;
        }}

        .metric-panel {{
            padding: 22px;
            display: grid;
            gap: 12px;
        }}

        .metric {{
            padding: 16px;
            border-radius: 8px;
            background: var(--surface-alt);
            border: 1px solid var(--line);
        }}

        .metric span {{
            display: block;
            color: var(--muted);
            font-size: 13px;
        }}

        .metric strong {{
            display: block;
            margin-top: 4px;
            font-size: 26px;
        }}

        .section-nav {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 0 0 22px;
        }}

        .section-nav span {{
            padding: 8px 10px;
            border-radius: 8px;
            background: #e8f3ef;
            color: var(--accent-strong);
            font-weight: 700;
            font-size: 13px;
        }}

        .chart-panel {{
            margin: 0 0 24px;
            padding: 16px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            box-shadow: var(--shadow);
        }}

        .chart-panel img {{
            display: block;
            width: 100%;
            height: auto;
            border-radius: 6px;
        }}

        .article {{
            padding: 28px 34px;
        }}

        .article h1 {{
            font-size: 32px;
            margin-bottom: 18px;
        }}

        .article h2 {{
            margin: 34px 0 14px;
            padding-top: 22px;
            border-top: 1px solid var(--line);
            font-size: 24px;
        }}

        .article h3 {{
            margin: 22px 0 10px;
            font-size: 18px;
        }}

        .article p,
        .article li {{
            color: #38352f;
        }}

        .article blockquote {{
            margin: 18px 0;
            padding: 14px 18px;
            border-left: 4px solid var(--accent);
            background: #eef7f3;
            color: var(--accent-strong);
            font-weight: 700;
        }}

        .article a {{
            font-weight: 700;
            border-bottom: 1px solid rgba(15, 118, 110, 0.25);
        }}

        .article hr {{
            border: 0;
            border-top: 1px solid var(--line);
            margin: 28px 0;
        }}

        .archive {{
            margin-top: 24px;
        }}

        .section-title {{
            display: flex;
            justify-content: space-between;
            align-items: end;
            gap: 16px;
            margin: 0 0 14px;
        }}

        .section-title h2 {{
            margin: 0;
            font-size: 24px;
        }}

        .archive-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 14px;
        }}

        .archive-card {{
            display: block;
            min-height: 178px;
            padding: 18px;
            color: var(--ink);
            transition: transform 0.18s ease, border-color 0.18s ease;
        }}

        .archive-card:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}

        .archive-card span {{
            color: var(--accent);
            font-size: 13px;
            font-weight: 800;
        }}

        .archive-card strong {{
            display: block;
            margin-top: 8px;
            line-height: 1.35;
        }}

        .archive-card p {{
            margin: 10px 0 0;
            color: var(--muted);
            font-size: 14px;
        }}

        .empty {{
            color: var(--muted);
        }}

        footer {{
            margin-top: 34px;
            padding-top: 18px;
            border-top: 1px solid var(--line);
            color: var(--muted);
            font-size: 13px;
        }}

        @media (max-width: 860px) {{
            .topbar,
            .hero,
            .section-title {{
                display: block;
            }}

            .top-actions {{
                margin-top: 14px;
            }}

            .metric-panel {{
                margin-top: 18px;
            }}

            .article,
            .hero-main,
            .chart-panel {{
                padding: 22px;
            }}

            .archive-grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="shell">
        <header class="topbar">
            <a class="brand" href="./index.html">
                <span class="brand-mark">¥</span>
                <span>每日财经简报</span>
            </a>
            <div class="top-actions">
                <span>更新于 {html.escape(now)}</span>
                <a class="button" href="digests/index.html">历史归档</a>
                <a class="button" href="{REPO_URL}">GitHub</a>
            </div>
        </header>

        <section class="hero">
            <div class="hero-main">
                <p class="eyebrow">Daily Finance Briefing</p>
                <h1>{latest_title}</h1>
                <p class="lede">{latest_lede}</p>
                <div class="meta-row">
                    <span class="pill">日期 {latest_date}</span>
                    <span class="pill">约 {latest_words} 字</span>
                    <span class="pill">网站自动更新</span>
                </div>
            </div>
            <aside class="metric-panel">
                <div class="metric"><span>归档简报</span><strong>{len(files)}</strong></div>
                <div class="metric"><span>最近更新</span><strong>{latest_date}</strong></div>
                <div class="metric"><span>运行方式</span><strong>GitHub Actions</strong></div>
            </aside>
        </section>

{sector_chart_html}
        {latest_sections}

        <article class="article">
            {latest_content}
        </article>

        <section class="archive">
            <div class="section-title">
                <h2>最近归档</h2>
                <a class="button" href="digests/index.html">查看全部</a>
            </div>
            <div class="archive-grid">
                {archive_html}
            </div>
        </section>

        <footer>
            由 OpenAI + GitHub Actions 自动生成。内容仅供参考，不构成投资建议。
        </footer>
    </div>
</body>
</html>
"""

    output_path.write_text(html_content, encoding="utf-8")
    print(f"[完成] 已生成: {output_path}")


def main():
    print("=" * 50)
    print("GitHub Pages 首页生成器")
    print("=" * 50)

    config = load_config()
    digests_dir = PROJECT_ROOT / config["output"]["digests_dir"]
    files = get_digest_files(digests_dir)

    print(f"扫描目录: {digests_dir}")
    print(f"找到 {len(files)} 份简报")

    generate_page(files, PROJECT_ROOT / "index.html")


if __name__ == "__main__":
    main()
