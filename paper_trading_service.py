"""
Paper Trading Service — Alpaca Paper API integration (Real Options)

Buys actual options contracts based on SP500 signals:
  CALL signal → BUY a CALL option on the underlying (ATM, ~30-day expiry)
  PUT  signal → BUY a PUT option on the underlying  (ATM, ~30-day expiry)

Position sizing: 1 contract per signal (~$500 notional in premium)
Exit strategy: sell the contract when the underlying hits 5% take-profit
  or 3% stop-loss vs. the entry price, or after 24 hours.
"""

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class TradeRecord:
    ticker: str
    direction: str          # "LONG" (call bought) or "SHORT" (put bought)
    qty: float              # number of contracts
    entry_price: float      # underlying price at signal time
    entry_time: str
    stop_loss: float        # underlying price level
    take_profit: float      # underlying price level
    signal_score: float
    signal_source: str      # "CALL" or "PUT"

    # Options contract info
    option_symbol: Optional[str] = None
    option_strike: Optional[float] = None
    option_expiry: Optional[str] = None

    entry_intraday_move: float = 0.0  # % move of underlying at entry (detects chased entries)
    entry_hour_et: int = -1           # ET hour of entry (detects out-of-window entries)

    # Filled after close
    exit_price: Optional[float] = None
    exit_time: Optional[str] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "open"    # "open" | "closed" | "error"
    alpaca_order_id: Optional[str] = None
    notes: str = ""


@dataclass
class PortfolioSnapshot:
    timestamp: str
    cash: float
    portfolio_value: float
    equity: float
    unrealized_pnl: float
    realized_pnl: float
    total_return_pct: float
    open_positions: int
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float


class PaperTradingService:
    """
    Manages options paper-trading execution against Alpaca's Paper API.

    Usage:
        service = PaperTradingService(api_key, api_secret)
        service.connect()
        service.execute_signals(recs)   # call after each SP500 analysis
    """

    STARTING_CAPITAL    = 100_000.0
    MAX_OPEN_POSITIONS  = 10
    HOLD_HOURS          = 24
    STOP_LOSS_PCT       = 0.03      # close if underlying moves 3% against us
    TAKE_PROFIT_PCT     = 0.05      # close if underlying moves 5% in our favour
    MIN_SIGNAL_SCORE    = 0.70
    COOLDOWN_HOURS      = 6
    MIN_EXPIRY_DAYS     = 25        # minimum days to expiry when entering
    MAX_EXPIRY_DAYS     = 50        # maximum days to expiry when entering
    DAILY_MAX_LOSS      = 2_000.0   # stop new entries if realized+unrealized loss exceeds this today
    OPTION_MULTIPLIER   = 100.0     # contract-to-share multiplier for standard equity options
    MIN_OPEN_INTEREST   = 1000      # below this, contracts are too thin to trade reliably

    # Real standing stop/target orders placed on the OPTION premium itself at
    # entry time — not the STOP_LOSS_PCT/TAKE_PROFIT_PCT underlying-move check
    # above, which only fires when a scan happens to run. A position opened
    # Friday afternoon gets zero protection all weekend under that check (see
    # the Aug 14->17 batch: held 70+ hours against a 24h rule, no scan to
    # notice). These orders sit with Alpaca directly and can fire any time
    # the market's open, including the instant Monday opens.
    OPTION_STOP_PCT     = 0.40      # sell if premium drops 40% from entry
    OPTION_TARGET_PCT    = 0.60      # sell if premium rises 60% from entry

    def __init__(self, api_key: str, api_secret: str):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.client     = None
        self.data_client = None
        self.connected  = False

        self.trade_history: List[TradeRecord] = []
        self._last_traded: Dict[str, datetime] = {}
        self._daily_loss_date: Optional[str] = None
        self._daily_loss_tripped: bool = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient

            self.client = TradingClient(self.api_key, self.api_secret, paper=True)
            self.data_client = StockHistoricalDataClient(self.api_key, self.api_secret)
            account = self.client.get_account()
            logger.info("[PaperTrading] Connected — equity=$%.2f cash=$%.2f",
                        float(account.equity), float(account.cash))
            self.connected = True
            return True
        except Exception as e:
            logger.error("[PaperTrading] Connection failed: %s", e)
            self.connected = False
            return False

    # ── Account / portfolio ────────────────────────────────────────────────────

    def get_account(self) -> Optional[Dict]:
        if not self.connected:
            return None
        try:
            acc = self.client.get_account()
            equity    = float(acc.equity)
            last_eq   = float(acc.last_equity) if hasattr(acc, "last_equity") and acc.last_equity else equity
            unreal_pl = equity - last_eq
            unreal_pct = (unreal_pl / last_eq * 100) if last_eq else 0.0
            return {
                "equity":          equity,
                "cash":            float(acc.cash),
                "buying_power":    float(acc.buying_power),
                "portfolio_value": float(acc.portfolio_value),
                "unrealized_pl":   unreal_pl,
                "unrealized_plpc": unreal_pct,
                "status": acc.status.value if hasattr(acc.status, "value") else str(acc.status),
            }
        except Exception as e:
            logger.error("[PaperTrading] get_account failed: %s", e)
            return None

    def get_positions(self) -> List[Dict]:
        if not self.connected:
            return []
        try:
            positions = self.client.get_all_positions()
            result = []
            for p in positions:
                d = {
                    "symbol":        p.symbol,
                    "qty":           float(p.qty),
                    "side":          p.side.value,
                    "market_value":  float(p.market_value),
                    "unrealized_pnl": float(p.unrealized_pl),
                    "unrealized_pnl_pct": float(p.unrealized_plpc) * 100,
                    "change_today":  float(p.change_today) * 100,
                }
                # For options positions include extra fields where available
                if hasattr(p, 'avg_entry_price'):
                    d["entry_price"] = float(p.avg_entry_price)
                if hasattr(p, 'current_price'):
                    d["current_price"] = float(p.current_price)
                result.append(d)
            return result
        except Exception as e:
            logger.error("[PaperTrading] get_positions failed: %s", e)
            return []

    def get_recent_orders(self, limit: int = 20) -> List[Dict]:
        if not self.connected:
            return []
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
            orders = self.client.get_orders(req)
            return [
                {
                    "id":         str(o.id),
                    "symbol":     o.symbol,
                    "side":       o.side.value,
                    "qty":        float(o.qty or 0),
                    "filled_qty": float(o.filled_qty or 0),
                    "status":     o.status.value,
                    "filled_at":  o.filled_at.isoformat() if o.filled_at else None,
                    "filled_avg_price": float(o.filled_avg_price or 0),
                }
                for o in orders
            ]
        except Exception as e:
            logger.error("[PaperTrading] get_recent_orders failed: %s", e)
            return []

    @staticmethod
    def _occ_option_type(symbol: str) -> str:
        """Extract call/put from a standard OCC option symbol, e.g.
        'TSEM260904C00265000' -> 'call'. Falls back to 'unknown'."""
        import re
        m = re.search(r"\d{6}([CP])\d{8}$", symbol)
        if not m:
            return "unknown"
        return "call" if m.group(1) == "C" else "put"

    @staticmethod
    def _is_occ_option_symbol(symbol: str) -> bool:
        """True for standard OCC option symbols (e.g. 'TSEM260904C00265000'),
        False for plain stock tickers. The same Alpaca account holds both
        stock_trading_service and paper_trading_service orders, so this
        distinguishes them before applying the options contract multiplier."""
        import re
        return bool(re.match(r"^[A-Z]+\d{6}[CP]\d{8}$", symbol))

    def get_realized_stats(self, limit: int = 500) -> Dict:
        """Reconstruct closed round-trip trades from Alpaca's own filled-order
        history, matching buys to sells FIFO per contract symbol.

        self.trade_history only lives in process memory and resets on every
        restart (Railway's free tier restarts/redeploys often), so it can't be
        trusted as the source of truth for realized stats. Alpaca's order
        history persists in their cloud regardless of our process lifecycle.
        """
        orders = self.get_recent_orders(limit=limit)
        filled = [o for o in orders if o["status"] == "filled" and o["filled_at"]]
        filled.sort(key=lambda o: o["filled_at"])

        open_lots: Dict[str, List[Dict]] = {}
        closed_trades: List[Dict] = []

        for o in filled:
            symbol, qty, price = o["symbol"], o["filled_qty"], o["filled_avg_price"]
            if o["side"] == "buy":
                open_lots.setdefault(symbol, []).append({"qty": qty, "price": price})
                continue

            remaining = qty
            lots = open_lots.get(symbol, [])
            is_option = self._is_occ_option_symbol(symbol)
            multiplier = self.OPTION_MULTIPLIER if is_option else 1.0
            while remaining > 0 and lots:
                lot = lots[0]
                matched = min(remaining, lot["qty"])
                pnl = (price - lot["price"]) * matched * multiplier
                closed_trades.append({
                    "symbol": symbol, "qty": matched,
                    "entry_price": lot["price"], "exit_price": price,
                    "pnl": round(pnl, 2),
                    "type": self._occ_option_type(symbol) if is_option else "stock",
                })
                lot["qty"] -= matched
                remaining -= matched
                if lot["qty"] <= 0:
                    lots.pop(0)

        winning = [t for t in closed_trades if t["pnl"] > 0]
        return {
            "closed_trades":  closed_trades,
            "realized_pnl":   round(sum(t["pnl"] for t in closed_trades), 2),
            "total_trades":   len(closed_trades),
            "winning_trades": len(winning),
            "losing_trades":  len(closed_trades) - len(winning),
            "win_rate":       round(len(winning) / len(closed_trades) * 100, 1) if closed_trades else 0.0,
        }

    def get_portfolio_snapshot(self) -> PortfolioSnapshot:
        acc = self.get_account() or {}
        equity        = acc.get("equity",          self.STARTING_CAPITAL)
        cash          = acc.get("cash",             self.STARTING_CAPITAL)
        portfolio_val = acc.get("portfolio_value",  self.STARTING_CAPITAL)
        unrealized    = acc.get("unrealized_pl",    0.0)

        stats     = self.get_realized_stats()
        total_ret = ((portfolio_val - self.STARTING_CAPITAL) / self.STARTING_CAPITAL) * 100

        return PortfolioSnapshot(
            timestamp        = datetime.utcnow().isoformat(),
            cash             = cash,
            portfolio_value  = portfolio_val,
            equity           = equity,
            unrealized_pnl   = unrealized,
            realized_pnl     = stats["realized_pnl"],
            total_return_pct = round(total_ret, 2),
            open_positions   = len(self.get_positions()),
            total_trades     = stats["total_trades"],
            winning_trades   = stats["winning_trades"],
            losing_trades    = stats["losing_trades"],
            win_rate         = stats["win_rate"],
        )

    def get_trade_history(self) -> List[Dict]:
        return [asdict(t) for t in self.trade_history]

    # ── Signal execution ───────────────────────────────────────────────────────

    def execute_signals(self, recommendations: List[Dict]) -> List[Dict]:
        if not self.connected:
            logger.warning("[PaperTrading] Not connected — skipping execution")
            return []

        # Daily max-loss circuit breaker — reset each calendar day
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self._daily_loss_date != today:
            self._daily_loss_date = today
            self._daily_loss_tripped = False

        if not self._daily_loss_tripped:
            try:
                acc = self.client.get_account()
                unrealized = float(getattr(acc, 'unrealized_pl', 0) or 0)
                closed_today = [
                    t for t in self.trade_history
                    if t.status == "closed" and t.pnl is not None
                    and (t.exit_time or "").startswith(today)
                ]
                realized_today = sum(t.pnl for t in closed_today)
                total_loss_today = realized_today + min(0.0, unrealized)
                if total_loss_today <= -self.DAILY_MAX_LOSS:
                    self._daily_loss_tripped = True
                    logger.warning(
                        "[PaperTrading] Daily max loss tripped ($%.0f) — no new entries today",
                        total_loss_today
                    )
            except Exception:
                pass

        if self._daily_loss_tripped:
            return []

        eligible = [r for r in recommendations if r.get("score", 0) >= self.MIN_SIGNAL_SCORE]
        if not eligible:
            logger.info("[PaperTrading] No signals above threshold %.2f", self.MIN_SIGNAL_SCORE)
            return []

        open_count = len(self.get_positions())
        slots = self.MAX_OPEN_POSITIONS - open_count
        if slots <= 0:
            logger.info("[PaperTrading] Max positions reached (%d)", self.MAX_OPEN_POSITIONS)
            return []

        calls = sorted([r for r in eligible if r.get("action") == "CALL"], key=lambda x: -x["score"])
        puts  = sorted([r for r in eligible if r.get("action") == "PUT"],  key=lambda x: -x["score"])

        candidates: List[Dict] = []
        while (calls or puts) and len(candidates) < slots:
            if calls: candidates.append(calls.pop(0))
            if puts and len(candidates) < slots:
                candidates.append(puts.pop(0))

        results = []
        for rec in candidates:
            ticker = rec.get("ticker", "")
            action = rec.get("action", "CALL")
            price  = float(rec.get("current_price", 0))
            score  = float(rec.get("score", 0))

            if price <= 0 or self._is_in_cooldown(ticker):
                continue

            # Skip if underlying already moved >2.5% intraday (chasing)
            intraday_move = self._get_intraday_move(ticker)
            if abs(intraday_move) > 0.025:
                logger.info(
                    "[PaperTrading] Skipping %s — already moved %.1f%% today",
                    ticker, intraday_move * 100
                )
                continue

            # Real-time staleness check: yfinance data is 15-20 min delayed.
            # Fetch current Alpaca quote and skip if price drifted >3% from rec.
            rt_price = self._get_realtime_price(ticker)
            if rt_price and rt_price > 0 and price > 0:
                drift = abs(rt_price - price) / price
                if drift > 0.03:
                    logger.info(
                        "[PaperTrading] Skipping %s — rec price $%.2f stale, now $%.2f (%.1f%% drift)",
                        ticker, price, rt_price, drift * 100
                    )
                    continue
                price = rt_price  # use fresh price for order sizing

            result = self._place_option_order(ticker, action, price, score)
            if result:
                results.append(result)
                self._last_traded[ticker] = datetime.utcnow()

        self._close_expired_positions()
        logger.info("[PaperTrading] Executed %d option trades this cycle", len(results))
        return results

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _find_option_contract(self, ticker: str, action: str, price: float) -> Optional[object]:
        """Find the most liquid ATM option contract expiring in MIN_EXPIRY_DAYS–MAX_EXPIRY_DAYS."""
        try:
            from alpaca.trading.requests import GetOptionContractsRequest
            from alpaca.trading.enums import ContractType

            c_type = ContractType.CALL if action == "CALL" else ContractType.PUT
            today  = date.today()

            # Two search passes: tight ±3% then wider ±8%
            for strike_pct in (0.03, 0.08):
                req = GetOptionContractsRequest(
                    underlying_symbols=[ticker],
                    expiration_date_gte=today + timedelta(days=self.MIN_EXPIRY_DAYS),
                    expiration_date_lte=today + timedelta(days=self.MAX_EXPIRY_DAYS),
                    type=c_type,
                    strike_price_gte=str(round(price * (1 - strike_pct), 2)),
                    strike_price_lte=str(round(price * (1 + strike_pct), 2)),
                )
                resp = self.client.get_option_contracts(req)
                contracts = resp.option_contracts if hasattr(resp, 'option_contracts') else list(resp)
                if not contracts:
                    continue

                # Only trade genuinely liquid contracts — thin OI means wide
                # spreads and bad fills even if the trade itself works out.
                liquid = [c for c in contracts if c.open_interest and int(c.open_interest) >= self.MIN_OPEN_INTEREST]
                if not liquid:
                    continue
                pool = liquid

                # Sort: nearest expiry, then closest strike to ATM
                return min(pool, key=lambda c: (
                    c.expiration_date,
                    abs(float(c.strike_price) - price)
                ))
            return None
        except Exception as e:
            logger.error("[PaperTrading] _find_option_contract %s %s: %s", action, ticker, e)
            return None

    def _wait_for_fill(self, order_id, timeout_secs: float = 8.0) -> bool:
        """Poll briefly for a buy order to fill before placing protective
        orders against it — Alpaca will reject a sell-to-close on shares/
        contracts not yet owned. Liquid, already OI-filtered contracts at
        a mid-price limit fill almost immediately in practice."""
        import time as _time
        from alpaca.trading.enums import OrderStatus
        deadline = _time.time() + timeout_secs
        while _time.time() < deadline:
            try:
                current = self.client.get_order_by_id(order_id)
                if current.status == OrderStatus.FILLED:
                    return True
                if current.status in (OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.EXPIRED):
                    return False
            except Exception:
                pass
            _time.sleep(0.5)
        return False

    def _place_protective_orders(self, option_symbol: str, entry_price: float) -> None:
        """Place real standing stop-loss and take-profit sell orders on the
        option contract itself, right after the buy fills — see
        OPTION_STOP_PCT/OPTION_TARGET_PCT for why this exists instead of
        relying solely on the scan-based _close_expired_positions check."""
        try:
            from alpaca.trading.requests import StopOrderRequest, LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            stop_price   = round(entry_price * (1 - self.OPTION_STOP_PCT), 2)
            target_price = round(entry_price * (1 + self.OPTION_TARGET_PCT), 2)

            self.client.submit_order(StopOrderRequest(
                symbol=option_symbol, qty=1, side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC, stop_price=max(stop_price, 0.01),
            ))
            self.client.submit_order(LimitOrderRequest(
                symbol=option_symbol, qty=1, side=OrderSide.SELL,
                time_in_force=TimeInForce.GTC, limit_price=target_price,
            ))
            logger.info(
                "[PaperTrading] Protective orders for %s: stop=$%.2f target=$%.2f (entry $%.2f)",
                option_symbol, stop_price, target_price, entry_price,
            )
        except Exception as e:
            # Not fatal — _close_expired_positions is still a fallback net
            logger.warning("[PaperTrading] Could not place protective orders for %s: %s", option_symbol, e)

    def _place_option_order(
        self, ticker: str, action: str, price: float, score: float
    ) -> Optional[Dict]:
        """Buy 1 options contract (CALL or PUT) closest to ATM using limit order at mid-price."""
        try:
            contract = self._find_option_contract(ticker, action, price)
            if not contract:
                logger.warning("[PaperTrading] No %s contract found for %s", action, ticker)
                return None

            from alpaca.trading.requests import LimitOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.requests import OptionLatestQuoteRequest

            # Require a real market bid — skip options with no liquidity (e.g. foreign ADRs)
            limit_price = None
            try:
                data_client = OptionHistoricalDataClient(self.api_key, self.api_secret)
                quotes = data_client.get_option_latest_quote(
                    OptionLatestQuoteRequest(symbol_or_symbols=contract.symbol)
                )
                q = quotes.get(contract.symbol)
                if q and float(q.bid_price) > 0 and float(q.ask_price) > 0:
                    mid = round((float(q.bid_price) + float(q.ask_price)) / 2, 2)
                    limit_price = max(mid, 0.01)
            except Exception as qe:
                logger.warning("[PaperTrading] Quote fetch failed for %s: %s", contract.symbol, qe)

            if not limit_price:
                logger.warning("[PaperTrading] Skipping %s — no real bid (illiquid option)", contract.symbol)
                return None

            order_req = LimitOrderRequest(
                symbol=contract.symbol,
                qty=1,
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
            logger.info("[PaperTrading] Limit order at $%.2f (mid) for %s", limit_price, contract.symbol)
            order = self.client.submit_order(order_req)

            if self._wait_for_fill(order.id):
                self._place_protective_orders(contract.symbol, limit_price)
            else:
                logger.warning(
                    "[PaperTrading] %s buy not confirmed filled — skipping protective orders, "
                    "_close_expired_positions will still catch it on the next scan",
                    contract.symbol,
                )

            direction   = "LONG" if action == "CALL" else "SHORT"
            stop_loss   = price * (1 - self.STOP_LOSS_PCT)   if action == "CALL" else price * (1 + self.STOP_LOSS_PCT)
            take_profit = price * (1 + self.TAKE_PROFIT_PCT) if action == "CALL" else price * (1 - self.TAKE_PROFIT_PCT)
            strike      = float(contract.strike_price)

            from zoneinfo import ZoneInfo
            now_et = datetime.now(ZoneInfo("America/New_York"))
            trade = TradeRecord(
                ticker               = ticker,
                direction            = direction,
                qty                  = 1.0,
                entry_price          = price,
                entry_time           = datetime.utcnow().isoformat(),
                stop_loss            = round(stop_loss, 4),
                take_profit          = round(take_profit, 4),
                signal_score         = score,
                signal_source        = action,
                option_symbol        = contract.symbol,
                option_strike        = strike,
                option_expiry        = str(contract.expiration_date),
                alpaca_order_id      = str(order.id),
                status               = "open",
                entry_intraday_move  = round(self._get_intraday_move(ticker) * 100, 2),
                entry_hour_et        = now_et.hour,
            )
            self.trade_history.append(trade)

            logger.info(
                "[PaperTrading] BUY %s %s | contract=%s strike=$%.2f expiry=%s score=%.3f",
                action, ticker, contract.symbol, strike, contract.expiration_date, score,
            )
            return {
                "ticker":           ticker,
                "action":           action,
                "option_symbol":    contract.symbol,
                "option_strike":    strike,
                "option_expiry":    str(contract.expiration_date),
                "underlying_price": price,
                "score":            score,
                "order_id":         str(order.id),
                "status":           "submitted",
            }

        except Exception as e:
            logger.error("[PaperTrading] Option order failed for %s %s: %s", action, ticker, e)
            self.trade_history.append(TradeRecord(
                ticker=ticker,
                direction="LONG" if action == "CALL" else "SHORT",
                qty=0, entry_price=price, entry_time=datetime.utcnow().isoformat(),
                stop_loss=0, take_profit=0, signal_score=score, signal_source=action,
                status="error", notes=str(e),
            ))
            return None

    def _cancel_open_orders_for(self, symbol: str) -> None:
        """Cancel any still-open orders on this symbol — used to clear the
        dangling stop or target order once the other one of the pair has
        already filled (they're separate orders, not a linked OCO pair)."""
        try:
            from alpaca.trading.requests import GetOrdersRequest
            from alpaca.trading.enums import QueryOrderStatus
            open_orders = self.client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol]))
            for o in open_orders:
                self.client.cancel_order_by_id(o.id)
        except Exception as e:
            logger.debug("[PaperTrading] Cancel dangling orders for %s failed: %s", symbol, e)

    def _close_expired_positions(self) -> None:
        """Sell any options positions that have hit stop/take-profit or exceeded HOLD_HOURS.

        First syncs against Alpaca directly — a standing stop or target order
        (placed at entry, see _place_protective_orders) may have already
        closed the position on its own, any time the market was open,
        independent of whether a scan happened to be running to notice."""
        if not self.connected:
            return
        try:
            open_trades = [t for t in self.trade_history if t.status == "open" and t.option_symbol]
            now = datetime.now(timezone.utc)

            for trade in open_trades:
                if not self._has_open_alpaca_position(trade.option_symbol):
                    # A standing protective order already closed this — sync
                    # our bookkeeping and clear whichever order didn't fire.
                    self._cancel_open_orders_for(trade.option_symbol)
                    trade.status = "closed"
                    trade.exit_time = datetime.utcnow().isoformat()
                    trade.notes = "closed_by_standing_order"
                    logger.info(
                        "[PaperTrading] %s already closed by its standing stop/target order",
                        trade.option_symbol,
                    )
                    continue

                entry_dt = datetime.fromisoformat(trade.entry_time.replace("Z", "+00:00"))
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=timezone.utc)
                age_hours = (now - entry_dt).total_seconds() / 3600

                if age_hours >= self.HOLD_HOURS:
                    # Time-based exit only — price-based stop/target now live
                    # as real standing orders, not checked here anymore.
                    current = self._get_realtime_price(trade.ticker) or trade.entry_price
                    self._cancel_open_orders_for(trade.option_symbol)
                    self._close_option_position(trade, current, "expired")

        except Exception as e:
            logger.error("[PaperTrading] _close_expired_positions failed: %s", e)

    def _has_open_alpaca_position(self, symbol: str) -> bool:
        """True if Alpaca still shows an open (nonzero qty) position for this symbol."""
        try:
            pos = self.client.get_open_position(symbol)
            return float(pos.qty) != 0
        except Exception:
            # get_open_position raises when there's no position for the symbol
            return False

    def _close_option_position(self, trade: TradeRecord, current_price: float, reason: str) -> None:
        """Sell an options contract and record the trade outcome."""
        try:
            # Check option has a real bid before closing — prevents $0 fill on illiquid options
            try:
                from alpaca.data.requests import OptionLatestQuoteRequest
                quotes = self.data_client.get_option_latest_quote(
                    OptionLatestQuoteRequest(symbol_or_symbols=trade.option_symbol)
                )
                q = quotes.get(trade.option_symbol)
                if q and float(q.bid_price or 0) <= 0:
                    logger.warning(
                        "[PaperTrading] Skipping close of %s — bid is $0 (illiquid). Will retry next scan.",
                        trade.option_symbol
                    )
                    return
            except Exception:
                pass  # proceed with close if quote check fails
            self.client.close_position(trade.option_symbol)

            entry = trade.entry_price
            if trade.direction == "LONG":
                pnl_pct = ((current_price - entry) / entry) * 100
            else:
                pnl_pct = ((entry - current_price) / entry) * 100

            # Approximate dollar P&L: ATM option has ~0.5 delta, so option moves ~50% of underlying
            pnl = pnl_pct / 100 * 500 * 0.5

            trade.exit_price = current_price
            trade.exit_time  = datetime.utcnow().isoformat()
            trade.pnl        = round(pnl, 4)
            trade.pnl_pct    = round(pnl_pct, 2)
            trade.status     = "closed"
            trade.notes      = reason

            logger.info(
                "[PaperTrading] Closed %s %s %s @ underlying=$%.2f (%.2f%%) reason=%s",
                trade.direction, trade.ticker, trade.option_symbol,
                current_price, pnl_pct, reason,
            )
        except Exception as e:
            logger.error("[PaperTrading] Close failed for %s: %s", trade.option_symbol, e)

    def close_rule_violating_positions(self) -> List[Dict]:
        """Close only positions that violated current entry rules:
        - entered when underlying already moved >2.5% intraday (chasing)
        - entered outside the 10:00–15:30 ET window
        - unknown entries (entry_hour_et == -1, i.e. placed before tracking was added)
        Returns list of closed position details.
        """
        if not self.connected:
            return []

        closed = []
        open_trades = [t for t in self.trade_history if t.status == "open" and t.option_symbol]

        for trade in open_trades:
            reason = None
            if trade.entry_hour_et == -1:
                reason = "pre-fix entry (tracking unavailable)"
            elif abs(trade.entry_intraday_move) > 2.5:
                reason = f"chased entry ({trade.entry_intraday_move:+.1f}% move at entry)"
            elif not (10 <= trade.entry_hour_et < 15 or (trade.entry_hour_et == 15 and 0 <= 30)):
                reason = f"outside trading window (entered {trade.entry_hour_et}:xx ET)"

            if reason:
                try:
                    self.client.close_position(trade.option_symbol)
                    trade.status = "closed"
                    trade.notes  = f"rule-violation close: {reason}"
                    closed.append({"ticker": trade.ticker, "symbol": trade.option_symbol, "reason": reason})
                    logger.info("[PaperTrading] Closed rule-violating %s — %s", trade.option_symbol, reason)
                except Exception as e:
                    logger.error("[PaperTrading] Could not close %s: %s", trade.option_symbol, e)

        # Also close any Alpaca positions not tracked in trade_history (legacy positions)
        try:
            tracked_symbols = {t.option_symbol for t in self.trade_history}
            all_positions = self.client.get_all_positions()
            for p in all_positions:
                if p.symbol not in tracked_symbols:
                    try:
                        self.client.close_position(p.symbol)
                        closed.append({"ticker": p.symbol[:4], "symbol": p.symbol, "reason": "legacy untracked position"})
                        logger.info("[PaperTrading] Closed legacy position %s", p.symbol)
                    except Exception as e:
                        logger.error("[PaperTrading] Could not close legacy %s: %s", p.symbol, e)
        except Exception as e:
            logger.error("[PaperTrading] Legacy position scan failed: %s", e)

        return closed

    def close_all_open_positions(self) -> int:
        """Close every open Alpaca position. Returns number closed."""
        if not self.connected:
            return 0
        closed = 0
        try:
            positions = self.client.get_all_positions()
            for p in positions:
                try:
                    self.client.close_position(p.symbol)
                    closed += 1
                    logger.info("[PaperTrading] Force-closed %s", p.symbol)
                except Exception as e:
                    logger.error("[PaperTrading] Could not close %s: %s", p.symbol, e)
        except Exception as e:
            logger.error("[PaperTrading] close_all_open_positions failed: %s", e)
        return closed

    def _is_in_cooldown(self, ticker: str) -> bool:
        last = self._last_traded.get(ticker)
        if last is None:
            return False
        return (datetime.utcnow() - last).total_seconds() < self.COOLDOWN_HOURS * 3600

    def _get_intraday_move(self, ticker: str) -> float:
        """Return today's intraday move as a fraction (e.g. 0.05 = +5%). Returns 0.0 on failure."""
        try:
            import yfinance as yf
            fi = yf.Ticker(ticker).fast_info
            open_price = getattr(fi, 'open', None) or getattr(fi, 'regular_market_open', None)
            last_price = getattr(fi, 'last_price', None)
            if open_price and last_price and open_price > 0:
                return (last_price - open_price) / open_price
        except Exception:
            pass
        return 0.0

    def _get_realtime_price(self, ticker: str) -> Optional[float]:
        """Get real-time price from Alpaca market data (not delayed like yfinance)."""
        try:
            from alpaca.data.requests import StockLatestQuoteRequest
            req = StockLatestQuoteRequest(symbol_or_symbols=ticker)
            quotes = self.data_client.get_stock_latest_quote(req)
            q = quotes.get(ticker)
            if q:
                mid = (float(q.ask_price) + float(q.bid_price)) / 2
                return mid if mid > 0 else float(q.ask_price or q.bid_price or 0)
        except Exception as e:
            logger.debug("[PaperTrading] Real-time price fetch failed for %s: %s", ticker, e)
        return None
