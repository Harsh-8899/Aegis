# Aegis Gold: Institutional-Grade XAU/USD Quant Trading Platform

Aegis Gold is an advanced, AI-driven, multi-agent quantitative trading, research, and simulation platform focused exclusively on Gold (XAU/USD). The system utilizes clean architecture, statistical risk management rules, and machine learning ensembles to execute automated strategies while prioritizing capital preservation.

---

## Key Highlights

- **Clean Architecture**: Decoupled layers from data ingestion to execution.
- **Ensemble Machine Learning**: Combined Random Forest, Extra Trees, and Gradient Boosting predictions.
- **Veto Risk Engine**: Strict limits on daily drawdowns, single-trade exposures, and VaR/CVaR breaches.
- **Low-Latency Simulation**: High-fidelity backtester and walk-forward/Monte Carlo analyzers.
- **Interactive UI Dashboard**: Premium dark-mode glassmorphism dashboard streaming updates via WebSockets.

---

## Project Structure

```
quant-platform/
├── config/
│   ├── development.yaml     # Sandbox configurations
│   └── production.yaml      # Staging configurations
├── src/
│   ├── agents/              # Multi-Agent orchestrators (CEO, Execution, etc.)
│   ├── api/                 # FastAPI REST / WebSockets routers
│   ├── data/                # Ingestion connector, validators, models
│   ├── features/            # Feature Store calculations (Polars powered)
│   ├── models/              # ML Ensembles training, drift, and registry
│   ├── risk/                # Exposure checks & Emergency shutdown
│   ├── simulation/          # Backtester & Walk-forward engines
│   └── dashboard/           # HTML5 / Vanilla CSS glassmorphism UI
├── tests/                   # Complete integration verification tests
└── requirements.txt         # Package dependencies list
```

---

## Quickstart Guide

### 1. Set Up Environment
Create a virtual environment and install all package requirements:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Database & Environment variables
Set environment details in `.env`:
```env
ENV=development
JWT_SECRET=super_secret_key
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/quant_trading
```

### 3. Start Redis Cache Server
Make sure a local Redis server is running (default port `6339` as defined in `development.yaml`):
```bash
redis-server --port 6339
```
*Note: If Redis is offline, the backend will automatically fall back to thread-safe in-memory caching.*

### 4. Run the API Server and Next.js Dashboard
Start the FastAPI live intelligence engine:
```bash
PYTHONPATH=. uvicorn src.api.server:app --reload --port 8000
```

Start the Next.js Dashboard server (in the `dashboard` folder):
```bash
cd dashboard
npm install
npm run dev
```

Open `http://localhost:3000` in your browser. The dashboard automatically subscribes to real-time WebSockets telemetry at `ws://localhost:8000/api/v1/ws/dashboard`.

### 5. Run the Test Suite
To verify the math engines, database schemas, API routes, and 1s real-time quant engines:
```bash
PYTHONPATH=. pytest
```

---

## Multi-Agent Communication Protocol

The platform implements specialized AI agents acting in coordination:

```
  [Market Intelligence] -- News Sentiment ---\
  [Macroeconomic Agent] -- Yields / DXY ------> [CEO Agent] ---> [Risk Evaluator] ---> [Execution Agent]
  [Microstructure Agent] - Tick Volumes -------/                   (Veto Check)
```

1. **CEO Agent**: Controls state changes and coordinates information routing.
2. **Risk Agent**: Evaluates exposure metrics and holds absolute veto authority to block or shut down trading.
3. **Execution Agent**: Places orders and calculates connection latencies/slippage logs.
4. **Performance Agent**: Calculates Sharpe, Sortino, Calmar, and Win Rate attributions.

---

## Disaster Recovery Controls

### Emergency Shutdown Trigger
If drawdown limits are breached or the market experiences extreme anomalies, the Risk Agent executes an Emergency Shutdown. 

To trigger this manually, send a POST request with administrative JWT authorization:
```bash
curl -X POST http://localhost:8000/api/v1/system/emergency-shutdown \
  -H "Authorization: Bearer <JWT_TOKEN>"
```
This cancels all pending orders, flattens all open positions, and restricts further order routing.
