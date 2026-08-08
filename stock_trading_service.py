"""
Stock Trading Service — Alpaca Paper API, direct stock positions.

Buys fractional shares ($1,000 per signal) on CALL/bullish signals.
Exits on -5% stop-loss, +10% take-profit, or 48-hour hold limit.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class StockTradeRecord:
    ticker: str
    qty: float
    entry_price: float
    entry_time: str
    stop_loss: float
    take_profit: float
    signal_score: float
    notional: float

    exit_price: Optional[float] = None
    exit_time:  Optional[str]   = None
    pnl:        Optional[float] = None
    pnl_pct:    Optional[float] = None
    status: str = "open"
    alpaca_order_id: Optional[str] = None
    notes: str = ""


class StockTradingService:
    POSITION_SIZE    = 1_000.0   # $ per trade (fractional shares)
    STOP_LOSS_PCT    = 0.05      # exit if underlying drops 5%
    TAKE_PROFIT_PCT  = 0.10      # exit if underlying gains 10%
    MIN_SIGNAL_SCORE = 0.80
    MAX_OPEN_POSITIONS = 8
    COOLDOWN_HOURS   = 6
    DAILY_MAX_LOSS   = 2_000.0
    HOLD_HOURS       = 48

    def __init__(self, api_key: str, api_secret: str, dry_run: bool = True):
        self.api_key    = api_key
        self.api_secret = api_secret
        # ── TEST ONLY: dry_run=True = predictions only, no real orders ──────────
        # Set dry_run=False (via STOCK_ORDERS_ENABLED env var) to place real orders.
        # Remove this flag and the dry_run guard in _place_stock_order after testing.
        self.dry_run    = dry_run
        # ────────────────────────────────────────────────────────────────────────
        self.client     = None
        self.data_client = None
        self.connected  = False
        self.trade_history: List[StockTradeRecord] = []
        self._last_traded: Dict[str, datetime] = {}
        self._daily_loss_date:    Optional[str]  = None
        self._daily_loss_tripped: bool           = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
            self.client      = TradingClient(self.api_key, self.api_secret, paper=True)
            self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
            acc = self.client.get_account()
            logger.info("[StockTrading] Connected — equity=$%.2f", float(acc.equity))
            self.connected = True
            return True
        except Exception as e:
            logger.error("[StockTrading] Connection failed: %s", e)
            self.connected = False
            return False

    # ── Portfolio ──────────────────────────────────────────────────────────────

    def get_positions(self) -> List[Dict]:
        if not self.connected:
            return []
        try:
            positions = self.client.get_all_positions()
            result = []
            for p in positions:
                sym = p.symbol
                # skip options contracts
                if len(sym) > 10 or any(c.isdigit() for c in sym):
                    continue
                result.append({
                    "symbol":          sym,
                    "qty":             float(p.qty),
                    "market_value":    float(p.market_value or 0),
                    "unrealized_pnl":  float(p.unrealized_pl or 0),
                    "unrealized_pnl_pct": float(p.unrealized_plpc or 0) * 100,
                    "entry_price":     float(p.avg_entry_price or 0),
                    "current_price":   float(p.current_price or 0),
                    "change_today":    float(p.change_today or 0),
                })
            return result
        except Exception as e:
            logger.error("[StockTrading] get_positions failed: %s", e)
            return []

    def get_portfolio_snapshot(self) -> Dict:
        try:
            acc = self.client.get_account()
            positions   = self.get_positions()
            unrealized  = sum(p["unrealized_pnl"] for p in positions)
            closed = [t for t in self.trade_history if t.status == "closed" and t.pnl is not None]
            realized    = sum(t.pnl for t in closed)
            winners     = [t for t in closed if (t.pnl or 0) > 0]
            equity      = float(acc.equity)
            total_ret   = ((equity - 100_000.0) / 100_000.0) * 100
            return {
                "timestamp":       datetime.utcnow().isoformat(),
                "cash":            float(acc.cash),
                "equity":          equity,
                "unrealized_pnl":  round(unrealized, 2),
                "realized_pnl":    round(realized, 2),
                "total_return_pct": round(total_ret, 2),
                "open_positions":  len(positions),
                "total_trades":    len(closed),
                "win_rate":        round(len(winners) / len(closed) * 100, 1) if closed else 0.0,
            }
        except Exception as e:
            logger.error("[StockTrading] snapshot failed: %s", e)
            return {}

    # ── Signal execution ───────────────────────────────────────────────────────

    def execute_signals(self, recommendations: List[Dict]) -> List[Dict]:
        if not self.connected:
            return []

        # Daily circuit breaker
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self._daily_loss_date != today:
            self._daily_loss_date    = today
            self._daily_loss_tripped = False
        if self._daily_loss_tripped:
            logger.warning("[StockTrading] Daily max loss tripped — no new entries today")
            return []

        try:
            acc = self.client.get_account()
            unrealized = float(getattr(acc, 'unrealized_pl', 0) or 0)
            closed_today = [t for t in self.trade_history
                            if t.status == "closed" and t.pnl is not None
                            and (t.exit_time or "").startswith(today)]
            realized_today = sum(t.pnl for t in closed_today)
            if realized_today + min(0.0, unrealized) <= -self.DAILY_MAX_LOSS:
                self._daily_loss_tripped = True
                return []
        except Exception:
            pass

        # Only bullish (CALL) signals
        eligible = [r for r in recommendations
                    if r.get("action") == "CALL" and r.get("score", 0) >= self.MIN_SIGNAL_SCORE]
        if not eligible:
            return []

        open_positions = self.get_positions()
        open_tickers   = {p["symbol"] for p in open_positions}
        slots = self.MAX_OPEN_POSITIONS - len(open_positions)
        if slots <= 0:
            logger.info("[StockTrading] Max positions reached")
            return []

        results = []
        for rec in sorted(eligible, key=lambda x: -x["score"])[:slots]:
            ticker = rec.get("ticker", "")
            price  = float(rec.get("current_price", 0))
            score  = float(rec.get("score", 0))

            if not ticker or price <= 0:
                continue
            if ticker in open_tickers:
                continue
            if self._is_in_cooldown(ticker):
                continue

            # Real-time price staleness check
            rt_price = self._get_realtime_price(ticker)
            if rt_price and price > 0:
                drift = abs(rt_price - price) / price
                if drift > 0.03:
                    logger.info("[StockTrading] Skipping %s — price drifted %.1f%% since rec", ticker, drift * 100)
                    continue
                price = rt_price

            trade = self._place_stock_order(ticker, price, score)
            if trade:
                results.append(trade)
                open_tickers.add(ticker)
                self._last_traded[ticker] = datetime.utcnow()

        self._close_expired_positions()
        logger.info("[StockTrading] Executed %d stock trades this cycle", len(results))
        return results

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _place_stock_order(self, ticker: str, price: float, score: float) -> Optional[Dict]:
        try:
            qty         = round(self.POSITION_SIZE / price, 4)
            limit_price = round(price, 2)
            stop_loss   = round(price * (1 - self.STOP_LOSS_PCT), 2)
            take_profit = round(price * (1 + self.TAKE_PROFIT_PCT), 2)

            order_id = "DRY_RUN"

            # ── TEST ONLY: real order placement — remove block after testing ────
            if not self.dry_run:
                from alpaca.trading.requests import LimitOrderRequest
                from alpaca.trading.enums import OrderSide, TimeInForce
                order = LimitOrderRequest(
                    symbol=ticker,
                    qty=qty,
                    side=OrderSide.BUY,
                    type="limit",
                    limit_price=limit_price,
                    time_in_force=TimeInForce.DAY,
                )
                result = self.client.submit_order(order)
                order_id = str(result.id)
            # ────────────────────────────────────────────────────────────────────

            trade = StockTradeRecord(
                ticker=ticker,
                qty=qty,
                entry_price=limit_price,
                entry_time=datetime.utcnow().isoformat(),
                stop_loss=stop_loss,
                take_profit=take_profit,
                signal_score=score,
                notional=self.POSITION_SIZE,
                alpaca_order_id=order_id,
                notes="dry_run" if self.dry_run else "",
            )
            self.trade_history.append(trade)
            mode = "[DRY RUN]" if self.dry_run else ""
            logger.info("[StockTrading]%s Would buy %s × %.4f @ $%.2f (stop $%.2f / tp $%.2f)",
                        mode, ticker, qty, limit_price, stop_loss, take_profit)
            return asdict(trade)
        except Exception as e:
            logger.error("[StockTrading] Order failed for %s: %s", ticker, e)
            return None

    def _close_expired_positions(self) -> None:
        if not self.connected:
            return
        try:
            open_trades = [t for t in self.trade_history if t.status == "open"]
            now = datetime.now(timezone.utc)
            for trade in open_trades:
                entry_dt = datetime.fromisoformat(trade.entry_time.replace("Z", "+00:00"))
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - entry_dt).total_seconds() / 3600

                current = self._get_realtime_price(trade.ticker) or trade.entry_price
                hit_stop   = current <= trade.stop_loss
                hit_target = current >= trade.take_profit

                if age_hours >= self.HOLD_HOURS or hit_stop or hit_target:
                    reason = ("expired" if age_hours >= self.HOLD_HOURS
                              else "stop_loss" if hit_stop else "take_profit")
                    self._close_position(trade, current, reason)
        except Exception as e:
            logger.error("[StockTrading] _close_expired_positions failed: %s", e)

    def _close_position(self, trade: StockTradeRecord, current: float, reason: str) -> None:
        try:
            self.client.close_position(trade.ticker)
            pnl_pct = ((current - trade.entry_price) / trade.entry_price) * 100
            pnl     = trade.notional * (pnl_pct / 100)
            trade.exit_price = current
            trade.exit_time  = datetime.utcnow().isoformat()
            trade.pnl        = round(pnl, 2)
            trade.pnl_pct    = round(pnl_pct, 2)
            trade.status     = "closed"
            trade.notes      = reason
            logger.info("[StockTrading] Closed %s @ $%.2f (%.2f%%) reason=%s",
                        trade.ticker, current, pnl_pct, reason)
        except Exception as e:
            logger.error("[StockTrading] Close failed for %s: %s", trade.ticker, e)

    def close_all(self) -> int:
        if not self.connected:
            return 0
        closed = 0
        for p in self.get_positions():
            try:
                self.client.close_position(p["symbol"])
                closed += 1
            except Exception as e:
                logger.error("[StockTrading] Could not close %s: %s", p["symbol"], e)
        return closed

    def _get_realtime_price(self, ticker: str) -> Optional[float]:
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            quotes = self.data_client.get_stock_latest_quote(
                StockLatestQuoteRequest(symbol_or_symbols=ticker))
            q = quotes.get(ticker)
            if q:
                ask = float(q.ask_price or 0)
                bid = float(q.bid_price or 0)
                return (ask + bid) / 2 if ask > 0 and bid > 0 else ask or bid or None
        except Exception:
            pass
        return None

    def _is_in_cooldown(self, ticker: str) -> bool:
        last = self._last_traded.get(ticker)
        if last is None:
            return False
        return (datetime.utcnow() - last).total_seconds() < self.COOLDOWN_HOURS * 3600
