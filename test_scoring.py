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


# ── Broad market news (mcp_stock_agent.MCPStockAgent) ──────────────────────
# Replaced ~1,650 per-ticker Alpaca news calls with one market-wide pull;
# Alpaca tags each article with the tickers it covers, so that single batch
# doubles as both the sentiment source and the "breaking news" discovery
# feed. See _fetch_broad_market_news / get_news_matched_tickers.

@pytest.fixture
def agent():
    from mcp_stock_agent import MCPStockAgent
    return MCPStockAgent()


class _FakeArticle:
    def __init__(self, headline, symbols):
        self.headline = headline
        self.symbols = symbols


class _FakeNewsResponse:
    def __init__(self, articles):
        self.data = {'news': articles}


def _patch_alpaca_news(monkeypatch, articles):
    import alpaca.data.historical.news as news_module

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        def get_news(self, req):
            return _FakeNewsResponse(articles)

    monkeypatch.setattr(news_module, "NewsClient", _FakeClient)


def test_score_headlines_none_when_no_keywords_match(agent):
    assert agent._score_headlines(["Some headline with no tracked words"]) is None


def test_score_headlines_bullish_beats_bearish_net_positive(agent):
    result = agent._score_headlines(["Company beats estimates and raises guidance"])
    assert result is not None
    assert result['overall_sentiment'] > 0
    assert result['trend'] == 'improving'


def test_score_headlines_skips_market_wide_openers(agent):
    # "Stocks... higher" opens with a MARKET_OPENERS word — shouldn't count
    # toward any single ticker's sentiment even though "higher" isn't tracked
    # anyway; this checks the opener-skip path itself using a tracked word.
    result = agent._score_headlines(["Stocks surge as investors cheer earnings"])
    assert result is None  # "surge" only appears in a skipped opener headline


def test_fetch_broad_market_news_groups_by_tagged_symbol(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company beats estimates, shares soar", ["NVDA"]),
        _FakeArticle("Firm cuts guidance after weak quarter, layoffs planned", ["MSTR"]),
        _FakeArticle("Nothing notable happened today", ["ZZZZ"]),  # no keyword hit
    ])
    result = agent._fetch_broad_market_news()
    assert result["NVDA"]["overall_sentiment"] > 0
    assert result["MSTR"]["overall_sentiment"] < 0
    assert "ZZZZ" not in result  # no signal after scoring -> excluded, not zero


def test_fetch_broad_market_news_multi_symbol_article_scores_all_tagged_tickers(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Sector rallies as both firms beat expectations", ["AAPL", "MSFT"]),
    ])
    result = agent._fetch_broad_market_news()
    assert "AAPL" in result and "MSFT" in result


def test_fetch_broad_market_news_caches_for_30_minutes(agent, monkeypatch):
    calls = {"n": 0}
    import alpaca.data.historical.news as news_module

    class _CountingClient:
        def __init__(self, *a, **kw):
            pass

        def get_news(self, req):
            calls["n"] += 1
            return _FakeNewsResponse([_FakeArticle("Company beats estimates", ["NVDA"])])

    monkeypatch.setattr(news_module, "NewsClient", _CountingClient)
    agent._fetch_broad_market_news()
    agent._fetch_broad_market_news()
    assert calls["n"] == 1  # second call served from cache


def test_get_news_matched_tickers_returns_symbol_set(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company beats estimates", ["NVDA"]),
    ])
    assert agent.get_news_matched_tickers() == {"NVDA"}


def test_fetch_real_news_data_returns_real_sentiment_for_matched_ticker(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company beats estimates and raises guidance", ["NVDA"]),
    ])
    result = agent._fetch_real_news_data("NVDA")
    assert result['overall_sentiment'] > 0
    assert result['news_count'] == 1


def test_fetch_real_news_data_neutral_when_ticker_not_in_broad_feed(agent, monkeypatch):
    # The overwhelming common case: a ticker not among the ~50 top market
    # headlines this cycle. Must be neutral (0.5 normalized), not a
    # price-momentum proxy that would double-count the technical/strategy
    # weights already derived from the same price action.
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company beats estimates", ["NVDA"]),
    ])
    result = agent._fetch_real_news_data("SOME_UNRELATED_TICKER")
    assert result['overall_sentiment'] == 0.0
    assert result['news_count'] == 0


def test_fetch_real_news_data_neutral_on_api_failure_with_no_prior_cache(agent, monkeypatch):
    import alpaca.data.historical.news as news_module

    class _BrokenClient:
        def __init__(self, *a, **kw):
            pass

        def get_news(self, req):
            raise RuntimeError("Alpaca unavailable")

    monkeypatch.setattr(news_module, "NewsClient", _BrokenClient)
    result = agent._fetch_real_news_data("AAPL")
    assert result['overall_sentiment'] == 0.0


def test_get_top_headlines_returns_most_recent_first_with_tickers(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company beats estimates", ["NVDA"]),
        _FakeArticle("Firm cuts guidance after weak quarter", ["MSTR"]),
    ])
    headlines = agent.get_top_headlines(limit=10)
    assert headlines[0] == {'headline': "Company beats estimates", 'tickers': ["NVDA"]}
    assert headlines[1] == {'headline': "Firm cuts guidance after weak quarter", 'tickers': ["MSTR"]}


def test_get_top_headlines_respects_limit(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle(f"Headline number {i}", ["AAPL"]) for i in range(20)
    ])
    assert len(agent.get_top_headlines(limit=5)) == 5


def test_get_top_headlines_dedupes_same_story_tagged_to_multiple_tickers(agent, monkeypatch):
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Sector rallies on trade news", ["AAPL"]),
        _FakeArticle("Sector rallies on trade news", ["MSFT"]),
    ])
    headlines = agent.get_top_headlines(limit=10)
    assert len(headlines) == 1


def test_get_top_headlines_includes_headlines_with_no_scored_sentiment(agent, monkeypatch):
    # A headline with no tracked keyword still belongs on a banner (it's
    # real news) even though it contributes nothing to the sentiment score.
    _patch_alpaca_news(monkeypatch, [
        _FakeArticle("Company announces new product lineup", ["AAPL"]),
    ])
    headlines = agent.get_top_headlines(limit=10)
    assert len(headlines) == 1


# ── Market pulse (banner's fixed SPY/VIX chip) ──────────────────────────────

def _patch_market_data(agent, monkeypatch, **overrides):
    data = {
        'spy_change_pct': 0.0,
        'vix': 20.0,
        'volatility': {'regime': 'medium'},
    }
    data.update(overrides)
    monkeypatch.setattr(agent, "_fetch_real_market_data", lambda: data)


def test_market_pulse_quiet_session_when_flat_and_low_vix(agent, monkeypatch):
    _patch_market_data(agent, monkeypatch, spy_change_pct=0.05,
                        vix=13.0, volatility={'regime': 'low'})
    pulse = agent.get_market_pulse()
    assert pulse['summary'] == 'Quiet session'


def test_market_pulse_rallying_on_strong_positive_change(agent, monkeypatch):
    _patch_market_data(agent, monkeypatch, spy_change_pct=1.2,
                        vix=14.0, volatility={'regime': 'low'})
    assert agent.get_market_pulse()['summary'] == 'Rallying'


def test_market_pulse_selling_off_on_strong_negative_change(agent, monkeypatch):
    _patch_market_data(agent, monkeypatch, spy_change_pct=-0.8,
                        vix=18.0, volatility={'regime': 'medium'})
    assert agent.get_market_pulse()['summary'] == 'Selling off'


def test_market_pulse_volatile_takes_priority_over_direction(agent, monkeypatch):
    # High VIX should read as "Volatile" even on a day SPY is up strongly —
    # the fear gauge matters more here than which way price moved.
    _patch_market_data(agent, monkeypatch, spy_change_pct=1.5,
                        vix=32.0, volatility={'regime': 'high'})
    assert agent.get_market_pulse()['summary'] == 'Volatile'


def test_market_pulse_mixed_when_neither_quiet_nor_directional(agent, monkeypatch):
    _patch_market_data(agent, monkeypatch, spy_change_pct=0.4,
                        vix=19.0, volatility={'regime': 'medium'})
    assert agent.get_market_pulse()['summary'] == 'Mixed'


def test_market_pulse_passes_through_spy_change_and_vix(agent, monkeypatch):
    _patch_market_data(agent, monkeypatch, spy_change_pct=-0.55,
                        vix=15.72, volatility={'regime': 'low'})
    pulse = agent.get_market_pulse()
    assert pulse['spy_change_pct'] == -0.55
    assert pulse['vix'] == 15.72
    assert pulse['vix_regime'] == 'low'
