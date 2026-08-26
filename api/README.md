# AI Quant Lab API

FastAPI service that runs on-demand quant backtests. Wraps the same
Streamlit page (`streamlit_app/app_pages/2_AI_Quant_Lab.py`) that produces
the daily preset results — so custom configs get real, freshly computed
answers instead of "nearest preset" fallbacks.

Consumed by [`aiquantlab-web`](https://github.com/danggyugit/aiquantlab-web).

## Local dev

```bash
cd api
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Test:
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/backtest \
  -H "Content-Type: application/json" \
  -d '{"cap_tiers":["Large Cap"],"sectors":["Information Technology"]}'
```

**Note**: first request takes 5-10 min (cold prefetch: yfinance +
SEC EDGAR downloads). Subsequent requests reuse the in-memory cache.

## Deployment (Render.com)

The repo-root `render.yaml` includes both the MCP server and this API as
Blueprint services. To deploy:

1. Push this repo to GitHub (already done)
2. Render → New → Blueprint → connect the `stock-dashboard` repo
3. Render creates two services: `aiquantlab-mcp` (free) and `aiquantlab-api`
4. Confirm `aiquantlab-api` is on a paid plan (Starter $7/mo minimum — the
   free tier's 512MB RAM won't fit sklearn + xgboost + lightgbm loaded
   together, and cold starts drop the in-memory cache)
5. After first deploy, copy the URL and add to `aiquantlab-web` as
   `NEXT_PUBLIC_API_URL`

## Endpoints

- `GET /` → basic status
- `GET /health` → health check (Render uses this)
- `POST /backtest` → run backtest, returns full result JSON matching
  the shape of `streamlit_app/data/cache/backtests/*.json`

## Environment variables

- `CORS_ALLOW_ORIGINS` (comma-separated): defaults to
  `http://localhost:3000,https://aiquantlab-web.vercel.app`
- `PORT` (Render sets automatically)
- Optional: `FINNHUB_API_KEY`, `FRED_API_KEY` if the AI Quant Lab code
  calls those providers (currently backtest engine doesn't need them)
