"""Read public hanserLIVE posts and send incremental email notifications."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import smtplib
import ssl
import sys
import time
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

BASE = "https://2550505.com"
UID = 1
PAGE_SIZE = 20


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def request_json(path, params=None):
    url = BASE + path + ("?" + urlencode(params) if params else "")
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": "HanserLiveWatcher/1.0", "Referer": BASE + "/space/1"})
            with urlopen(request, timeout=30) as response:
                data = json.load(response)
            if not isinstance(data, dict) or data.get("code") != 0:
                raise RuntimeError("Website returned an unsuccessful response")
            return data
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def validate_author(post):
    if post.get("author", {}).get("uid") != UID or post.get("author", {}).get("nickname") != "hanserLIVE":
        raise RuntimeError("Unexpected post author")
    if not isinstance(post.get("id"), int) or post["id"] <= 0:
        raise RuntimeError("Invalid post ID")


def page(number):
    result = request_json("/post/user/list", {"uid": UID, "page": number, "pageSize": PAGE_SIZE})
    posts = result.get("list")
    if not isinstance(posts, list):
        raise RuntimeError("Missing post list")
    for post in posts:
        validate_author(post)
    return posts


def detail(post_id):
    info = request_json(f"/post/detail/{post_id}").get("info")
    if not isinstance(info, dict):
        raise RuntimeError("Missing post detail")
    validate_author(info)
    if info["id"] != post_id:
        raise RuntimeError("Wrong post ID")
    # The detail endpoint supplies an ISO timestamp with timezone, unlike the list.
    stamp = datetime.fromisoformat(info["post_time"].replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise RuntimeError("Missing timestamp timezone")
    return info


class BodyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.images = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ("br", "p", "div", "li"):
            self.parts.append("\n")
        if tag == "img" and attrs.get("src"):
            self.images.append(attrs["src"])
        if tag == "a" and attrs.get("href"):
            self.parts.append(" " + attrs["href"] + " ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "div", "li"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def post_body(post):
    parser = BodyParser()
    parser.feed(post.get("content") or "")
    images = list(parser.images)
    for image in post.get("pictures") or []:
        if isinstance(image, str):
            images.append(image)
        elif isinstance(image, dict):
            # Accept only explicit body image URLs, never the author's avatar.
            for key in ("url", "src", "origin", "original"):
                if isinstance(image.get(key), str):
                    images.append(image[key])
                    break
    safe_images = []
    for image in images:
        url = urljoin(BASE, unescape(image))
        if urlparse(url).scheme in ("https", "http") and url not in safe_images:
            safe_images.append(url)
    text = "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    return text, safe_images


def config():
    values = {name: os.environ.get(name, "").strip() for name in ("SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_TO")}
    missing = [key for key, value in values.items() if not value]
    if missing:
        raise RuntimeError("Missing GitHub Secrets: " + ", ".join(missing))
    return values


def send_email(posts=None, test=False):
    settings = config()
    sender = settings["SMTP_USERNAME"]
    recipient = settings["MAIL_TO"]
    message = EmailMessage()
    message["From"], message["To"] = sender, recipient
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Subject"] = "hanserLIVE 监控测试邮件" if test else f"hanserLIVE 有 {len(posts)} 条新动态"
    lines = ["这是一封 hanserLIVE 动态监控测试邮件。收到它说明发信链路可用。", BASE + "/space/1"] if test else []
    for post in posts or []:
        text, pictures = post_body(post)
        published = datetime.fromisoformat(post["post_time"].replace("Z", "+00:00"))
        from zoneinfo import ZoneInfo
        lines += [post.get("title") or "（无标题）", "北京时间：" + published.astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S"),
                  text or "（无文字正文）", BASE + f"/post/{post['id']}"]
        if pictures:
            lines += ["正文图片：", *pictures]
        lines.append("")
    message.set_content("\n".join(lines))
    port = int(os.environ.get("SMTP_PORT", "465"))
    host = os.environ.get("SMTP_HOST", "smtp.qq.com")
    context = ssl.create_default_context()
    smtp = smtplib.SMTP_SSL(host, port, timeout=30, context=context) if port == 465 else smtplib.SMTP(host, port, timeout=30)
    with smtp:
        if port != 465:
            smtp.starttls(context=context)
        smtp.login(sender, settings["SMTP_PASSWORD"])
        if smtp.send_message(message):
            raise RuntimeError("SMTP refused recipient")
    print("SMTP accepted the message. Inbox delivery must be checked by the recipient.")


def save_state(path, state):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def initialize(path):
    if path.exists():
        raise RuntimeError("State exists; refusing to replace the baseline")
    started = utcnow()
    posts = page(1)
    if not posts:
        raise RuntimeError("Empty list cannot establish a baseline")
    latest = detail(posts[0]["id"])
    save_state(path, {"version": 1, "uid": UID, "started_at": started, "last_successful_check": utcnow(),
                      "seen_ids": [p["id"] for p in posts], "notified_ids": []})
    print(f"Baseline saved: {len(posts)} known posts. Latest: {BASE}/post/{latest['id']}. No historical email sent.")


def check():
    posts = page(1)
    if not posts:
        raise RuntimeError("Empty dynamic list")
    latest = detail(posts[0]["id"])
    text, images = post_body(latest)
    print(json.dumps({"author": latest["author"]["nickname"], "uid": UID, "post_count": len(posts),
                      "latest_id": latest["id"], "published_at": latest["post_time"],
                      "title": latest["title"], "body_characters": len(text), "body_images": len(images)}, ensure_ascii=False))


def monitor(path):
    config()  # Missing mail configuration must not establish or advance the baseline.
    if not path.exists():
        initialize(path)
        return
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or state.get("uid") != UID:
        raise RuntimeError("Invalid state version or author")
    started = datetime.fromisoformat(state["started_at"])
    seen = set(state["seen_ids"])
    previous = set(seen)
    candidates = {}
    for number in range(1, 101):
        batch = page(number)
        if not batch:
            break
        for post in batch:
            if post["id"] not in previous:
                candidates[post["id"]] = post
        # Continue past pinned/known posts if the last item is new.
        if batch[-1]["id"] in previous or len(batch) < PAGE_SIZE:
            break
    else:
        raise RuntimeError("Pagination limit reached; state was not advanced")
    fresh = []
    for post_id in sorted(candidates):
        info = detail(post_id)
        seen.add(post_id)
        if datetime.fromisoformat(info["post_time"].replace("Z", "+00:00")) >= started:
            fresh.append(info)
    if fresh:
        send_email(fresh)
        state["last_mail_accepted_at"] = utcnow()
        state["notified_ids"] = sorted(set(state.get("notified_ids", [])) | {p["id"] for p in fresh})
    state["seen_ids"] = sorted(seen)
    state["last_successful_check"] = utcnow()
    save_state(path, state)
    print(f"Successful check: {len(fresh)} new post(s).")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("check", "initialize", "monitor", "test-email"), default="monitor")
    parser.add_argument("--state", type=Path, default=Path("state.json"))
    args = parser.parse_args()
    try:
        if args.mode == "check":
            check()
        elif args.mode == "initialize":
            initialize(args.state)
        elif args.mode == "test-email":
            send_email(test=True)
        else:
            monitor(args.state)
    except Exception as error:
        # Avoid exposing credentials, recipient addresses or server error responses in public logs.
        message = str(error) if isinstance(error, RuntimeError) else "Check website connectivity, SMTP configuration and provider status."
        print(f"Failed ({type(error).__name__}): {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
