import sys
import os
# Force UTF-8 before anything else
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import yfinance as yf
import math
import httpx
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()


def _safe(s) -> str:
    """Return a UTF-8 safe string, stripping surrogate characters."""
    if s is None:
        return ""
    return str(s).encode("utf-8", errors="replace").decode("utf-8")

app = FastAPI(title="Equity Research Copilot API")


@app.get("/health")
async def health():
    return {"status": "ok"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _clean(val):
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    return val


def _get_api_key():
    key = os.getenv("DEEPSEEK_API_KEY", "")
    if not key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY not set")
    try:
        key = key.encode("utf-8", "surrogateescape").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    key = "".join(c for c in key.strip() if ord(c) < 128)
    if not key:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY contains only invalid characters")
    return key


CLAUDE_VERSION = "deepseek-v1"


async def _call_claude(system: str, messages: list, max_tokens: int = 2048) -> str:
    """Call DeepSeek API (OpenAI-compatible) via stdlib urllib.request."""
    import json
    import urllib.request
    import urllib.error
    import asyncio
    import ssl

    api_key = _get_api_key()
    full_messages = [{"role": "system", "content": system}] + messages
    payload = {
        "model": "deepseek-chat",
        "max_tokens": max_tokens,
        "messages": full_messages,
    }
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    def do_request():
        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=body_bytes,
            method="POST",
        )
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("content-type", "application/json; charset=utf-8")
        req.add_header("accept", "application/json")
        ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    loop = asyncio.get_event_loop()
    status, body = await loop.run_in_executor(None, do_request)

    body_text = body.decode("utf-8", errors="replace")
    if status != 200:
        try:
            err = json.loads(body_text)
            msg = err.get("error", {}).get("message", body_text)
        except Exception:
            msg = body_text
        raise HTTPException(status_code=status, detail=f"DeepSeek API ({status}): {msg}")

    data = json.loads(body_text)
    return data["choices"][0]["message"]["content"]


@app.get("/api/version")
async def version():
    return {"claude_caller": CLAUDE_VERSION, "build": "2026-05-11"}


@app.get("/api/stock/{ticker}")
async def get_stock_overview(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        price = _clean(info.get("currentPrice") or info.get("regularMarketPrice"))
        if price is None:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found")

        hist = stock.history(period="3mo")
        price_history = []
        if not hist.empty:
            price_history = [
                {"date": str(d.date()), "close": round(float(c), 2)}
                for d, c in zip(hist.index, hist["Close"])
            ]

        prev_close = _clean(info.get("previousClose"))
        change = round(price - prev_close, 2) if prev_close else None
        change_pct = _clean(info.get("regularMarketChangePercent"))

        return {
            "ticker": ticker.upper(),
            "name": info.get("longName", ticker.upper()),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "currency": info.get("currency", "USD"),
            "description": info.get("longBusinessSummary", ""),
            "website": info.get("website", ""),
            "employees": info.get("fullTimeEmployees"),
            "price": price,
            "previousClose": prev_close,
            "change": change,
            "changePercent": change_pct,
            "marketCap": _clean(info.get("marketCap")),
            "enterpriseValue": _clean(info.get("enterpriseValue")),
            "peRatio": _clean(info.get("trailingPE")),
            "forwardPE": _clean(info.get("forwardPE")),
            "pegRatio": _clean(info.get("pegRatio")),
            "priceToBook": _clean(info.get("priceToBook")),
            "priceToSales": _clean(info.get("priceToSalesTrailing12Months")),
            "evToEbitda": _clean(info.get("enterpriseToEbitda")),
            "evToRevenue": _clean(info.get("enterpriseToRevenue")),
            "eps": _clean(info.get("trailingEps")),
            "forwardEps": _clean(info.get("forwardEps")),
            "dividendYield": _clean(info.get("dividendYield")),
            "dividendRate": _clean(info.get("dividendRate")),
            "payoutRatio": _clean(info.get("payoutRatio")),
            "beta": _clean(info.get("beta")),
            "52wHigh": _clean(info.get("fiftyTwoWeekHigh")),
            "52wLow": _clean(info.get("fiftyTwoWeekLow")),
            "50dAvg": _clean(info.get("fiftyDayAverage")),
            "200dAvg": _clean(info.get("twoHundredDayAverage")),
            "volume": _clean(info.get("volume")),
            "avgVolume": _clean(info.get("averageVolume")),
            "shortRatio": _clean(info.get("shortRatio")),
            "grossMargin": _clean(info.get("grossMargins")),
            "operatingMargin": _clean(info.get("operatingMargins")),
            "netMargin": _clean(info.get("profitMargins")),
            "roe": _clean(info.get("returnOnEquity")),
            "roa": _clean(info.get("returnOnAssets")),
            "revenueGrowth": _clean(info.get("revenueGrowth")),
            "earningsGrowth": _clean(info.get("earningsGrowth")),
            "debtToEquity": _clean(info.get("debtToEquity")),
            "currentRatio": _clean(info.get("currentRatio")),
            "quickRatio": _clean(info.get("quickRatio")),
            "freeCashflow": _clean(info.get("freeCashflow")),
            "operatingCashflow": _clean(info.get("operatingCashflow")),
            "totalRevenue": _clean(info.get("totalRevenue")),
            "totalDebt": _clean(info.get("totalDebt")),
            "totalCash": _clean(info.get("totalCash")),
            "recommendationKey": info.get("recommendationKey"),
            "recommendationMean": _clean(info.get("recommendationMean")),
            "targetMeanPrice": _clean(info.get("targetMeanPrice")),
            "targetHighPrice": _clean(info.get("targetHighPrice")),
            "targetLowPrice": _clean(info.get("targetLowPrice")),
            "numberOfAnalysts": info.get("numberOfAnalystOpinions"),
            "priceHistory": price_history,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{ticker}/history")
async def get_price_history(ticker: str, period: str = "1y"):
    valid = ["1mo", "3mo", "6mo", "1y", "2y", "5y"]
    if period not in valid:
        period = "1y"
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=period)
        if hist.empty:
            return {"history": []}
        return {
            "history": [
                {
                    "date": str(d.date()),
                    "open": round(float(r["Open"]), 2),
                    "high": round(float(r["High"]), 2),
                    "low": round(float(r["Low"]), 2),
                    "close": round(float(r["Close"]), 2),
                    "volume": int(r["Volume"]),
                }
                for d, r in hist.iterrows()
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{ticker}/financials")
async def get_financials(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper())

        def df_to_records(df):
            if df is None or df.empty:
                return []
            records = []
            for col in df.columns:
                row = {"period": str(col.date() if hasattr(col, "date") else col)}
                for idx in df.index:
                    val = df.loc[idx, col]
                    try:
                        v = float(val)
                        row[str(idx)] = None if (math.isnan(v) or math.isinf(v)) else v
                    except Exception:
                        row[str(idx)] = None
                records.append(row)
            return records

        return {
            "annual": {
                "incomeStatement": df_to_records(stock.financials),
                "balanceSheet": df_to_records(stock.balance_sheet),
                "cashFlow": df_to_records(stock.cashflow),
            },
            "quarterly": {
                "incomeStatement": df_to_records(stock.quarterly_financials),
                "balanceSheet": df_to_records(stock.quarterly_balance_sheet),
                "cashFlow": df_to_records(stock.quarterly_cashflow),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stock/{ticker}/news")
async def get_news(ticker: str):
    try:
        stock = yf.Ticker(ticker.upper())
        raw = stock.news or []
        items = []
        for n in raw[:20]:
            thumb = ""
            t = n.get("thumbnail")
            if t and isinstance(t, dict):
                res = t.get("resolutions", [])
                if res:
                    thumb = res[0].get("url", "")
            items.append({
                "title": n.get("title", ""),
                "link": n.get("link", ""),
                "publisher": n.get("publisher", ""),
                "publishTime": n.get("providerPublishTime"),
                "thumbnail": thumb,
                "relatedTickers": n.get("relatedTickers", []),
            })
        return {"news": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    ticker: Optional[str] = None
    stockContext: Optional[dict] = None


def _build_context_str(ticker: str, ctx: dict) -> str:
    def pct(v):
        return f"{v*100:.1f}%" if isinstance(v, (int, float)) else "N/A"

    def money(v, unit=""):
        if not isinstance(v, (int, float)):
            return "N/A"
        if unit == "B":
            return f"${v/1e9:.2f}B"
        if unit == "M":
            return f"${v/1e6:.2f}M"
        return f"${v:,.2f}"

    def cap(v):
        if not isinstance(v, (int, float)):
            return "N/A"
        if v >= 1e12:
            return f"${v/1e12:.2f}T"
        if v >= 1e9:
            return f"${v/1e9:.2f}B"
        return f"${v/1e6:.2f}M"

    lines = [
        f"\n\n=== Current Stock Context: {ticker} ({ctx.get('name', '')}) ===",
        f"Price: {money(ctx.get('price'))} | Change: {ctx.get('changePercent', 'N/A')}%",
        f"Market Cap: {cap(ctx.get('marketCap'))} | EV: {cap(ctx.get('enterpriseValue'))}",
        f"P/E: {ctx.get('peRatio', 'N/A')} | Fwd P/E: {ctx.get('forwardPE', 'N/A')} | PEG: {ctx.get('pegRatio', 'N/A')}",
        f"P/B: {ctx.get('priceToBook', 'N/A')} | P/S: {ctx.get('priceToSales', 'N/A')} | EV/EBITDA: {ctx.get('evToEbitda', 'N/A')}",
        f"EPS: {money(ctx.get('eps'))} | Fwd EPS: {money(ctx.get('forwardEps'))}",
        f"Revenue: {cap(ctx.get('totalRevenue'))} | Rev Growth: {pct(ctx.get('revenueGrowth'))} | EPS Growth: {pct(ctx.get('earningsGrowth'))}",
        f"Gross Margin: {pct(ctx.get('grossMargin'))} | Op Margin: {pct(ctx.get('operatingMargin'))} | Net Margin: {pct(ctx.get('netMargin'))}",
        f"ROE: {pct(ctx.get('roe'))} | ROA: {pct(ctx.get('roa'))}",
        f"D/E: {ctx.get('debtToEquity', 'N/A')} | Current Ratio: {ctx.get('currentRatio', 'N/A')} | Quick: {ctx.get('quickRatio', 'N/A')}",
        f"FCF: {cap(ctx.get('freeCashflow'))} | Total Debt: {cap(ctx.get('totalDebt'))} | Cash: {cap(ctx.get('totalCash'))}",
        f"Beta: {ctx.get('beta', 'N/A')} | Div Yield: {pct(ctx.get('dividendYield'))}",
        f"52W: {money(ctx.get('52wLow'))} – {money(ctx.get('52wHigh'))}",
        f"Analyst: {(ctx.get('recommendationKey') or 'N/A').upper()} | Target: {money(ctx.get('targetMeanPrice'))} | Analysts: {ctx.get('numberOfAnalysts', 'N/A')}",
        f"Sector: {ctx.get('sector', 'N/A')} | Industry: {ctx.get('industry', 'N/A')}",
    ]
    desc = _safe(ctx.get("description", ""))
    if desc:
        lines.append(f"Description: {desc[:600]}")
    return "\n".join(_safe(l) for l in lines)


SYSTEM_PROMPT = """You are an expert equity research analyst and AI copilot for professional investors.

You help users analyze stocks, interpret financial statements, evaluate valuations, identify risks and opportunities, and form investment theses.

Guidelines:
- Cite specific metrics when making claims
- Use headers and bullet points for clarity
- Be balanced — present both bull and bear cases when relevant
- Flag data limitations or when your analysis is speculative
- Recommend consulting a financial advisor for personal investment decisions"""


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        system = SYSTEM_PROMPT
        if request.ticker and request.stockContext:
            system += _build_context_str(request.ticker, request.stockContext)
        messages = [{"role": m.role, "content": m.content} for m in request.messages]
        text = await _call_claude(system, messages, max_tokens=2048)
        return {"response": text}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=traceback.format_exc())


class ReportRequest(BaseModel):
    ticker: str
    stockContext: dict


@app.post("/api/report")
async def generate_report(request: ReportRequest):
    try:
        ctx = request.stockContext
        context_str = _build_context_str(request.ticker, ctx)

        prompt = _safe(f"""Generate a comprehensive professional equity research report.
{context_str}

Write the report in the following structure using Markdown:

# {ctx.get('name', request.ticker)} ({request.ticker}) — Equity Research Report

**Date:** {__import__('datetime').date.today().strftime('%B %d, %Y')}

## Executive Summary
[2–3 paragraphs with the investment thesis and key findings]

## Investment Rating
| Field | Value |
|-------|-------|
| **Rating** | BUY / HOLD / SELL |
| **12-Month Price Target** | $XX.XX |
| **Current Price** | [from data] |
| **Upside / Downside** | X% |

## Company Overview
[Business description, key products/services, competitive positioning, market opportunity]

## Financial Analysis
### Revenue & Growth
[Revenue trend analysis, growth drivers, guidance]

### Profitability & Margins
[Gross / operating / net margin analysis and trends]

### Balance Sheet & Cash Flow
[Leverage, liquidity, FCF generation, capital allocation]

## Valuation
[Multiples vs. peers, DCF considerations, fair value range]

## Investment Thesis

### Bull Case
- Key reason 1
- Key reason 2
- Key reason 3

### Bear Case / Key Risks
- Key risk 1
- Key risk 2
- Key risk 3

## Conclusion
[One-paragraph investment summary]

---
*This report is generated by AI Equity Research Copilot for informational purposes only and does not constitute investment advice. Always do your own due diligence.*""")

        text = await _call_claude(
            system="You are an expert equity research analyst writing a professional report.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )
        return {"report": text}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_tickers(q: str = Query(..., min_length=1)):
    try:
        url = "https://query1.finance.yahoo.com/v1/finance/search"
        params = {"q": q, "quotesCount": 8, "newsCount": 0, "listsCount": 0, "enableFuzzyQuery": True}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; EquityResearchCopilot/1.0)"}
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url, params=params, headers=headers)
            data = resp.json()
        results = []
        for item in data.get("quotes", []):
            sym = item.get("symbol", "")
            if not sym:
                continue
            results.append({
                "ticker": sym,
                "name": _safe(item.get("longname") or item.get("shortname") or sym),
                "exchange": item.get("exchDisp") or item.get("exchange", ""),
                "type": item.get("quoteType", ""),
            })
        return {"results": results}
    except Exception:
        return {"results": []}


# Serve frontend static files (must be last)
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
