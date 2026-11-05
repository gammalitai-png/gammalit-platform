
import math
from datetime import date, timedelta

import numpy as np

# All inputs are synthetic. No live market data is used.
MARKETS = {
    "SPY": {"spot": 600.0, "multiplier": 100},
    "SPX": {"spot": 6000.0, "multiplier": 100},
}


def normal_pdf(x):
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_gamma(spot, strike, time, volatility, rate=0.04):
    """Black-Scholes unit gamma for a European-style option."""
    if min(spot, strike, time, volatility) <= 0:
        return 0.0

    d1 = (
        math.log(spot / strike)
        + (rate + 0.5 * volatility**2) * time
    ) / (volatility * math.sqrt(time))

    return normal_pdf(d1) / (
        spot * volatility * math.sqrt(time)
    )


def simulated_chain(symbol):
    symbol = symbol.upper()

    if symbol not in MARKETS:
        raise ValueError("Supported symbols: SPY, SPX")

    config = MARKETS[symbol]
    spot = config["spot"]
    strikes = np.linspace(spot * 0.90, spot * 1.10, 41)
    expiry = date.today() + timedelta(days=30)

    contracts = []

    for i, strike in enumerate(strikes):
        distance = (strike - spot) / spot
        base_oi = int(
            1000 + 12000 * math.exp(
                -0.5 * (distance / 0.035)**2
            )
        )

        for option_type in ("call", "put"):
            oi = int(
                base_oi * (
                    1.15 if option_type == "call"
                    else 1.05
                )
            )

            # Deterministic, synthetic volatility skew.
            iv = max(
                0.05,
                0.20 - 0.40 * distance
                + 0.02 * abs(distance)
            )

            contracts.append({
                "symbol": symbol,
                "type": option_type,
                "strike": round(float(strike), 2),
                "expiry": expiry.isoformat(),
                "days_to_expiry": 30,
                "open_interest": oi,
                "implied_volatility": round(iv, 6),
            })

    return contracts


def calculate_gex(symbol, spot_override=None):
    symbol = symbol.upper()

    if symbol not in MARKETS:
        raise ValueError("Supported symbols: SPY, SPX")

    config = MARKETS[symbol]
    spot = (
        config["spot"]
        if spot_override is None
        else float(spot_override)
    )

    if not math.isfinite(spot) or spot <= 0:
        raise ValueError("Spot must be positive and finite")

    chain = simulated_chain(symbol)
    exposure = {}

    for contract in chain:
        strike = contract["strike"]
        time = contract["days_to_expiry"] / 365
        gamma = bs_gamma(
            spot,
            strike,
            time,
            contract["implied_volatility"],
        )

        # Illustrative assumption only:
        # dealers long calls and short puts.
        sign = 1 if contract["type"] == "call" else -1

        # Dollar gamma exposure for a 1% underlying move.
        gex = (
            sign
            * gamma
            * contract["open_interest"]
            * config["multiplier"]
            * spot**2
            * 0.01
        )

        if strike not in exposure:
            exposure[strike] = {
                "strike": strike,
                "call_gex": 0.0,
                "put_gex": 0.0,
                "net_gex": 0.0,
            }

        key = (
            "call_gex"
            if contract["type"] == "call"
            else "put_gex"
        )
        exposure[strike][key] += gex
        exposure[strike]["net_gex"] += gex

    levels = sorted(exposure.values(), key=lambda x: x["strike"])

    call_wall = max(levels, key=lambda x: x["call_gex"])
    put_wall = min(levels, key=lambda x: x["put_gex"])
    total_gex = sum(x["net_gex"] for x in levels)

    return {
        "symbol": symbol,
        "spot": spot,
        "data_source": "SIMULATED",
        "dealer_assumption": "long_calls_short_puts",
        "units": "USD gamma exposure per 1% move",
        "net_gex": round(total_gex, 2),
        "call_wall": call_wall["strike"],
        "put_wall": put_wall["strike"],
        "levels": [
            {
                key: round(value, 2)
                for key, value in level.items()
            }
            for level in levels
        ],
    }


def gamma_flip(symbol):
    """Find an approximate zero crossing in modeled net GEX."""
    base_spot = MARKETS[symbol.upper()]["spot"]
    prices = np.linspace(base_spot * 0.85, base_spot * 1.15, 121)

    previous_price = None
    previous_gex = None
    crossings = []

    for price in prices:
        current_gex = calculate_gex(
            symbol, spot_override=float(price)
        )["net_gex"]

        if previous_gex is not None:
            if previous_gex * current_gex < 0:
                fraction = (
                    -previous_gex / (current_gex - previous_gex)
                )
                crossings.append(
                    previous_price
                    + fraction * (price - previous_price)
                )

        previous_price = float(price)
        previous_gex = current_gex

    if not crossings:
        return None

    return round(
        min(crossings, key=lambda x: abs(x - base_spot)),
        2,
    )