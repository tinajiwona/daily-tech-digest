#!/usr/bin/env python3
"""
PushPlus 微信推送通知。
"""

import html
import os
import re
import sys
from datetime import datetime

import pytz


SECTION_COLORS = {
    "今日热点": "#dc2626",
    "市场动态": "#0f766e",
    "宏观与政策": "#7c3aed",
    "行业观察": "#2563eb",
    "国际视野": "#b45309",
    "投资洞察": "#134e4a",
    "选题灵感": "#be123c",
    "延伸阅读": "#4b5563",
}


def normalize_section_name(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fa5A-Za-z0-9]", "", text)


def get_repo_links() -> dict:
    repo = os.environ.get("GITHUB_REPOSITORY", "tinajiwona/daily-tech-digest")
    run_id = os.environ.get("GITHUB_RUN_ID")
    base = f"https://github.com/{repo}"
    pages = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}"
    return {
        "pages": pages,
        "latest": f"{pages}/digests/latest.md",
        "archive": f"{pages}/digests/",
        "repo": base,
        "run": f"{base}/actions/runs/{run_id}" if run_id else f"{base}/actions",
    }


def extract_digest_intro(markdown_text: str) -> str:
    quote = re.search(r"^>\s*(.+)$", markdown_text, re.MULTILINE)
    if quote:
        return quote.group(1).strip()

    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown_text)
    text = re.sub(r"[#>*_`~-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180] + ("..." if len(text) > 180 else "")


def extract_section_titles(markdown_text: str) -> list[str]:
    return [item.strip() for item in re.findall(r"^##\s+(.+)$", markdown_text, re.MULTILINE)]


def inline_markdown(text: str) -> str:
    safe = html.escape(text)
    safe = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", safe)
    safe = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', safe)
    return safe


def format_markdown_to_html(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    html_lines = []
    in_list = False

    for raw_line in lines:
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

            level = len(re.match(r"^#+", line).group())
            text = line.lstrip("#").strip()
            section_key = normalize_section_name(text)
            color = next(
                (value for key, value in SECTION_COLORS.items() if normalize_section_name(key) in section_key),
                "#134e4a",
            )

            if level == 1:
                html_lines.append(
                    f'<h1 style="font-size:22px;line-height:1.35;margin:18px 0 12px;color:#111827;">{inline_markdown(text)}</h1>'
                )
            else:
                html_lines.append(
                    f'<h2 style="font-size:18px;line-height:1.35;margin:22px 0 10px;padding:9px 11px;border-left:4px solid {color};background:#f8fafc;color:#111827;">{inline_markdown(text)}</h2>'
                )
            continue

        if line.startswith(("> ", "〉")):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            text = line.lstrip(">〉 ").strip()
            html_lines.append(
                f'<blockquote style="margin:12px 0;padding:12px 14px;border-left:4px solid #0f766e;background:#ecfdf5;color:#134e4a;line-height:1.75;">{inline_markdown(text)}</blockquote>'
            )
            continue

        if line in {"---", "***"}:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append('<hr style="border:none;border-top:1px solid #e5e7eb;margin:18px 0;">')
            continue

        if line.startswith(("- ", "* ")) or re.match(r"^\d+\.\s+", line):
            if not in_list:
                html_lines.append('<ul style="margin:8px 0 14px;padding-left:18px;">')
                in_list = True
            text = re.sub(r"^(-|\*|\d+\.)\s+", "", line)
            html_lines.append(f'<li style="margin:7px 0;line-height:1.75;">{inline_markdown(text)}</li>')
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False

        html_lines.append(f'<p style="margin:9px 0;line-height:1.8;">{inline_markdown(line)}</p>')

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def build_push_content(markdown_text: str) -> str:
    tz = pytz.timezone("Asia/Shanghai")
    generated_at = datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")
    links = get_repo_links()
    intro = html.escape(extract_digest_intro(markdown_text))
    sections = extract_section_titles(markdown_text)
    section_badges = "".join(
        f'<span style="display:inline-block;margin:4px 4px 0 0;padding:4px 8px;border-radius:6px;background:#f1f5f9;color:#334155;font-size:12px;">{html.escape(section)}</span>'
        for section in sections[:8]
    )
    body = format_markdown_to_html(markdown_text)

    return f"""
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',Arial,sans-serif;color:#1f2937;background:#ffffff;line-height:1.75;">
  <div style="padding:16px 16px 14px;border:1px solid #e5e7eb;border-radius:10px;background:#fffbeb;margin-bottom:16px;">
    <div style="font-size:13px;font-weight:700;color:#92400e;margin-bottom:6px;">每日财经简报</div>
    <div style="font-size:15px;color:#374151;">{intro}</div>
    <div style="margin-top:10px;">{section_badges}</div>
  </div>

  {body}

  <div style="margin-top:22px;padding:14px;border-radius:10px;background:#f8fafc;border:1px solid #e5e7eb;">
    <p style="margin:0 0 8px;font-weight:700;color:#111827;">快速入口</p>
    <p style="margin:6px 0;"><a href="{links['latest']}">查看最新简报</a></p>
    <p style="margin:6px 0;"><a href="{links['archive']}">打开历史归档</a></p>
    <p style="margin:6px 0;"><a href="{links['run']}">查看本次 Actions 运行</a></p>
  </div>

  <p style="text-align:center;color:#9ca3af;font-size:12px;line-height:1.6;margin:18px 0 0;">
    由 OpenAI + GitHub Actions 自动生成<br>
    生成时间: {generated_at}<br>
    本简报仅供参考，不构成投资建议。
  </p>
</div>
"""


def post_pushplus(payload: dict) -> tuple[bool, str]:
    import requests

    errors = []
    for url in ["https://www.pushplus.plus/send", "http://www.pushplus.plus/send"]:
        try:
            response = requests.post(url, json=payload, timeout=20)
            response.raise_for_status()
            result = response.json()
            code = result.get("code")
            msg = result.get("msg") or result.get("message") or "无返回消息"

            if code == 200:
                return True, f"PushPlus 已接收：{msg}"

            errors.append(f"{url} 返回 code={code}, msg={msg}")
        except Exception as exc:
            errors.append(f"{url} 请求失败：{exc}")

    return False, "；".join(errors)


def send_pushplus_notification(token: str, title: str, content: str) -> bool:
    token = token.strip()
    html_payload = {
        "token": token,
        "title": title,
        "content": build_push_content(content),
        "template": "html",
        "channel": "wechat",
    }
    success, message = post_pushplus(html_payload)
    if success:
        print(f"[成功] {message}")
        return True

    print(f"[警告] HTML 简报推送失败，尝试发送短文本测试消息：{message}")

    links = get_repo_links()
    fallback_payload = {
        "token": token,
        "title": f"{title} - 测试通知",
        "content": "\n".join(
            [
                "每日财经简报已生成，但完整 HTML 推送失败。",
                "这是一条 PushPlus 短文本兜底测试通知。",
                f"查看最新简报：{links['latest']}",
                f"查看运行记录：{links['run']}",
            ]
        ),
        "template": "txt",
        "channel": "wechat",
    }
    fallback_success, fallback_message = post_pushplus(fallback_payload)
    if fallback_success:
        print(f"[成功] 短文本兜底通知已发送：{fallback_message}")
        return True

    print(f"[失败] PushPlus 推送失败：{fallback_message}")
    return False


def main():
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("[错误] 请设置 PUSHPLUS_TOKEN 环境变量")
        sys.exit(1)

    digest_file = os.environ.get("DIGEST_FILE", "digests/latest.md")

    try:
        with open(digest_file, "r", encoding="utf-8") as f:
            content = f.read()

        tz = pytz.timezone("Asia/Shanghai")
        today = datetime.now(tz).strftime("%Y-%m-%d")
        title = f"每日财经简报 {today}"
        success = send_pushplus_notification(token=token, title=title, content=content)

        sys.exit(0 if success else 1)
    except FileNotFoundError:
        print(f"[错误] 找不到简报文件: {digest_file}")
        sys.exit(1)
    except Exception as exc:
        print(f"[错误] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
