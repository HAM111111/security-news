import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import feedparser
from openai import OpenAI

# مصادر RSS (أضف أو احذف حسب رغبتك)
FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
    "https://krebsonsecurity.com/feed/",
    "https://www.securityweek.com/feed/",
    "https://www.darkreading.com/rss.xml",
]

OUTPUT = Path("news.json")
MAX_ITEMS_PER_FEED = 15
MODEL = "openai/gpt-oss-120b"

PROMPT = """You are a cybersecurity analyst. Below are news articles from several sources,
each with an index number and its source name.

Task 1: Group articles that describe the SAME event together into stories.
Choose the stories that are most important: high severity, or affecting globally known
companies with economic impact. Choose as many as you judge worthwhile (at least 1, at most 5).
Ignore minor news.

For each story, write the analysis IN ARABIC with these fields:
- headline: عنوان القصة بالعربية
- article_indexes: list of the article indexes that belong to this story
- agreement: ما اتفقت عليه المصادر (in Arabic)
- differences: ما اختلفت فيه المصادر أو ما انفردت به (in Arabic; write "لا يوجد" if none)
- severity: عالية or متوسطة
- what_happened: ماذا حدث؟
- how_it_happened: كيف حدث بالضبط؟ (explain the attack path at a conceptual level only:
  the weakness, the entry point, the technique category. Do NOT include exploit code,
  payloads, or step-by-step instructions that would enable someone to repeat the attack.)
- how_handled: كيف تم التصرف؟

Task 2: From the chosen stories, pick 5 English technical terms and give each an
Arabic explanation (2-3 sentences).

Return ONLY valid JSON, no extra text, in this exact shape:
{"stories": [{"headline": "...", "article_indexes": [0, 3], "agreement": "...", "differences": "...",
 "severity": "...", "what_happened": "...", "how_it_happened": "...", "how_handled": "..."}],
 "terms": [{"term": "...", "explanation": "..."}]}

Articles:
"""


def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_all():
    items = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"Skipping {url}: {e}")
            continue
        if not feed.entries:
            print(f"No entries from {url}")
            continue
        source = feed.feed.get("title", url)
        for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
            items.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "source": source,
                "published": entry.get("published", ""),
                "summary": clean_html(entry.get("summary", ""))[:800],
            })
    return items


def extract_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON found in model response")
    return json.loads(text[start:end + 1])


def analyze(items):
    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=os.environ["GROQ_API_KEY"],
    )
    articles = "\n\n".join(
        f"[{i}] ({it['source']}) {it['title']}\n{it['summary']}"
        for i, it in enumerate(items)
    )
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=5000,
        messages=[{"role": "user", "content": PROMPT + articles}],
    )
    text = resp.choices[0].message.content.strip()
    return extract_json(text)


def main():
    items = fetch_all()
    if not items:
        raise SystemExit("No items fetched from any RSS feed")

    result = analyze(items)

    stories = []
    for s in result.get("stories", []):
        sources = []
        for idx in s.get("article_indexes", []):
            if isinstance(idx, int) and 0 <= idx < len(items):
                sources.append({
                    "name": items[idx]["source"],
                    "link": items[idx]["link"],
                })
        stories.append({
            "headline": s.get("headline", ""),
            "sources": sources,
            "agreement": s.get("agreement", ""),
            "differences": s.get("differences", ""),
            "severity": s.get("severity", ""),
            "what_happened": s.get("what_happened", ""),
            "how_it_happened": s.get("how_it_happened", ""),
            "how_handled": s.get("how_handled", ""),
        })

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "stories": stories,
        "terms": result.get("terms", []),
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(stories)} stories and {len(data['terms'])} terms")


if __name__ == "__main__":
    main()
