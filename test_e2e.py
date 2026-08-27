"""
End-to-end smoke test against the LIVE Railway deployment: trigger a real
scan → verify results → verify trade-execution/portfolio state → report.

Run from Arkapic/ directory: python3 test_e2e.py

This hits production over the network and can take ~60s (a full scan is
~50s) — it's a smoke test for "is the real system working end-to-end
right now," not a fast unit test. For fast, offline logic tests see
test_scoring.py instead.

Rewritten 2026-08-26 — the previous version imported run_once/
push_to_railway from local_runner.py, the Mac-based scanner that was fully
retired when scanning moved to Railway's own scheduler. That import would
still technically work (the file wasn't deleted) but exercised an
architecture nothing in production uses anymore. This version calls the
real endpoints Railway actually serves.
"""
import time
import requests
from dotenv import load_dotenv
import os

load_dotenv()

RAILWAY_URL = os.getenv("RAILWAY_URL", "https://arka.up.railway.app")
API_TOKEN   = os.getenv("API_SECRET_KEY", "arka-secret-2024")
HEADERS     = {"Authorization": f"Bearer {API_TOKEN}", "Content-Type": "application/json"}


def main():
    print("\n🏥 Step 1: Health check...")
    r = requests.get(f"{RAILWAY_URL}/health", timeout=15)
    r.raise_for_status()
    health = r.json()
    print(f"   status={health.get('status')}  scheduler={health.get('components', {}).get('sp500_scheduler')}")
    if health.get("status") != "healthy":
        print("   ⚠️  Not healthy — aborting.")
        return

    print("\n🔍 Step 2: Triggering a real scan (POST /sp500/refresh-now, ~50s)...")
    t0 = time.time()
    r = requests.post(f"{RAILWAY_URL}/api/v1/sp500/refresh-now", headers=HEADERS, timeout=150)
    elapsed = time.time() - t0
    if r.status_code != 200:
        print(f"   ❌ refresh-now failed: {r.status_code} {r.text[:200]}")
        return
    n = r.json().get("recommendations_available", 0)
    print(f"   ✅ Scan done in {elapsed:.0f}s: {n} recommendations")
    if n == 0:
        print("   ⚠️  No recs returned — likely no signals cleared the score threshold right now, not necessarily a bug.")

    print("\n📊 Step 3: Fetching results (GET /sp500/options-recommendations)...")
    r = requests.get(f"{RAILWAY_URL}/api/v1/sp500/options-recommendations?limit=5&min_score=0.0",
                      headers=HEADERS, timeout=20)
    r.raise_for_status()
    d = r.json()
    recs = d.get("recommendations", [])
    print(f"   total_available={d.get('total_available')}  showing top {len(recs)}")
    for rec in recs:
        f = rec.get("fundamentals") or {}
        pe = f.get("trailing_pe")
        pe_str = f"P/E {pe:.1f}" if pe else ""
        print(f"     {rec['ticker']:<6} {rec['action']:<4} score={rec['score']:.2f}  ${rec['current_price']:.2f}  {pe_str}")
        # Basic sanity on the real data, not just that a response came back
        assert 0.0 <= rec["score"] <= 1.0, f"{rec['ticker']} score out of range: {rec['score']}"
        assert rec["current_price"] > 0, f"{rec['ticker']} has a non-positive price"
        assert rec["thesis"], f"{rec['ticker']} has no thesis text"

    print("\n📈 Step 4: Consistent tickers (GET /sp500/consistent-tickers)...")
    r = requests.get(f"{RAILWAY_URL}/api/v1/sp500/consistent-tickers", headers=HEADERS, timeout=20)
    if r.status_code == 200:
        ct = r.json()
        print(f"   {ct.get('count', 0)} ticker(s) with repeat appearances today")
    else:
        print(f"   {r.status_code} {r.text[:120]}")

    print("\n⚡ Step 5: Options trade execution (POST /paper-trading/execute-now)...")
    r = requests.post(f"{RAILWAY_URL}/api/v1/paper-trading/execute-now", headers=HEADERS, timeout=30)
    if r.status_code == 200:
        d = r.json()
        n = d.get("trades_executed", 0)
        print(f"   {n} trade(s) executed" if n else "   0 trades (positions full or no qualifying signals)")
        for t in d.get("trades", []):
            print(f"     → {t.get('ticker')} {t.get('action')} score={t.get('score')}")
    elif r.status_code == 400 and "closed" in r.text.lower():
        print("   Market closed — expected outside trading hours.")
    else:
        print(f"   {r.status_code} {r.text[:120]}")

    print("\n🏦 Step 6: Stock trading state (read-only — no manual execute-now anymore)...")
    print("   Note: stock trade execution no longer has an HTTP endpoint — the scheduler")
    print("   calls it directly in-process (_sp500_scheduler_loop → stock_trader.execute_signals).")
    print("   That's real architecture, not a gap: nothing external ever needs to trigger it.")
    r = requests.get(f"{RAILWAY_URL}/api/v1/stock-trading/signals?limit=5", headers=HEADERS, timeout=15)
    if r.status_code == 200:
        sigs = r.json().get("signals", [])
        print(f"   Stock signals: {len(sigs)} (showing up to 5)")
        for s in sigs[:3]:
            print(f"     {s.get('ticker'):<6} score={s.get('score'):.2f} ${s.get('current_price'):.2f}")
    elif r.status_code == 503:
        print("   503 — stock trader not connected (check ALPACA_API_KEY on Railway)")
    else:
        print(f"   {r.status_code}")

    print("\n💼 Step 7: Portfolio state...")
    r = requests.get(f"{RAILWAY_URL}/api/v1/paper-trading/portfolio", headers=HEADERS, timeout=15)
    if r.status_code == 200:
        p = r.json().get("portfolio", {})
        print(f"   Options portfolio: equity=${p.get('equity', 0):.2f}, {p.get('open_positions')} positions")

    r = requests.get(f"{RAILWAY_URL}/api/v1/stock-trading/portfolio", headers=HEADERS, timeout=15)
    if r.status_code == 200:
        p = r.json().get("portfolio", {})
        print(f"   Stock portfolio:   equity=${p.get('equity', '?')}, {p.get('open_positions', '?')} positions")
    elif r.status_code == 503:
        print("   Stock portfolio: 503 — stock trader not connected on Railway")

    print("\n✅ End-to-end smoke test complete. Open the iOS app to visually confirm.")


if __name__ == "__main__":
    main()
