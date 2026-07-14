# news-updater

An automated daily news digest for **UPSC Civil Services** aspirants.

Every day, a GitHub Actions workflow pulls headlines from a curated set of
UPSC-relevant sources, groups them by subject (Polity, Economy, Environment,
Science & Tech, International Relations, Editorials, Explained), and saves a
markdown digest to the `digests/` folder. It works out of the box using free
public RSS feeds - no API key required. Optionally, it can also generate a
short AI-written brief if you add an OpenAI API key.

## How it works

1. `fetch_news.py` fetches items from RSS feeds defined in the `FEEDS` dict
   (The Hindu, Indian Express Explained, Down To Earth, PIB, etc.).
2. It groups the headlines by UPSC-relevant subject/category.
3. It writes the result to `digests/YYYY-MM-DD.md` and `digests/latest.md`.
4. `.github/workflows/daily_news.yml` runs this script automatically every
   day and commits the new digest back to the repo.

## Setup

1. **Enable workflow write access** (one-time): go to
   Settings -> Actions -> General -> Workflow permissions, and select
   "Read and write permissions". This lets the daily workflow commit the
   digest back to the repo.
2. **(Optional) Add an AI summary**: go to Settings -> Secrets and variables
   -> Actions, and add a secret named `OPENAI_API_KEY` with your OpenAI key.
   If you skip this, the digest still works - it just won't include the
   AI-written brief section.
3. The workflow runs automatically every day at 01:30 UTC (~07:00 IST). You
   can also trigger it manually any time from the Actions tab ->
   "Daily UPSC News Digest" -> "Run workflow".

## Customizing sources

Edit the `FEEDS` dictionary in `fetch_news.py` to add, remove, or re-tag any
RSS feed under a subject category.

## Disclaimer

This is an automated aggregator of publicly available headlines. Always
verify facts against the original source before using them in Mains answers.
