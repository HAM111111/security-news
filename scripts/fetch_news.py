import json
import feedparser
from datetime import datetime, timezone
from pathlib import Path

# مصادر RSS أمنية (يمكن تغييرها أو إضافة غيرها لاحقاً)
FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
]

OUTPUT = Path("news.json")
MAX_ITEMS_PER_FEED = 20


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
                "summary": entry.get("summary", "")[:500],
            })
    return items


def main():
    items = fetch_all()
    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(items),
        "items": items,
    }
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {len(items)} items to {OUTPUT}")


if __name__ == "__main__":
    main()
