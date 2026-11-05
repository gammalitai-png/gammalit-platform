
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gamma_v5 import calculate_v5, fetch_chain

st.set_page_config(
    page_title="GammaLit AI V5",
    page_icon="📊",
    layout="wide",
)

st.title("GammaLit AI V5")
st.caption("Market-Data Gamma Exposure Analytics")

st.info(
    "Source: Yahoo Finance. Data may be delayed or incomplete. "
    "GEX is modeled using assumed dealer positioning, "
    "not observed dealer holdings."
)

@st.cache_data(ttl=300)
def load_expirations():
    result = fetch_chain("SPY")
    return result["expirations"]

@st.cache_data(ttl=300)
def load_analysis(expiration):
    return calculate_v5("SPY", expiration)

try:
    expirations = load_expirations()
except Exception as exc:
    st.error(f"Unable to retrieve option expirations: {exc}")
    st.stop()

expiration = st.selectbox(
    "Select SPY Expiration",
    expirations,
)

if st.button("Refresh Market Data"):
    st.cache_data.clear()
    st.rerun()

try:
    result = load_analysis(expiration)
except Exception as exc:
    st.error(f"Market-data analysis unavailable: {exc}")
    st.stop()

spot = result["spot"]
profile = result["profile"]
quality = result["quality"]

st.caption(
    f"Latest available underlying bar: "
    f"{result['price_timestamp']}"
)

if quality["warning"]:
    st.warning(
        "Data quality warning: limited near-the-money "
        "coverage or many excluded contracts."
    )

st.subheader("SPY Gamma Exposure")

a, b, c, d = st.columns(4)

a.metric("SPY Reference Price", f"${spot:,.2f}")
b.metric("Net GEX", f"${result['net_gex']:,.0f}")
c.metric("Call Wall", (
    f"{result['call_wall']:,.2f}"
    if result["call_wall"] is not None else "N/A"
))
d.metric("Put Wall", (
    f"{result['put_wall']:,.2f}"
    if result["put_wall"] is not None else "N/A"
))

st.metric(
    "Modeled Gamma Flip",
    f"{result['gamma_flip']:,.2f}"
    if result["gamma_flip"] is not None
    else "No crossing detected",
)

fig = go.Figure()

fig.add_bar(
    x=profile["strike"],
    y=profile["call"],
    name="Call GEX",
    marker_color="#22C55E",
)

fig.add_bar(
    x=profile["strike"],
    y=profile["put"],
    name="Put GEX",
    marker_color="#EF4444",
)

fig.add_scatter(
    x=profile["strike"],
    y=profile["net_gex"],
    mode="lines",
    name="Net GEX",
    line=dict(color="#38BDF8", width=2),
)

fig.add_vline(
    x=spot,
    line_color="#FFFFFF",
    line_dash="dash",
)

fig.update_layout(
    template="plotly_dark",
    height=550,
    barmode="relative",
    title=f"SPY Gamma Exposure — {expiration}",
    xaxis_title="Strike Price",
    yaxis_title="Modeled GEX (USD per 1% move)",
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)

st.subheader("Data Quality")

q1, q2, q3 = st.columns(3)
q1.metric("Retrieved Contracts", quality["raw_contracts"])
q2.metric("Usable Contracts", quality["valid_contracts"])
q3.metric("Excluded Contracts", quality["excluded_contracts"])

st.write(
    "Near-spot calls:", quality["near_spot_calls"],
    " | Near-spot puts:", quality["near_spot_puts"],
)

with st.expander("View Strike-Level Gamma Exposure"):
    st.dataframe(profile, hide_index=True)

with st.expander("View Retrieved Option Chain"):
    st.dataframe(result["chain"], hide_index=True)

st.caption(
    "GEX calculations use a 100-share contract multiplier "
    "and a simplified Black-Scholes model. Gamma flip is "
    "a model estimate, not a verified support/resistance level. "
    "This dashboard is not suitable for live trade execution."
)
