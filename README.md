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

## Gold & Silver live trading agent

`trading_chart_app.py` is a separate Streamlit dashboard (unrelated to the
news digest) for tracking Gold and Silver:

- A live TradingView chart widget (`OANDA:XAUUSD` / `OANDA:XAGUSD`), free and
  requiring no API key.
- A Plotly technical chart built from free Yahoo Finance data (`GC=F` / `SI=F`
  futures) with moving averages, Bollinger Bands, RSI, MACD, and
  auto-detected **support/resistance** levels drawn from recent swing
  highs/lows.
- An **AI agent** (`trading_agent.py`) that combines trend, momentum, and
  proximity to support/resistance into a `BUY` / `SELL` / `HOLD` call with
  the reasoning listed out. If `OPENAI_API_KEY` is set, it also asks an LLM
  to turn the computed signal into a short plain-English market note (the
  call itself is always computed deterministically, never invented by the
  model).

Run it locally with:

```bash
pip install -r requirements.txt
streamlit run trading_chart_app.py
```

You can also run the agent standalone from the command line:

```bash
python trading_agent.py
```

This is automated technical analysis, not financial advice - always verify
before trading and manage your own risk.

## Disclaimer

This is an automated aggregator of publicly available headlines. Always
verify facts against the original source before using them in Mains answers.
