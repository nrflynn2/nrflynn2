#!/usr/bin/env python3
import os
import re
import sys
import html
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime

README_PATH = os.environ.get("README_PATH", "README.md")
FEED_URL = os.environ.get("FEED_URL", "https://noahrflynn.com/feed.xml")
POST_LIMIT = int(os.environ.get("POST_LIMIT", "8"))

START = "<!-- BLOG-POST-LIST:START -->"
END = "<!-- BLOG-POST-LIST:END -->"

ATOM = {"atom": "http://www.w3.org/2005/Atom"}


def fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nrflynn2-profile-readme-updater/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def clean_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return value.replace("|", r"\|")


def parse_date(value: str) -> datetime:
    if not value:
        return datetime.min
    try:
        return parsedate_to_datetime(value).replace(tzinfo=None)
    except Exception:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except Exception:
            return datetime.min


def parse_atom(root):
    posts = []
    for entry in root.findall("atom:entry", ATOM):
        title = clean_text(entry.findtext("atom:title", default="", namespaces=ATOM))
        published = (
            entry.findtext("atom:published", default="", namespaces=ATOM)
            or entry.findtext("atom:updated", default="", namespaces=ATOM)
        )

        link = ""
        for candidate in entry.findall("atom:link", ATOM):
            rel = candidate.attrib.get("rel", "alternate")
            href = candidate.attrib.get("href", "")
            if href and rel == "alternate":
                link = href
                break

        if title and link:
            posts.append({"title": title, "url": link, "date": parse_date(published)})

    return posts


def parse_rss(root):
    posts = []
    for item in root.findall("./channel/item"):
        title = clean_text(item.findtext("title", default=""))
        link = clean_text(item.findtext("link", default=""))
        published = item.findtext("pubDate", default="")

        if title and link:
            posts.append({"title": title, "url": link, "date": parse_date(published)})

    return posts


def load_posts():
    data = fetch(FEED_URL)
    root = ET.fromstring(data)

    if root.tag.endswith("feed"):
        posts = parse_atom(root)
    else:
        posts = parse_rss(root)

    posts.sort(key=lambda post: post["date"], reverse=True)
    return posts[:POST_LIMIT]


def render_table(posts):
    lines = ["| Date | Post |", "| --- | --- |"]

    if not posts:
        lines.append("| - | No posts found |")
        return "\n".join(lines)

    for post in posts:
        date = post["date"].strftime("%b %Y") if post["date"] != datetime.min else ""
        lines.append(f"| {date} | [{post['title']}]({post['url']}) |")

    return "\n".join(lines)


def replace_section(readme, rendered):
    pattern = re.compile(
        rf"{re.escape(START)}.*?{re.escape(END)}",
        flags=re.DOTALL,
    )

    replacement = f"{START}\n{rendered}\n{END}"

    if not pattern.search(readme):
        raise RuntimeError(f"Could not find README markers: {START} / {END}")

    return pattern.sub(replacement, readme)


def main():
    posts = load_posts()
    rendered = render_table(posts)

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    updated = replace_section(readme, rendered)

    if updated == readme:
        print("README already up to date.")
        return 0

    with open(README_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)

    print(f"Updated {README_PATH} with {len(posts)} posts from {FEED_URL}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

