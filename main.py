from gamma_engine import calculate_gex, gamma_flip
from fastapi import FastAPI
from datetime import datetime, timezone

app = FastAPI(
    title="GammaLit AI",
    description="AI-powered options and market analytics",
    version="0.1.0"
)

@app.get("/")
def home():
    return {
        "platform": "GammaLit AI",
        "status": "online",
        "version": "0.1.0"
    }

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.get("/api/features")
def features():
    return {
        "features": [
            "Gamma Exposure Analytics",
            "Options Flow",
            "Dealer Positioning Estimates",
            "AI Trading Analyst",
            "Advanced Charts and Heatmaps",
            "Discord Alerts",
            "Strategy Backtesting"
        ],
        "data_source": "not_connected"
    }

@app.get("/api/gamma/{symbol}")
def gamma_data(symbol: str):
    symbol = symbol.upper()

    if symbol not in ("SPY", "SPX"):
        raise HTTPException(
            status_code=400,
            detail="Only SPY and SPX are supported",
        )

    result = calculate_gex(symbol)
    result["gamma_flip"] = gamma_flip(symbol)
    return result
