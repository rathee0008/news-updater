"""
Gold & Silver Live Trading Chart + AI Agent
--------------------------------------------
Streamlit dashboard with:
  1. A live TradingView candlestick widget for real-time price action
     (no API key needed - TradingView's free embeddable widget).
  2. A Plotly technical chart built from Yahoo Finance data, annotated
     with moving averages, Bollinger Bands, and detected support /
     resistance levels, plus RSI and MACD panels underneath.
  3. An "AI Agent" panel that turns all of the above into a plain
     BUY / SELL / HOLD call with the reasoning behind it (see
     trading_agent.py for the signal logic).

Run with: streamlit run trading_chart_app.py
"""

import datetime

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from trading_agent import SYMBOLS, analyze

st.set_page_config(page_title="Gold & Silver Trading Agent", page_icon="\U0001F4C8", layout="wide")

st.title("Gold & Silver Live Trading Agent")
st.caption(
    "Live chart + a rule-based technical agent for Gold (GC=F) and Silver (SI=F) "
    "futures - trend, momentum, support/resistance and a BUY/SELL/HOLD call."
)

TV_SYMBOLS = {"Gold": "OANDA:XAUUSD", "Silver": "OANDA:XAUUSD".replace("XAU", "XAG")}

PERIOD_OPTIONS = {
    "1 Month": ("1mo", "1d"),
    "3 Months": ("3mo", "1d"),
    "6 Months": ("6mo", "1d"),
    "1 Year": ("1y", "1d"),
    "5 Days (hourly)": ("5d", "1h"),
}

with st.sidebar:
    st.header("Options")
    asset = st.radio("Asset", list(SYMBOLS.keys()), index=0)
    period_label = st.selectbox("Chart range", list(PERIOD_OPTIONS.keys()), index=2)
    show_live_widget = st.checkbox("Show live TradingView widget", value=True)
    refresh = st.button("Refresh analysis")
    st.markdown("---")
    st.caption(
        "Data source: Yahoo Finance (yfinance), free & no API key. "
        "Add an OPENAI_API_KEY secret to also get a plain-English AI note "
        "on top of the computed signal."
    )
    st.caption(
        "This is not financial advice. Verify against your own research "
        "and risk management before trading."
    )

period, interval = PERIOD_OPTIONS[period_label]


@st.cache_data(ttl=60, show_spinner=False)
def run_analysis(symbol_name: str, period: str, interval: str):
    return analyze(symbol_name, period=period, interval=interval)


if refresh:
    run_analysis.clear()

if show_live_widget:
    tv_symbol = TV_SYMBOLS[asset]
    tv_html = f"""
    <div class="tradingview-widget-container">
      <div id="tv_chart_{asset.lower()}"></div>
      <script src="https://s3.tradingview.com/tv.js"></script>
      <script>
      new TradingView.widget({{
        "width": "100%",
        "height": 500,
        "symbol": "{tv_symbol}",
        "interval": "60",
        "timezone": "Etc/UTC",
        "theme": "light",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "studies": ["STD;Pivot%1Points%1Standard", "STD;RSI"],
        "container_id": "tv_chart_{asset.lower()}"
      }});
      </script>
    </div>
    """
    st.subheader(f"Live chart - {tv_symbol}")
    st.components.v1.html(tv_html, height=520)

with st.spinner(f"Fetching {asset} data and running the agent..."):
    result = run_analysis(asset, period, interval)

if "error" in result:
    st.error(f"Could not fetch data for {asset} ({result.get('ticker')}): {result['error']}")
    st.stop()

df = result["data"]
sig = result["signal"]
support = result["support"]
resistance = result["resistance"]

call_color = {"BUY": "green", "SELL": "red", "HOLD": "orange"}[sig["call"]]

col1, col2, col3 = st.columns(3)
col1.metric(f"{asset} price", f"${sig['close']:,.2f}")
col2.markdown(
    f"<h2 style='color:{call_color};margin-top:0'>{sig['call']}</h2>"
    f"<span>Confidence: {sig['confidence']}%</span>",
    unsafe_allow_html=True,
)
col3.metric(
    "Nearest support / resistance",
    f"${sig['nearest_support']:,.2f}" if sig["nearest_support"] else "n/a",
    delta=f"R: ${sig['nearest_resistance']:,.2f}" if sig["nearest_resistance"] else None,
    delta_color="off",
)

st.subheader("Technical chart with support / resistance")

fig = make_subplots(
    rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03,
    subplot_titles=(f"{asset} price", "RSI", "MACD"),
)

fig.add_trace(
    go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name=asset,
    ),
    row=1, col=1,
)
fig.add_trace(go.Scatter(x=df.index, y=df["SMA_SHORT"], name="SMA 20", line=dict(width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["SMA_LONG"], name="SMA 50", line=dict(width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["BB_UPPER"], name="BB Upper", line=dict(width=1, dash="dot")), row=1, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["BB_LOWER"], name="BB Lower", line=dict(width=1, dash="dot")), row=1, col=1)

for lvl in support:
    fig.add_hline(y=lvl, line=dict(color="green", dash="dash", width=1),
                   annotation_text=f"Support ${lvl:,.2f}", annotation_position="bottom left", row=1, col=1)
for lvl in resistance:
    fig.add_hline(y=lvl, line=dict(color="red", dash="dash", width=1),
                   annotation_text=f"Resistance ${lvl:,.2f}", annotation_position="top left", row=1, col=1)

fig.add_trace(go.Scatter(x=df.index, y=df["RSI"], name="RSI", line=dict(width=1, color="purple")), row=2, col=1)
fig.add_hline(y=70, line=dict(color="red", dash="dot", width=1), row=2, col=1)
fig.add_hline(y=30, line=dict(color="green", dash="dot", width=1), row=2, col=1)

fig.add_trace(go.Bar(x=df.index, y=df["MACD_HIST"], name="MACD Hist"), row=3, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["MACD"], name="MACD", line=dict(width=1)), row=3, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["MACD_SIGNAL"], name="Signal", line=dict(width=1)), row=3, col=1)

fig.update_layout(height=850, xaxis_rangeslider_visible=False, legend=dict(orientation="h", y=1.05))
st.plotly_chart(fig, use_container_width=True)

st.subheader("Agent reasoning")
for reason in sig["reasons"]:
    st.markdown(f"- {reason}")

if result.get("ai_note"):
    st.subheader("AI market note")
    st.info(result["ai_note"])

st.caption(f"Last analyzed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (cached for 60s)")
st.divider()
st.caption(
    "Automated technical analysis only - not financial advice. Gold/Silver futures "
    "prices can gap and move fast; always confirm with your own research and manage risk."
)
