"""
Gold & Silver Live Trading Agent
---------------------------------
Fetches live/historical price data for Gold and Silver futures via Yahoo
Finance (no API key required), computes common technical indicators
(moving averages, RSI, MACD, Bollinger Bands), detects support/resistance
levels from recent swing highs and lows, and runs a rule-based "agent"
that combines all of the above into a BUY / SELL / HOLD call with the
reasoning spelled out.

If an OPENAI_API_KEY secret is available, the agent also asks an LLM to
turn the computed indicators into a short plain-English market note (the
LLM is only used for narration - all signals are computed deterministically
first, so the trading call never depends on the model "inventing" numbers).

This module has no Streamlit dependency so it can be reused from a script,
a notebook, or the Streamlit app in trading_chart_app.py.
"""

import os

import numpy as np
import pandas as pd
import yfinance as yf

# Yahoo Finance tickers for the front-month COMEX futures contracts.
SYMBOLS = {
    "Gold": "GC=F",
    "Silver": "SI=F",
}

SMA_SHORT = 20
SMA_LONG = 50
EMA_SPAN = 20
RSI_PERIOD = 14
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD = 2
SWING_WINDOW = 5  # bars on each side to confirm a swing high/low
SR_TOLERANCE_PCT = 0.0025  # cluster levels within 0.25% of each other


def fetch_price_data(ticker: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Download OHLCV data for a ticker. Returns an empty DataFrame on failure."""
    try:
        df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.dropna(subset=["Close"])
        df.index.name = "Date"
        return df
    except Exception as exc:
        print(f"[warn] Failed to fetch {ticker}: {exc}")
        return pd.DataFrame()


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Adds SMA/EMA/RSI/MACD/Bollinger Band columns to a copy of df."""
    out = df.copy()
    close = out["Close"]

    out["SMA_SHORT"] = close.rolling(SMA_SHORT).mean()
    out["SMA_LONG"] = close.rolling(SMA_LONG).mean()
    out["EMA"] = close.ewm(span=EMA_SPAN, adjust=False).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / RSI_PERIOD, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI"] = 100 - (100 / (1 + rs))
    out["RSI"] = out["RSI"].fillna(50)

    ema_fast = close.ewm(span=MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW, adjust=False).mean()
    out["MACD"] = ema_fast - ema_slow
    out["MACD_SIGNAL"] = out["MACD"].ewm(span=MACD_SIGNAL, adjust=False).mean()
    out["MACD_HIST"] = out["MACD"] - out["MACD_SIGNAL"]

    mid = close.rolling(BOLLINGER_PERIOD).mean()
    std = close.rolling(BOLLINGER_PERIOD).std()
    out["BB_MID"] = mid
    out["BB_UPPER"] = mid + BOLLINGER_STD * std
    out["BB_LOWER"] = mid - BOLLINGER_STD * std

    return out


def _cluster_levels(levels, tolerance_pct: float):
    """Merge nearby price levels into single averaged levels."""
    if not levels:
        return []
    levels = sorted(levels)
    clusters = [[levels[0]]]
    for lvl in levels[1:]:
        if abs(lvl - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
            clusters[-1].append(lvl)
        else:
            clusters.append([lvl])
    return [round(sum(c) / len(c), 2) for c in clusters]


def find_support_resistance(df: pd.DataFrame, window: int = SWING_WINDOW,
                             tolerance_pct: float = SR_TOLERANCE_PCT):
    """
    Detects swing highs/lows (a bar whose high/low is the max/min within
    +/- `window` bars) and clusters them into support and resistance levels.
    Returns (support_levels, resistance_levels) as sorted lists of floats.
    """
    highs = df["High"]
    lows = df["Low"]
    n = len(df)

    swing_highs, swing_lows = [], []
    for i in range(window, n - window):
        window_high = highs.iloc[i - window: i + window + 1]
        window_low = lows.iloc[i - window: i + window + 1]
        if highs.iloc[i] == window_high.max():
            swing_highs.append(float(highs.iloc[i]))
        if lows.iloc[i] == window_low.min():
            swing_lows.append(float(lows.iloc[i]))

    resistance_levels = _cluster_levels(swing_highs, tolerance_pct)
    support_levels = _cluster_levels(swing_lows, tolerance_pct)

    last_close = float(df["Close"].iloc[-1])
    resistance_levels = sorted(lvl for lvl in resistance_levels if lvl >= last_close)[:3]
    support_levels = sorted((lvl for lvl in support_levels if lvl <= last_close), reverse=True)[:3]

    return sorted(support_levels), sorted(resistance_levels)


def generate_signal(df: pd.DataFrame, support_levels, resistance_levels) -> dict:
    """
    Rule-based agent: scores bullish/bearish evidence from trend, momentum
    and proximity to support/resistance, then turns the score into a call.
    """
    latest = df.iloc[-1]
    close = float(latest["Close"])
    reasons = []
    score = 0

    if pd.notna(latest["SMA_SHORT"]) and pd.notna(latest["SMA_LONG"]):
        if latest["SMA_SHORT"] > latest["SMA_LONG"]:
            score += 1
            reasons.append(f"Price trend is bullish: {SMA_SHORT}-period SMA is above the {SMA_LONG}-period SMA.")
        else:
            score -= 1
            reasons.append(f"Price trend is bearish: {SMA_SHORT}-period SMA is below the {SMA_LONG}-period SMA.")

    if close > latest["EMA"]:
        score += 0.5
        reasons.append(f"Price (${close:,.2f}) is trading above its {EMA_SPAN}-period EMA (${latest['EMA']:,.2f}).")
    else:
        score -= 0.5
        reasons.append(f"Price (${close:,.2f}) is trading below its {EMA_SPAN}-period EMA (${latest['EMA']:,.2f}).")

    rsi = float(latest["RSI"])
    if rsi >= 70:
        score -= 1
        reasons.append(f"RSI is {rsi:.1f} - overbought, momentum may be overstretched to the upside.")
    elif rsi <= 30:
        score += 1
        reasons.append(f"RSI is {rsi:.1f} - oversold, momentum may be overstretched to the downside.")
    else:
        reasons.append(f"RSI is {rsi:.1f} - in neutral territory.")

    if pd.notna(latest["MACD"]) and pd.notna(latest["MACD_SIGNAL"]):
        if latest["MACD"] > latest["MACD_SIGNAL"]:
            score += 1
            reasons.append("MACD is above its signal line - bullish momentum crossover.")
        else:
            score -= 1
            reasons.append("MACD is below its signal line - bearish momentum crossover.")

    if pd.notna(latest.get("BB_UPPER")) and pd.notna(latest.get("BB_LOWER")):
        if close >= latest["BB_UPPER"]:
            score -= 0.5
            reasons.append("Price is at/above the upper Bollinger Band - stretched, watch for a pullback.")
        elif close <= latest["BB_LOWER"]:
            score += 0.5
            reasons.append("Price is at/below the lower Bollinger Band - stretched, watch for a bounce.")

    nearest_resistance = min(resistance_levels, default=None,
                              key=lambda lvl: abs(lvl - close)) if resistance_levels else None
    nearest_support = min(support_levels, default=None,
                           key=lambda lvl: abs(lvl - close)) if support_levels else None

    if nearest_resistance is not None and abs(nearest_resistance - close) / close <= 0.005:
        score -= 0.5
        reasons.append(f"Price is close to resistance at ${nearest_resistance:,.2f} - upside may stall here.")
    if nearest_support is not None and abs(nearest_support - close) / close <= 0.005:
        score += 0.5
        reasons.append(f"Price is close to support at ${nearest_support:,.2f} - downside may find a floor here.")

    if score >= 1.5:
        call = "BUY"
    elif score <= -1.5:
        call = "SELL"
    else:
        call = "HOLD"

    confidence = min(95, 50 + abs(score) * 12)

    return {
        "call": call,
        "score": round(score, 2),
        "confidence": round(confidence, 1),
        "close": close,
        "reasons": reasons,
        "nearest_support": nearest_support,
        "nearest_resistance": nearest_resistance,
    }


def maybe_generate_ai_commentary(symbol: str, signal: dict) -> str | None:
    """Optional LLM narration of the already-computed signal. Skipped without an API key."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        reasons_text = "\n".join(f"- {r}" for r in signal["reasons"])
        prompt = (
            f"You are a trading-desk assistant. Below are the deterministic technical "
            f"signals computed for {symbol} (current price ${signal['close']:,.2f}, "
            f"call: {signal['call']}, confidence: {signal['confidence']}%).\n\n"
            f"{reasons_text}\n\n"
            "Write a concise 3-4 sentence market note summarizing this setup in plain "
            "English for a retail trader. Do not invent price levels or facts not "
            "listed above, and include a one-line risk disclaimer at the end."
        )
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[warn] AI commentary skipped for {symbol}: {exc}")
        return None


def analyze(symbol_name: str, period: str = "6mo", interval: str = "1d") -> dict:
    """End-to-end: fetch -> indicators -> support/resistance -> signal -> optional AI note."""
    ticker = SYMBOLS[symbol_name]
    raw = fetch_price_data(ticker, period=period, interval=interval)
    if raw.empty:
        return {"symbol": symbol_name, "ticker": ticker, "error": "No data available"}

    df = compute_indicators(raw)
    support, resistance = find_support_resistance(raw)
    signal = generate_signal(df, support, resistance)
    ai_note = maybe_generate_ai_commentary(symbol_name, signal)

    return {
        "symbol": symbol_name,
        "ticker": ticker,
        "data": df,
        "support": support,
        "resistance": resistance,
        "signal": signal,
        "ai_note": ai_note,
    }


if __name__ == "__main__":
    for name in SYMBOLS:
        result = analyze(name)
        if "error" in result:
            print(f"{name}: {result['error']}")
            continue
        sig = result["signal"]
        print(f"\n=== {name} ({result['ticker']}) ===")
        print(f"Price: ${sig['close']:,.2f}  Call: {sig['call']}  Confidence: {sig['confidence']}%")
        print(f"Support: {result['support']}  Resistance: {result['resistance']}")
        for r in sig["reasons"]:
            print(f" - {r}")
        if result["ai_note"]:
            print(f"\nAI note: {result['ai_note']}")
