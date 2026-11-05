
import math

from gamma_engine import calculate_gex, gamma_flip


def test_spy_output():
    result = calculate_gex("SPY")
    assert result["symbol"] == "SPY"
    assert result["data_source"] == "SIMULATED"
    assert len(result["levels"]) > 0


def test_spx_output():
    result = calculate_gex("SPX")
    assert result["symbol"] == "SPX"
    assert len(result["levels"]) > 0


def test_gamma_arithmetic():
    for symbol in ("SPY", "SPX"):
        result = calculate_gex(symbol)

        for level in result["levels"]:
            expected = level["call_gex"] + level["put_gex"]

            assert math.isclose(
                level["net_gex"],
                expected,
                rel_tol=1e-6,
                abs_tol=0.05,
            )


def test_gamma_flip():
    for symbol in ("SPY", "SPX"):
        flip = gamma_flip(symbol)

        assert flip is None or (
            isinstance(flip, (int, float))
            and math.isfinite(flip)
        )
