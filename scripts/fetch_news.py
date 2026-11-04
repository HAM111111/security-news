import json
import re
import feedparser
import anthropic
from datetime import datetime, timezone
from pathlib import Path

FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
]

OUTPUT = Path("news.json")
MAX_ITEMS_PER_FEED = 20
MODEL = "claude-haiku-5-5"

PROMPT = """You are a cybersecurity analyst. Below are news articles, each with an index number.

Task 1: Choose up to 2 articles about breaches that are HIGH severity or that affect
globally known companies with economic impact. Skip anything else.
For each chosen article, write the analysis IN ARABIC with these fields:
- what_happened: ماذا حدث؟
- how_it_happened: كيف حدث بالضبط؟ (explain the attack path at a conceptual level only:
  the weakness, the entry point, the technique category. Do NOT include exploit code,
  payloads, or step-by-step instructions that would enable someone to repeat the attack.)
- how_handled: كيف تم التصرف؟
- severity: عالية or متوسطة

Task 2: From the chosen articles, pick 5 English technical terms and give each an
Arabic explanation (2-3 sentences).

Return ONLY valid JSON, no extra text, in this exact shape:
{"breaches": [{"index": 0, "severity": "...", "what_happened": "...", "how_it_happened": "...", "how_handled": "..."}],
 "terms": [{"term": "...", "explanation": "..."}]}

Articles:
"""


def clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", text).strip()


def fetch_all():
    items = []
    for url in FEEDS:
        feed = feedparser.parse(url)
        source = feed.feed.get("title", url)
        for entry in feed.entries[:MAX_ITEMS_PER_FEED]:
            items.append({
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "source": source,
                "published": entry.get("published", ""),
                "summary": clean_html(entry.get("summary", ""))[:1000],
            })
    return items


def analyze(items):
    client = anthropic.Anthropic()  # يقرأ ANTHROPIC_API_KEY من البيئة
    articles = "\n\n".join(
        f"[{i}] {it['title']}\n{it['summary']}" for i, it in enumerate(items)
    )
    msg = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": PROMPT + articles}],
    )
    text = msg.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)


def main():
    items = fetch_all()
    result = analyze(items)

    breaches = []
    for b in result.get("breaches", []):
        src = items[b["index"]]
        breaches.append({
            "title": src["title"],
            "link": src["link"],
            "source": src["source"],
            "severity": b.get("severity", ""),
            "what_happened": b.get("what_happened", ""),
            "how_it_happened": b.get("how_it_happened", ""),
            "how_handled": b.get("how_handled", ""),
        })

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "breaches": breaches,
        "terms": result.get("terms", []),
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(breaches)} breaches and {len(data['terms'])} terms")


if __name__ == "__main__":
    main()
