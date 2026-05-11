# Equity Research Copilot

An AI-powered equity research tool built with FastAPI, yfinance, and Claude.

## Features

- **Stock Overview** — Real-time price, market cap, 52-week range, analyst ratings
- **Key Metrics** — Valuation, growth, profitability, financial health, and market data
- **Price Charts** — Interactive historical price charts (1M → 5Y)
- **Financial Statements** — Annual and quarterly income statement, balance sheet, cash flow
- **News Feed** — Latest news articles for any ticker
- **AI Copilot Chat** — Ask questions about any stock; Claude answers with full financial context
- **Research Report Generator** — One-click AI-generated equity research report

## Setup

### 1. Clone and configure

```bash
cd backend
cp .env.example .env
# Edit .env and add your Anthropic API key
```

### 2. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Run

```bash
cd backend
uvicorn main:app --reload
```

Visit **http://localhost:8000**

## Usage

1. Enter a ticker symbol (e.g. `AAPL`, `MSFT`, `NVDA`) in the search bar
2. Browse the **Overview**, **Financials**, and **News** tabs
3. Switch to **AI Copilot** to chat with Claude about the stock
4. Click **Generate Research Report** for a full AI-written equity research report

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key ([get one here](https://console.anthropic.com)) |

## Tech Stack

- **Backend**: FastAPI, yfinance, Anthropic Python SDK
- **Frontend**: React 18 (CDN), Tailwind CSS (CDN), Chart.js
- **AI Model**: Claude Sonnet (claude-sonnet-4-6)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stock/{ticker}` | Stock overview and key metrics |
| GET | `/api/stock/{ticker}/history` | Price history (`?period=1y`) |
| GET | `/api/stock/{ticker}/financials` | Financial statements |
| GET | `/api/stock/{ticker}/news` | Recent news |
| POST | `/api/chat` | AI chat with stock context |
| POST | `/api/report` | Generate research report |
