"""
Daily UPSC News Digest Agent
-----------------------------
Fetches curated news from UPSC-relevant sources (The Hindu, Indian Express,
Down To Earth, PIB) via their public RSS feeds, groups them by subject
(useful for GS Paper mapping), and writes a dated markdown digest to the
digests/ folder. If an OPENAI_API_KEY secret is available, it also adds a
short AI-written brief on top of the headlines.

This script has NO paid dependency by default -- it works purely off free
public RSS feeds. The AI summary step is optional and is skipped
automatically if no API key is configured.
"""

import os
import datetime
import feedparser

FEEDS = {
    "Polity & Governance": [
        ("The Hindu - National", "https://www.thehindu.com/news/national/feeder/default.rss"),
        ("PIB - Press Releases", "https://pib.gov.in/rss/lreng.xml"),
    ],
    "International Relations": [
        ("The Hindu - International", "https://www.thehindu.com/news/international/feeder/default.rss"),
    ],
    "Economy": [
        ("The Hindu - Business", "https://www.thehindu.com/business/feeder/default.rss"),
    ],
    "Environment & Ecology": [
        ("Down To Earth", "https://www.downtoearth.org.in/rss/home"),
    ],
    "Science & Technology": [
        ("The Hindu - Sci-Tech", "https://www.thehindu.com/sci-tech/feeder/default.rss"),
    ],
    "Editorial / Opinion (for Mains)": [
        ("The Hindu - Editorial", "https://www.thehindu.com/opinion/editorial/feeder/default.rss"),
    ],
    "Explained (Concept building)": [
        ("Indian Express - Explained", "https://indianexpress.com/section/explained/feed/"),
    ],
}

MAX_ITEMS_PER_SOURCE = 6


def fetch_category(sources):
    items = []
    for source_name, url in sources:
        try:
            parsed = feedparser.parse(url)
            for entry in parsed.entries[:MAX_ITEMS_PER_SOURCE]:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if title and link:
                    items.append({
                        "source": source_name,
                        "title": title,
                        "link": link,
                    })
        except Exception as exc:
            print(f"[warn] Failed to fetch {source_name}: {exc}")
    return items


def maybe_generate_ai_brief(all_items):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        headlines = []
        for category, items in all_items.items():
            for item in items[:3]:
                headlines.append(f"[{category}] {item['title']}")
        if not headlines:
            return None

        prompt = (
            "You are helping a UPSC Civil Services aspirant. Below is a list of "
            "today's headlines grouped by subject. Write a concise 5-6 sentence "
            "brief highlighting the 3-4 most exam-relevant developments and why "
            "they matter for Prelims/Mains. Do not invent facts not present in "
            "the headlines.\n\n" + "\n".join(headlines)
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[warn] AI brief generation skipped: {exc}")
        return None


def build_markdown(all_items, date_str):
    lines = [f"# UPSC Daily News Digest - {date_str}", ""]
    lines.append("_Auto-generated. Verify facts against original sources before quoting in Mains answers._")
    lines.append("")

    ai_brief = maybe_generate_ai_brief(all_items)
    if ai_brief:
        lines.append("## Today's Brief")
        lines.append("")
        lines.append(ai_brief)
        lines.append("")

    for category, items in all_items.items():
        if not items:
            continue
        lines.append(f"## {category}")
        lines.append("")
        for item in items:
            lines.append(f"- **[{item['title']}]({item['link']})** -- _{item['source']}_")
        lines.append("")

    return "\n".join(lines)


def main():
    today = datetime.date.today().isoformat()
    all_items = {category: fetch_category(sources) for category, sources in FEEDS.items()}

    markdown = build_markdown(all_items, today)

    os.makedirs("digests", exist_ok=True)
    out_path = os.path.join("digests", f"{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    latest_path = os.path.join("digests", "latest.md")
    with open(latest_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"Digest written to {out_path}")


if __name__ == "__main__":
    main()
