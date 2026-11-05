
import math
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf

NY = ZoneInfo("America/New_York")
MULTIPLIER = 100
RISK_FREE_RATE = 0.04
MIN_T = 1 / (365 * 24 * 6)


def bs_gamma(spot, strike, t, iv):
    if spot <= 0 or strike <= 0 or iv <= 0:
        return 0.0

    t = max(t, MIN_T)
    d1 = (
        math.log(spot / strike)
        + (RISK_FREE_RATE + iv * iv / 2) * t
    ) / (iv * math.sqrt(t))

    pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
    return pdf / (spot * iv * math.sqrt(t))


def fetch_chain(symbol="SPY", expiration=None):
    ticker = yf.Ticker(symbol)
    expirations = list(ticker.options)

    if not expirations:
        raise ValueError("No option expirations available")

    expiration = expiration or expirations[0]

    if expiration not in expirations:
        raise ValueError("Expiration not available")

    history = ticker.history(period="5d")
    if history.empty:
        raise ValueError("No underlying price available")

    spot = float(history["Close"].iloc[-1])

    if not math.isfinite(spot) or spot <= 0:
        raise ValueError("Invalid underlying price")

    price_time = str(history.index[-1])
    chain = ticker.option_chain(expiration)

    calls = chain.calls.copy()
    puts = chain.puts.copy()

    calls["type"] = "call"
    puts["type"] = "put"

    raw = pd.concat([calls, puts], ignore_index=True)

    required = [
        "strike", "openInterest", "impliedVolatility"
    ]

    if any(col not in raw.columns for col in required):
        raise ValueError("Required options fields missing")

    for col in required:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    quality = {
        "raw_contracts": len(raw),
        "missing_oi": int(raw["openInterest"].isna().sum()),
        "missing_iv": int(raw["impliedVolatility"].isna().sum()),
    }

    valid = (
        raw["strike"].gt(0)
        & raw["openInterest"].ge(0)
        & raw["impliedVolatility"].gt(0.01)
        & raw["impliedVolatility"].lt(5.0)
    )

    clean = raw.loc[valid].copy()

    if clean.empty:
        raise ValueError("No usable option contracts")

    quality["valid_contracts"] = len(clean)
    quality["excluded_contracts"] = len(raw) - len(clean)

    near = clean[
        clean["strike"].between(spot * 0.95, spot * 1.05)
    ]

    quality["near_spot_calls"] = int(
        (near["type"] == "call").sum()
    )
    quality["near_spot_puts"] = int(
        (near["type"] == "put").sum()
    )

    quality["warning"] = (
        quality["near_spot_calls"] < 10
        or quality["near_spot_puts"] < 10
        or quality["excluded_contracts"] > len(raw) * 0.2
    )

    return {
        "symbol": symbol,
        "spot": spot,
        "price_timestamp": price_time,
        "expiration": expiration,
        "expirations": expirations,
        "chain": clean,
        "quality": quality,
    }


def time_to_expiry(expiration):
    expiry = datetime.combine(
        datetime.fromisoformat(expiration).date(),
        time(16, 0),
        tzinfo=NY,
    )

    remaining = (expiry - datetime.now(NY)).total_seconds()

    if remaining <= 0:
        raise ValueError("Option expiration has passed")

    return max(remaining / (365 * 24 * 3600), MIN_T)


def exposure_profile(chain, spot, t):
    rows = []

    for row in chain.itertuples():
        gamma = bs_gamma(
            spot,
            float(row.strike),
            t,
            float(row.impliedVolatility),
        )

        exposure = (
            gamma
            * float(row.openInterest)
            * MULTIPLIER
            * spot * spot
            * 0.01
        )

        # Assumed dealer long calls / short puts.
        signed = exposure if row.type == "call" else -exposure

        rows.append({
            "strike": float(row.strike),
            "type": row.type,
            "gex": signed,
        })

    df = pd.DataFrame(rows)

    if df.empty:
        raise ValueError("No exposure values")

    pivot = df.pivot_table(
        index="strike",
        columns="type",
        values="gex",
        aggfunc="sum",
        fill_value=0,
    )

    for col in ("call", "put"):
        if col not in pivot.columns:
            pivot[col] = 0.0

    pivot = pivot.reset_index()
    pivot["net_gex"] = pivot["call"] + pivot["put"]

    return pivot.sort_values("strike")


def calculate_v5(symbol="SPY", expiration=None):
    result = fetch_chain(symbol, expiration)
    spot = result["spot"]
    t = time_to_expiry(result["expiration"])
    chain = result["chain"]

    profile = exposure_profile(chain, spot, t)

    calls = profile[profile["call"] > 0]
    puts = profile[profile["put"] < 0]

    call_wall = (
        float(calls.loc[calls["call"].idxmax(), "strike"])
        if not calls.empty else None
    )
    put_wall = (
        float(puts.loc[puts["put"].idxmin(), "strike"])
        if not puts.empty else None
    )

    # Reprice gamma over hypothetical underlying prices.
    spots = np.linspace(spot * 0.85, spot * 1.15, 121)
    nets = np.array([
        exposure_profile(chain, float(s), t)["net_gex"].sum()
        for s in spots
    ])

    crossings = []

    for i in range(len(spots) - 1):
        a, b = nets[i], nets[i + 1]

        if a == 0:
            crossings.append(float(spots[i]))
        elif a * b < 0:
            crossing = spots[i] - a * (
                spots[i + 1] - spots[i]
            ) / (b - a)
            crossings.append(float(crossing))

    flip = (
        min(crossings, key=lambda x: abs(x - spot))
        if crossings else None
    )

    result.update({
        "profile": profile,
        "net_gex": float(profile["net_gex"].sum()),
        "call_gex": float(profile["call"].sum()),
        "put_gex": float(profile["put"].sum()),
        "call_wall": call_wall,
        "put_wall": put_wall,
        "gamma_flip": flip,
        "units": "USD exposure per 1% underlying move",
        "source": "Yahoo Finance / yfinance",
        "position_assumption": "Dealer long calls, short puts",
    })

    return result
