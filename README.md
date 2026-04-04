# Stock Dashboard

A full-stack US stock market dashboard combining **Market Heatmap**, **Portfolio Tracker**, and **Sentiment Analysis** into a single application.

![Tech Stack](https://img.shields.io/badge/React_19-TypeScript-blue)
![Backend](https://img.shields.io/badge/FastAPI-Python_3.11+-green)
![DB](https://img.shields.io/badge/DuckDB-Local-orange)

## Features

### A. Market Heatmap + Screener
- **D3.js treemap heatmap** — S&P 500 stocks grouped by GICS sector, sized by market cap, colored by daily change
- **Screener** — Filter stocks by sector, market cap, P/E, dividend yield with sortable results
- **Stock Detail** — TradingView-style candlestick chart (lightweight-charts), financials, news
- **Compare** — Overlay normalized performance charts for up to 5 stocks

### B. Portfolio Tracker
- **Trade management** — Record buy/sell trades with ticker autocomplete
- **Holdings & P/L** — Real-time unrealized gain/loss calculation with current prices
- **Asset allocation** — Donut charts by stock and sector (Recharts)
- **Dividend calendar** — Monthly grid view with upcoming ex-dates
- **Tax estimation** — Short-term vs long-term capital gains summary

### C. Market Sentiment
- **Fear & Greed Index** — Custom SVG gauge combining VIX, momentum, volume, and market breadth
- **News sentiment** — Headlines with AI-powered sentiment analysis (Claude API)
- **AI Market Report** — LLM-generated daily market summary (manual trigger)

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 19, TypeScript, Vite 6, Tailwind CSS, shadcn/ui |
| Charts | D3.js (treemap), lightweight-charts (candlestick), Recharts (general) |
| State | Zustand (client), TanStack Query (server) |
| Backend | FastAPI, Python 3.11+, Pydantic v2 |
| Database | DuckDB (local, serverless) |
| Data | yfinance (market data), Finnhub (news) |
| AI | Anthropic Claude API (sentiment analysis, reports) |
| Scheduler | APScheduler (auto-refresh) |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- (Optional) Finnhub API key, Anthropic API key

### Backend
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # Edit with your API keys
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

### First-time Setup
After both servers are running, load S&P 500 stock data:
```bash
curl -X POST http://localhost:8001/api/market/refresh
```

## Project Structure

```
stock_dashboard/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Pydantic Settings
│   ├── db.py                # DuckDB schema (10 tables)
│   ├── routers/             # API endpoints (30+)
│   ├── services/            # Business logic
│   ├── providers/           # yfinance, Finnhub, Claude wrappers
│   └── models/              # Pydantic request/response models
├── frontend/
│   ├── src/
│   │   ├── pages/           # 11 pages
│   │   ├── components/      # UI, market, portfolio, sentiment
│   │   ├── api/             # Typed API client (30+ functions)
│   │   ├── stores/          # Zustand global state
│   │   └── types/           # Centralized TypeScript types
│   └── package.json
├── docs/
│   ├── PRD.md               # Product requirements
│   └── TRD.md               # Technical design
├── CLAUDE.md                # Project coding rules
└── AGENTS.md                # Agent team definitions
```

## API Endpoints

| Group | Endpoints | Description |
|---|---|---|
| Market | 9 | Heatmap, screener, stock detail, chart, compare, search |
| Portfolio | 14 | CRUD portfolios/trades, allocation, performance, dividends, tax |
| Sentiment | 7 | Fear & Greed, news, sentiment analysis, AI report |

## Environment Variables

```env
DUCKDB_PATH=./data/stock_dashboard.duckdb    # Required
FINNHUB_API_KEY=your_key                      # Optional (news)
ANTHROPIC_API_KEY=sk-ant-...                  # Optional (AI features)
```

## License

MIT
