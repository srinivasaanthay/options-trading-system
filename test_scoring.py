"""
Unit tests for the core scoring/analysis pipeline in app.py.

Scope: pure/near-pure functions only — no live network calls, no market
hours dependency, no Postgres/Railway. Run anytime with:

    python3 -m pytest test_scoring.py -v

Why this exists: every real bug found this session (MSTR showing a price
outside its own day's range, signal colors backwards, thesis text
disconnected from the actual score) lived in exactly this logic and was
only caught by manual, one-off inspection. These tests exist so a
regression here fails a test run instead of waiting for someone to notice
a wrong number in the app.
"""
import types
import pytest

import app as app_module
from app import (
    _interpret_composite_score,
    _is_price_plausible,
    _strike_for_action,
    _compute_long_term_score,
    _make_options_rec,
    _generate_thesis,
    _generate_key_factors_and_risks,
    _append_catalyst_narrative,
    _compute_consistent_tickers,
    OptionsRecommendation,
)
from mcp_stock_agent import BuySignal


def make_analysis_result(**overrides):
    """A minimal stand-in for the real AnalysisResult object _make_options_rec
    consumes — only the attributes it actually reads (some via getattr with
    defaults, buy_signal directly), with the same defaults the real
    dataclass uses."""
    defaults = dict(
        technical_score=0.60, sentiment_score=0.10, ml_score=0.70,
        buy_signal=BuySignal.ACCUMULATE,
        iv_rank=50.0, volume_ratio=1.0, rs_vs_spy=0.0,
        fundamental_score=0.5, analyst_upside=0.0, days_to_earnings=999,
        rsi=50.0, market_score=0.5, avg_dollar_volume=0.0,
    )
    defaults.update(overrides)
    return types.SimpleNamespace(**defaults)


# ── _interpret_composite_score ────────────────────────────────────────────

@pytest.mark.parametrize("score,expected_signal", [
    (0.85, "STRONG_BUY"),
    (0.80, "STRONG_BUY"),
    (0.75, "BUY"),
    (0.70, "BUY"),
    (0.68, "ACCUMULATE"),
    (0.65, "ACCUMULATE"),
    (0.60, "HOLD"),
    (0.55, "HOLD"),
    (0.54, "AVOID"),
    (0.10, "AVOID"),
])
def test_interpret_composite_score_thresholds(score, expected_signal):
    _, buy_signal = _interpret_composite_score(score)
    assert buy_signal == expected_signal


def test_interpret_composite_score_confidence_matches_signal_strength():
    confidence, _ = _interpret_composite_score(0.90)
    assert confidence == "VERY_HIGH"
    confidence, _ = _interpret_composite_score(0.10)
    assert confidence == "VERY_LOW"


# ── _is_price_plausible — the MSTR bug, as a permanent regression test ────

def test_price_plausible_regression_mstr_bug():
    """The exact real-world scenario that shipped a wrong BUY signal: a
    fetched price of $115.74 while MSTR's real intraday range that day was
    $119.38-$127.90. Must be rejected."""
    assert _is_price_plausible(115.74, today_low=119.38, today_high=127.90) is False


def test_price_plausible_accepts_price_within_range():
    assert _is_price_plausible(122.62, today_low=119.38, today_high=127.90) is True


def test_price_plausible_accepts_small_buffer_beyond_range():
    # 3% buffer above high / 3% below low for bid-ask spread and rounding
    assert _is_price_plausible(127.90 * 1.02, today_low=119.38, today_high=127.90) is True
    assert _is_price_plausible(119.38 * 0.98, today_low=119.38, today_high=127.90) is True


def test_price_plausible_rejects_beyond_buffer():
    assert _is_price_plausible(127.90 * 1.10, today_low=119.38, today_high=127.90) is False
    assert _is_price_plausible(119.38 * 0.80, today_low=119.38, today_high=127.90) is False


def test_price_plausible_true_when_no_range_data_available():
    # Can't reject what we have nothing to check it against
    assert _is_price_plausible(100.0, today_low=None, today_high=None) is True
    assert _is_price_plausible(100.0, today_low=0.0, today_high=0.0) is True


# ── _strike_for_action ──────────────────────────────────────────────────

def test_strike_for_action_call_rounds_up_and_otm():
    assert _strike_for_action(122.62, "CALL") == 125  # nearest $5 is 125 (>122.62), already OTM
    assert _strike_for_action(120.0, "CALL") == 120    # exactly on a $5 mark stays ATM, not bumped


def test_strike_for_action_put_rounds_down_and_otm():
    assert _strike_for_action(122.62, "PUT") == 120
    assert _strike_for_action(120.0, "PUT") == 120     # exactly on a $5 mark stays ATM, not bumped


# ── _compute_long_term_score — bullish vs bearish weighting differs ──────

def test_long_term_score_bullish_rewards_fundamentals_and_upside():
    bullish = _compute_long_term_score(tech=0.8, rs_score=0.8, fund=0.9, analyst_upside=20.0, is_bearish=False)
    assert 0.0 <= bullish <= 1.0
    assert bullish > 0.5  # strong fundamentals + upside should score well


def test_long_term_score_bearish_inverts_technical_weighting():
    # A bearish (weak technicals) case should score differently than treating
    # the same weak technical_score as if it were bullish input
    bearish = _compute_long_term_score(tech=0.2, rs_score=0.2, fund=0.5, analyst_upside=0.0, is_bearish=True)
    bullish_same_inputs = _compute_long_term_score(tech=0.2, rs_score=0.2, fund=0.5, analyst_upside=0.0, is_bearish=False)
    assert bearish != bullish_same_inputs


# ── _make_options_rec — the core scoring integration ──────────────────────

def test_make_options_rec_bullish_when_technical_score_high():
    result = make_analysis_result(technical_score=0.75, rs_vs_spy=3.0)
    rec = _make_options_rec("AAPL", result, price=200.0)
    assert rec.action == "CALL"
    assert rec.strike_price > 0
    assert 0.0 <= rec.score <= 1.0
    assert rec.thesis  # non-empty — every rec must have a real explanation


def test_make_options_rec_bearish_when_signal_is_avoid():
    # is_bearish triggers on technical_score < 0.48 OR buy_signal in HOLD/AVOID —
    # here technical_score alone is enough
    result = make_analysis_result(technical_score=0.30)
    rec = _make_options_rec("XYZ", result, price=50.0)
    assert rec.action == "PUT"


def test_make_options_rec_same_day_reversal_penalizes_score():
    """A CALL that's already faded well off today's own high should score
    lower than the identical setup without that fade — this is the fix for
    the blind spot where daily-bar technicals can't see an intraday reversal."""
    result = make_analysis_result(technical_score=0.75, rs_vs_spy=3.0)
    price = 100.0
    rec_no_fade = _make_options_rec("AAPL", result, price=price, today_high=100.5, today_low=95.0)
    rec_faded = _make_options_rec("AAPL", result, price=price, today_high=110.0, today_low=95.0)  # faded ~9% off high
    assert rec_faded.score < rec_no_fade.score
    assert rec_faded.intraday_move_pct < 0


def test_make_options_rec_populates_key_factors_and_risks():
    result = make_analysis_result(technical_score=0.75, rs_vs_spy=3.0, volume_ratio=2.0)
    rec = _make_options_rec("AAPL", result, price=200.0)
    assert isinstance(rec.key_factors, list) and len(rec.key_factors) > 0
    assert isinstance(rec.risks, list) and len(rec.risks) > 0


def test_make_options_rec_day_change_pct_uses_prev_close_not_intraday_extremes():
    """day_change_pct is today's overall move vs prior close — independent
    of today_high/today_low (which only affect intraday_move_pct/score)."""
    result = make_analysis_result(technical_score=0.75, rs_vs_spy=3.0)
    rec = _make_options_rec("AAPL", result, price=106.0, prev_close=100.0)
    assert rec.day_change_pct == 6.0


def test_make_options_rec_day_change_pct_defaults_to_zero_without_prev_close():
    result = make_analysis_result(technical_score=0.75, rs_vs_spy=3.0)
    rec = _make_options_rec("AAPL", result, price=106.0)
    assert rec.day_change_pct == 0.0


def test_make_options_rec_avg_dollar_volume_passthrough():
    """Absolute, cross-ticker liquidity measure — distinct from volume_ratio,
    which is self-relative and can't tell a genuinely liquid stock (e.g.
    NVDA) apart from a thin one (e.g. TORM) having a busier-than-usual day."""
    result = make_analysis_result(technical_score=0.75, avg_dollar_volume=5_000_000_000.0)
    rec = _make_options_rec("NVDA", result, price=200.0)
    assert rec.avg_dollar_volume == 5_000_000_000.0


# ── _generate_thesis — direction-consistency, the specific bug from earlier ─

def test_generate_thesis_bullish_text_matches_call_action():
    thesis = _generate_thesis(
        "UBER", "CALL", score=0.79, confidence="HIGH", tech=0.75, rs=6.9,
        iv_rank=22.0, vol_ratio=1.3, intraday_move_pct=0.0, price=79.59,
        strike=80.0, days_to_earnings=999, rsi=58.0, market_score=0.68,
    )
    assert "bullish" in thesis.lower()
    assert "bearish" not in thesis.lower()
    assert "UBER" in thesis


def test_generate_thesis_bearish_text_matches_put_action():
    """Regression test for the original bug: thesis text used to come from
    a separate code path and could say 'positioned for upside appreciation'
    while the actual verdict was PUT/AVOID. Must never happen again."""
    thesis = _generate_thesis(
        "AAPL", "PUT", score=0.45, confidence="VERY_LOW", tech=0.56, rs=2.8,
        iv_rank=29.0, vol_ratio=0.66, intraday_move_pct=0.0, price=310.72,
        strike=310.0, days_to_earnings=999, rsi=50.0, market_score=0.5,
    )
    assert "bearish" in thesis.lower()
    assert "upside appreciation" not in thesis.lower()


def test_generate_thesis_never_crashes_across_score_range():
    for score in [0.0, 0.25, 0.5, 0.75, 1.0]:
        for action in ["CALL", "PUT"]:
            thesis = _generate_thesis(
                "TEST", action, score=score, confidence="MODERATE", tech=score,
                rs=0.0, iv_rank=50.0, vol_ratio=1.0, intraday_move_pct=0.0,
                price=100.0, strike=100.0, days_to_earnings=999, rsi=50.0, market_score=0.5,
            )
            assert isinstance(thesis, str) and len(thesis) > 0


def test_append_catalyst_narrative_fresh_vs_stale():
    base = "Base thesis."
    fresh = _append_catalyst_narrative(base, "AAPL", catalyst_age_days=0, price_change_since_catalyst=0.0)
    stale = _append_catalyst_narrative(base, "AAPL", catalyst_age_days=10, price_change_since_catalyst=15.0)
    no_catalyst = _append_catalyst_narrative(base, "AAPL", catalyst_age_days=-1, price_change_since_catalyst=0.0)
    assert fresh != base and "today" in fresh.lower()
    assert stale != base and "already" in stale.lower()
    assert no_catalyst == base  # -1 means no news found, nothing to append


# ── _compute_consistent_tickers ───────────────────────────────────────────

def test_compute_consistent_tickers_ranks_by_appearance_count(monkeypatch):
    snapshots = [
        {'hour_label': '12:00 PM', 'recommendations': [
            {'ticker': 'AAPL', 'action': 'CALL', 'score': 0.78},
            {'ticker': 'TSLA', 'action': 'PUT', 'score': 0.71},
        ]},
        {'hour_label': '11:00 AM', 'recommendations': [
            {'ticker': 'AAPL', 'action': 'CALL', 'score': 0.75},
            {'ticker': 'MSTR', 'action': 'CALL', 'score': 0.69},
        ]},
        {'hour_label': '10:00 AM', 'recommendations': [
            {'ticker': 'AAPL', 'action': 'CALL', 'score': 0.72},
        ]},
    ]
    monkeypatch.setattr(app_module, "hourly_snapshots", snapshots)
    results = _compute_consistent_tickers()

    by_ticker = {r['ticker']: r for r in results}
    assert by_ticker['AAPL']['appearances'] == 3
    assert by_ticker['AAPL']['first_seen_hour'] == '10:00 AM'
    assert by_ticker['AAPL']['still_active'] is True
    assert by_ticker['MSTR']['still_active'] is False  # not in the latest (12PM) snapshot
    # Ranked by appearances descending — AAPL (3) must come before TSLA/MSTR (1 each)
    assert results[0]['ticker'] == 'AAPL'


def test_compute_consistent_tickers_empty_when_no_snapshots(monkeypatch):
    monkeypatch.setattr(app_module, "hourly_snapshots", [])
    assert _compute_consistent_tickers() == []
