#!/usr/bin/env python3
"""
HTML 归档页生成器。
"""

import html
import json
import re
from datetime import datetime
from pathlib import Path

import pytz


PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def plain_text(markdown_text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown_text)
    text = re.sub(r"[#>*_`~-]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_digest_files(digests_dir: Path) -> list[dict]:
    files = []
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")

    for file in digests_dir.glob("*.md"):
        if not pattern.match(file.name):
            continue

        content = file.read_text(encoding="utf-8")
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        quote_match = re.search(r"^>\s*(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else f"{file.stem} 财经简报"
        summary = quote_match.group(1).strip() if quote_match else plain_text(content)[:150]

        files.append(
            {
                "date": file.stem,
                "filename": file.name,
                "title": title,
                "summary": summary[:170] + ("..." if len(summary) > 170 else ""),
                "size": len(content),
            }
        )

    files.sort(key=lambda x: x["date"], reverse=True)
    return files


def generate_html(files: list[dict], output_path: Path):
    tz = pytz.timezone("Asia/Shanghai")
    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

    items = []
    for item in files:
        items.append(
            f"""
            <a class="digest-item" href="{html.escape(item['filename'])}">
                <div>
                    <span class="digest-date">{html.escape(item['date'])}</span>
                    <h2>{html.escape(item['title'])}</h2>
                    <p>{html.escape(item['summary'])}</p>
                </div>
                <span class="read-link">阅读</span>
            </a>
            """
        )

    list_html = "\n".join(items) if items else '<p class="empty">暂无简报</p>'

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>每日财经简报归档</title>
    <style>
        :root {{
            --bg: #f7f4ed;
            --surface: #fffdf8;
            --ink: #201f1b;
            --muted: #6e6a60;
            --line: #ddd5c7;
            --accent: #0f766e;
            --accent-strong: #134e4a;
            --shadow: 0 14px 34px rgba(39, 35, 26, 0.08);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: var(--bg);
            color: var(--ink);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans SC", Arial, sans-serif;
            line-height: 1.65;
        }}

        a {{
            color: inherit;
            text-decoration: none;
        }}

        .container {{
            max-width: 980px;
            margin: 0 auto;
            padding: 36px 20px 56px;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            gap: 18px;
            margin-bottom: 24px;
        }}

        .eyebrow {{
            margin: 0 0 8px;
            color: var(--accent-strong);
            font-size: 13px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }}

        h1 {{
            margin: 0;
            font-size: clamp(32px, 7vw, 56px);
            line-height: 1.05;
            letter-spacing: 0;
        }}

        .subtitle {{
            margin: 10px 0 0;
            color: var(--muted);
        }}

        .home-link,
        .read-link {{
            display: inline-flex;
            align-items: center;
            min-height: 38px;
            padding: 0 14px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            color: var(--accent-strong);
            font-weight: 800;
        }}

        .digest-list {{
            display: grid;
            gap: 14px;
        }}

        .digest-item {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 18px;
            align-items: center;
            padding: 20px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            box-shadow: var(--shadow);
            transition: transform 0.18s ease, border-color 0.18s ease;
        }}

        .digest-item:hover {{
            transform: translateY(-2px);
            border-color: var(--accent);
        }}

        .digest-date {{
            color: var(--accent);
            font-weight: 800;
            font-size: 13px;
        }}

        .digest-item h2 {{
            margin: 6px 0 8px;
            font-size: 20px;
            line-height: 1.35;
        }}

        .digest-item p {{
            margin: 0;
            color: var(--muted);
        }}

        .empty {{
            padding: 32px;
            border: 1px solid var(--line);
            border-radius: 8px;
            background: var(--surface);
            color: var(--muted);
        }}

        footer {{
            margin-top: 28px;
            padding-top: 18px;
            border-top: 1px solid var(--line);
            color: var(--muted);
            font-size: 13px;
        }}

        @media (max-width: 720px) {{
            header,
            .digest-item {{
                display: block;
            }}

            .home-link,
            .read-link {{
                margin-top: 14px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <p class="eyebrow">Archive</p>
                <h1>每日财经简报归档</h1>
                <p class="subtitle">按日期保存的市场热点、宏观政策、行业观察与投资洞察。</p>
            </div>
            <a class="home-link" href="../index.html">返回首页</a>
        </header>

        <main class="digest-list">
            {list_html}
        </main>

        <footer>
            共 {len(files)} 份简报 · 最后更新 {html.escape(now)} · 内容仅供参考，不构成投资建议。
        </footer>
    </div>
</body>
</html>
"""

    output_path.write_text(page, encoding="utf-8")
    print(f"[完成] 已生成: {output_path}")


def main():
    print("=" * 50)
    print("HTML 归档页生成器")
    print("=" * 50)

    config = load_config()
    digests_dir = PROJECT_ROOT / config["output"]["digests_dir"]
    files = get_digest_files(digests_dir)

    print(f"扫描目录: {digests_dir}")
    print(f"找到 {len(files)} 份简报")

    generate_html(files, digests_dir / "index.html")


if __name__ == "__main__":
    main()
