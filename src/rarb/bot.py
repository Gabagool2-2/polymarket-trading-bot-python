"""Main bot orchestration."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from rarb.analyzer.arbitrage import ArbitrageAnalyzer
from rarb.api.models import ArbitrageOpportunity
from rarb.config import get_settings
from rarb.executor.executor import ExecutionResult, ExecutionStatus, OrderExecutor
from rarb.notifications.slack import get_notifier
from rarb.scanner.market_scanner import MarketScanner, MarketSnapshot
from rarb.utils.logging import get_logger, setup_logging

log = get_logger(__name__)


@dataclass
class BotStats:
    """Runtime statistics for the bot."""

    started_at: datetime = field(default_factory=datetime.utcnow)
    scan_cycles: int = 0
    markets_scanned: int = 0
    opportunities_found: int = 0
    trades_executed: int = 0
    trades_successful: int = 0
    total_profit: Decimal = Decimal("0")


class ArbitrageBot:
    """
    Main arbitrage bot that coordinates scanning, analysis, and execution.

    Flow:
    1. Scanner polls markets for orderbook data
    2. Analyzer checks each market for arbitrage opportunities
    3. Executor places trades for profitable opportunities
    """

    def __init__(
        self,
        scanner: Optional[MarketScanner] = None,
        analyzer: Optional[ArbitrageAnalyzer] = None,
        executor: Optional[OrderExecutor] = None,
    ) -> None:
        settings = get_settings()

        # Initialize components
        self.scanner = scanner or MarketScanner(
            min_liquidity=settings.min_liquidity_usd,
        )
        self.analyzer = analyzer or ArbitrageAnalyzer()
        self.executor = executor or OrderExecutor()

        self.stats = BotStats()
        self._running = False
        self._pending_opportunities: list[ArbitrageOpportunity] = []

    async def process_snapshot(self, snapshot: MarketSnapshot) -> None:
        """
        Process a single market snapshot.

        Called by the scanner for each market update.
        """
        # Analyze for arbitrage
        opportunity = self.analyzer.analyze(snapshot)

        if opportunity is not None:
            self.stats.opportunities_found += 1
            self._pending_opportunities.append(opportunity)

    async def execute_opportunities(self) -> list[ExecutionResult]:
        """Execute all pending arbitrage opportunities."""
        results: list[ExecutionResult] = []

        if not self._pending_opportunities:
            return results

        # Sort by profit (best first)
        self._pending_opportunities.sort(key=lambda x: x.profit_pct, reverse=True)

        log.info(
            "Executing opportunities",
            count=len(self._pending_opportunities),
        )

        for opportunity in self._pending_opportunities:
            try:
                result = await self.executor.execute(opportunity)
                results.append(result)

                self.stats.trades_executed += 1
                if result.status == ExecutionStatus.FILLED:
                    self.stats.trades_successful += 1
                    self.stats.total_profit += result.expected_profit

            except Exception as e:
                log.error(
                    "Execution error",
                    market=opportunity.market.question[:30],
                    error=str(e),
                )

        # Clear pending
        self._pending_opportunities = []

        return results

    async def run_cycle(self) -> None:
        """Run a single scan/analyze/execute cycle."""
        self.stats.scan_cycles += 1

        # Scan all markets
        snapshots = await self.scanner.run_once()
        self.stats.markets_scanned += len(snapshots)

        # Analyze each snapshot
        for snapshot in snapshots:
            await self.process_snapshot(snapshot)

        # Execute any found opportunities
        if self._pending_opportunities:
            await self.execute_opportunities()

    async def run(self) -> None:
        """Run the bot continuously."""
        settings = get_settings()
        self._running = True

        mode = "DRY RUN" if settings.dry_run else "LIVE"
        log.info(
            f"Starting arbitrage bot [{mode}]",
            poll_interval=settings.poll_interval_seconds,
            min_profit=f"{settings.min_profit_threshold * 100:.1f}%",
            max_position=f"${settings.max_position_size}",
        )

        if not settings.dry_run and not self.executor.signer.is_configured:
            log.warning(
                "Trading credentials not configured. "
                "Set PRIVATE_KEY and WALLET_ADDRESS in .env for live trading."
            )

        try:
            while self._running:
                try:
                    await self.run_cycle()

                    # Log periodic stats
                    if self.stats.scan_cycles % 10 == 0:
                        self._log_stats()

                except Exception as e:
                    log.error("Cycle error", error=str(e))

                await asyncio.sleep(settings.poll_interval_seconds)

        except asyncio.CancelledError:
            log.info("Bot cancelled")
        finally:
            await self.shutdown()

    def stop(self) -> None:
        """Stop the bot."""
        log.info("Stopping bot...")
        self._running = False

    async def shutdown(self) -> None:
        """Clean shutdown of all components."""
        log.info("Shutting down...")
        self.stop()
        await self.scanner.close()
        await self.executor.close()
        self._log_stats()

    def _log_stats(self) -> None:
        """Log current statistics."""
        runtime = datetime.utcnow() - self.stats.started_at
        hours = runtime.total_seconds() / 3600

        log.info(
            "Bot statistics",
            runtime=f"{hours:.1f}h",
            cycles=self.stats.scan_cycles,
            markets=self.stats.markets_scanned,
            opportunities=self.stats.opportunities_found,
            trades=self.stats.trades_executed,
            successful=self.stats.trades_successful,
            profit=f"${float(self.stats.total_profit):.2f}",
        )

    def get_stats(self) -> dict:
        """Get current statistics."""
        runtime = datetime.utcnow() - self.stats.started_at

        return {
            "runtime_seconds": runtime.total_seconds(),
            "scan_cycles": self.stats.scan_cycles,
            "markets_scanned": self.stats.markets_scanned,
            "opportunities_found": self.stats.opportunities_found,
            "trades_executed": self.stats.trades_executed,
            "trades_successful": self.stats.trades_successful,
            "total_profit": float(self.stats.total_profit),
            "analyzer_stats": self.analyzer.get_stats(),
            "executor_stats": self.executor.get_stats(),
        }

    async def __aenter__(self) -> "ArbitrageBot":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.shutdown()


async def run_bot() -> None:
    """Entry point for running the bot (legacy polling mode)."""
    settings = get_settings()
    setup_logging(settings.log_level)

    async with ArbitrageBot() as bot:
        await bot.run()


class RealtimeArbitrageBot:
    """
    Real-time arbitrage bot using WebSocket streaming.

    This is the fast version that reacts to price changes instantly
    instead of polling.
    """

    # How often to check for redeemable positions (in seconds)
    REDEMPTION_CHECK_INTERVAL = 300  # 5 minutes
    # How often to record stats history (in seconds)
    STATS_HISTORY_INTERVAL = 3600  # 1 hour
    # How often to record minute-level stats (in seconds)
    MINUTE_STATS_INTERVAL = 60  # 1 minute

    # How often to refresh the cached balance (in seconds)
    BALANCE_REFRESH_INTERVAL = 60  # 1 minute

    def __init__(self) -> None:
        from rarb.scanner.realtime_scanner import RealtimeScanner

        settings = get_settings()

        # Create executor first so we can use its client for pre-caching
        self.executor = OrderExecutor()

        self.scanner = RealtimeScanner(
            on_arbitrage=self._on_arbitrage,
            on_markets_loaded=self._on_markets_loaded,
            min_liquidity=settings.min_liquidity_usd,
        )

        self.stats = BotStats()
        self._running = False
        self._execution_lock = asyncio.Lock()
        self._redemption_task: Optional[asyncio.Task] = None
        self._stats_history_task: Optional[asyncio.Task] = None
        self._minute_stats_task: Optional[asyncio.Task] = None
        self._balance_refresh_task: Optional[asyncio.Task] = None
        self._last_price_updates: int = 0  # Track delta for hourly stats
        self._last_minute_price_updates: int = 0  # Track delta for minute stats

        # Cached USDC balance (updated periodically and after trades)
        self._cached_balance: Decimal = Decimal("0")
        self._balance_lock = asyncio.Lock()

        # Risk management (position sizing, circuit breakers, pre-trade filters)
        from rarb.risk import RiskManager
        self._risk_manager = RiskManager()

    async def _on_markets_loaded(self, markets: list) -> None:
        """
        Pre-cache neg_risk status for all tokens when markets are loaded.

        This eliminates the ~500ms neg_risk API call during order execution.
        """
        from rarb.api.models import Market

        # Extract all token IDs
        token_ids = []
        for market in markets:
            if isinstance(market, Market):
                token_ids.append(market.yes_token.token_id)
                token_ids.append(market.no_token.token_id)

        if not token_ids:
            return

        # Get or create async client
        async_client = await self.executor._ensure_async_client()
        if async_client:
            log.info("Pre-caching neg_risk status for all tokens", count=len(token_ids))
            # Run pre-fetch in background to not block WebSocket setup
            asyncio.create_task(async_client.prefetch_neg_risk(token_ids))
        else:
            log.warning("Async CLOB client not available - skipping neg_risk pre-cache")

    async def _save_near_miss_alert(self, alert, min_required: Decimal) -> None:
        """Save an illiquid arbitrage alert to the database."""
        from datetime import datetime, timezone
        from rarb.data.repositories import NearMissAlertRepository

        try:
            await NearMissAlertRepository.insert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                market=alert.market.question[:60],
                yes_ask=float(alert.yes_ask),
                no_ask=float(alert.no_ask),
                combined=float(alert.combined_cost),
                profit_pct=float(alert.profit_pct),
                yes_liquidity=float(alert.yes_size_available),
                no_liquidity=float(alert.no_size_available),
                min_required=float(min_required),
                reason="insufficient_liquidity",
            )
        except Exception as e:
            log.debug("Failed to save near-miss alert", error=str(e))

    async def _save_insufficient_balance_alert(self, alert, required: Decimal, available: Decimal) -> None:
        """Save an alert for when balance is insufficient."""
        from datetime import datetime, timezone
        from rarb.data.repositories import NearMissAlertRepository

        try:
            await NearMissAlertRepository.insert(
                timestamp=datetime.now(timezone.utc).isoformat(),
                market=alert.market.question[:60],
                yes_ask=float(alert.yes_ask),
                no_ask=float(alert.no_ask),
                combined=float(alert.combined_cost),
                profit_pct=float(alert.profit_pct),
                yes_liquidity=float(alert.yes_size_available),
                no_liquidity=float(alert.no_size_available),
                min_required=float(required),
                reason=f"insufficient_balance (need ${float(required):.2f}, have ${float(available):.2f})",
            )
        except Exception as e:
            log.debug("Failed to save insufficient balance alert", error=str(e))

    async def _on_arbitrage(self, alert) -> None:
        """Handle arbitrage alert from scanner."""
        from datetime import timezone as tz
        from rarb.api.models import ArbitrageOpportunity
        from rarb.scanner.realtime_scanner import ArbitrageAlert

        alert: ArbitrageAlert = alert
        settings = get_settings()

        self.stats.opportunities_found += 1

        # --- Risk: pause and circuit breakers ---
        if self._risk_manager.is_paused():
            log.debug("Skipping arbitrage - risk pause active", until=str(self._risk_manager.pause_until_utc()))
            return

        async with self._balance_lock:
            current_balance = self._cached_balance

        allowed, reason = self._risk_manager.check_circuit_breakers(current_balance)
        if not allowed:
            log.warning("Skipping arbitrage - circuit breaker", reason=reason)
            return

        # --- Pre-trade filters (time to resolution, optional volume/zscore/RSI) ---
        seconds_until_resolution: Optional[float] = None
        if alert.market.end_date:
            now = datetime.now(tz.utc)
            end = alert.market.end_date
            if end.tzinfo is None:
                end = end.replace(tzinfo=tz.utc)
            seconds_until_resolution = (end - now).total_seconds()
        filter_result = self._risk_manager.pre_trade_filters(seconds_until_resolution=seconds_until_resolution)
        if not filter_result.allowed:
            log.info("Skipping arbitrage - pre-trade filter", reason=filter_result.reason)
            return

        # Convert alert to opportunity
        # Limit trade size to available liquidity on BOTH sides
        # Apply 50% safety margin to account for:
        # - Liquidity changes during execution (can take 1-20+ seconds)
        # - Other traders taking the same opportunity
        # - Order book depth inaccuracies
        LIQUIDITY_SAFETY_MARGIN = Decimal("0.50")  # Only use 50% of available liquidity
        max_position = Decimal(str(settings.max_position_size))
        raw_available = min(alert.yes_size_available, alert.no_size_available)
        available_size = (raw_available * LIQUIDITY_SAFETY_MARGIN).quantize(Decimal("1"), rounding="ROUND_DOWN")

        # Calculate minimum shares needed so BOTH orders meet Polymarket's $1 minimum
        # Formula: shares = $1.10 / price (using $1.10 for safety margin)
        min_order_value = Decimal("1.10")  # Polymarket minimum is $1, add buffer
        min_shares_for_yes = (min_order_value / alert.yes_ask).quantize(Decimal("1"), rounding="ROUND_UP")
        min_shares_for_no = (min_order_value / alert.no_ask).quantize(Decimal("1"), rounding="ROUND_UP")
        min_required_size = max(min_shares_for_yes, min_shares_for_no, Decimal("5"))  # At least 5 shares

        # Skip if insufficient liquidity on either side
        if available_size < min_required_size:
            log.warning(
                "Skipping arbitrage - insufficient liquidity for $1 min orders",
                market=alert.market.question[:40],
                yes_available=float(alert.yes_size_available),
                no_available=float(alert.no_size_available),
                min_required=float(min_required_size),
                yes_price=float(alert.yes_ask),
                no_price=float(alert.no_ask),
            )
            # Save near-miss alert for visibility (non-blocking)
            asyncio.create_task(self._save_near_miss_alert(alert, min_required_size))
            return

        # Risk-based position sizing: cap by risk_per_trade and position_cap_pct
        risk_shares, risk_usd = self._risk_manager.position_size(
            current_balance, alert.yes_ask
        )
        max_position_shares = (max_position / alert.combined_cost).quantize(
            Decimal("1"), rounding="ROUND_DOWN"
        )
        trade_size = min(
            available_size,
            risk_shares,
            max_position_shares,
        ).quantize(Decimal("1"), rounding="ROUND_DOWN")
        if trade_size < min_required_size:
            log.warning(
                "Skipping arbitrage - risk-based size below minimum",
                market=alert.market.question[:40],
                risk_shares=float(risk_shares),
                min_required=float(min_required_size),
            )
            return

        # Use execution lock for the ENTIRE balance check + deduct + execute flow
        # This prevents race conditions where multiple opportunities pass balance check simultaneously
        async with self._execution_lock:
            # Check if we have sufficient balance for this trade
            # Cost = trade_size * combined_cost (buying both YES and NO)
            required_cost = trade_size * alert.combined_cost

            async with self._balance_lock:
                current_balance = self._cached_balance

            if current_balance < required_cost:
                # Try to reduce trade size to fit available balance
                if current_balance >= min_required_size * alert.combined_cost:
                    # We have enough for at least minimum trade
                    max_affordable_size = current_balance / alert.combined_cost
                    trade_size = min(trade_size, max_affordable_size.quantize(Decimal("1"), rounding="ROUND_DOWN"))
                    required_cost = trade_size * alert.combined_cost
                    log.info(
                        "Reduced trade size to fit balance",
                        market=alert.market.question[:40],
                        original_size=float(available_size),
                        adjusted_size=float(trade_size),
                        balance=float(current_balance),
                    )
                else:
                    # Not enough balance for even minimum trade
                    log.warning(
                        "Skipping arbitrage - insufficient balance",
                        market=alert.market.question[:40],
                        required=float(required_cost),
                        available=float(current_balance),
                    )
                    # Save near-miss alert for visibility
                    asyncio.create_task(self._save_insufficient_balance_alert(alert, required_cost, current_balance))
                    return

            opportunity = ArbitrageOpportunity(
                market=alert.market,
                yes_ask=alert.yes_ask,
                no_ask=alert.no_ask,
                combined_cost=alert.combined_cost,
                profit_pct=alert.profit_pct,
                yes_size_available=alert.yes_size_available,
                no_size_available=alert.no_size_available,
                max_trade_size=trade_size,
            )

            log.info(
                "Executing with liquidity-adjusted size",
                market=alert.market.question[:40],
                trade_size=float(trade_size),
                yes_liquidity=float(alert.yes_size_available),
                no_liquidity=float(alert.no_size_available),
                balance=float(current_balance),
            )

            # Deduct expected cost from cached balance immediately to prevent over-trading
            async with self._balance_lock:
                self._cached_balance -= required_cost
            try:
                # Pass detection timestamp for latency tracking (convert to ms)
                detection_timestamp_ms = alert.timestamp * 1000
                result = await self.executor.execute(opportunity, detection_timestamp_ms=detection_timestamp_ms)

                self.stats.trades_executed += 1
                if result.status == ExecutionStatus.FILLED:
                    self.stats.trades_successful += 1
                    self.stats.total_profit += result.expected_profit
                    self._risk_manager.record_trade(True, result.expected_profit)
                    log.info(
                        "Trade executed successfully",
                        market=alert.market.question[:30],
                        profit=f"${float(result.expected_profit):.2f}",
                    )
                else:
                    self._risk_manager.record_trade(False, Decimal("0"))
                    # Trade failed/partial - refresh actual balance from chain
                    # Don't blindly restore as that causes cache inflation
                    new_balance = await self._refresh_balance()
                    log.warning(
                        "Refreshed balance after failed trade",
                        new_balance=float(new_balance),
                        status=result.status.value,
                    )

            except Exception as e:
                self._risk_manager.record_trade(False, Decimal("0"))
                # Exception - refresh actual balance from chain
                new_balance = await self._refresh_balance()
                log.error(
                    "Execution error - refreshed balance",
                    market=alert.market.question[:30],
                    error=str(e),
                    new_balance=float(new_balance),
                )

    async def _auto_redemption_loop(self) -> None:
        """Background task that periodically checks for and redeems resolved positions."""
        from rarb.executor.redemption import check_and_redeem

        settings = get_settings()

        # Wait a bit before first check to let the bot stabilize
        await asyncio.sleep(60)

        log.info("Auto-redemption task started", interval=f"{self.REDEMPTION_CHECK_INTERVAL}s")

        while self._running:
            try:
                result = await check_and_redeem()

                if result.get("skipped"):
                    log.debug("Redemption skipped", reason=result.get("reason"))
                elif result.get("redeemed", 0) > 0:
                    log.info(
                        "Auto-redemption completed",
                        redeemed=result["redeemed"],
                        total_value=f"${result.get('total_value', 0):.2f}",
                    )

                    # Send notification for successful redemptions
                    try:
                        notifier = get_notifier()
                        await notifier.send_message(
                            f"💰 Auto-redeemed {result['redeemed']} position(s) "
                            f"for ${result.get('total_value', 0):.2f}"
                        )
                    except Exception:
                        pass

                elif result.get("error"):
                    log.error("Auto-redemption error", error=result["error"])

            except Exception as e:
                log.error("Auto-redemption task error", error=str(e))

            # Wait for next check
            await asyncio.sleep(self.REDEMPTION_CHECK_INTERVAL)

    async def _stats_history_loop(self) -> None:
        """Background task that records hourly stats snapshots for charting."""
        from datetime import datetime, timezone
        from rarb.data.repositories import StatsHistoryRepository

        # Wait a bit before first record
        await asyncio.sleep(60)

        log.info("Stats history task started", interval=f"{self.STATS_HISTORY_INTERVAL}s")

        while self._running:
            try:
                # Get current scanner stats
                scanner_stats = self.scanner.get_stats()
                current_price_updates = scanner_stats.get("price_updates", 0)

                # Calculate delta since last record
                price_updates_delta = current_price_updates - self._last_price_updates
                self._last_price_updates = current_price_updates

                # Get current hour for grouping
                now = datetime.now(timezone.utc)
                hour = now.strftime("%Y-%m-%d %H:00")

                # Record stats (non-blocking)
                asyncio.create_task(StatsHistoryRepository.insert(
                    timestamp=now.isoformat(),
                    hour=hour,
                    markets=scanner_stats.get("markets", 0),
                    price_updates=price_updates_delta,
                    arbitrage_alerts=self.stats.opportunities_found,
                    executions_attempted=self.stats.trades_executed,
                    executions_filled=self.stats.trades_successful,
                    ws_connected=scanner_stats.get("ws_connected", False),
                ))

                log.debug(
                    "Stats history recorded",
                    hour=hour,
                    price_updates=price_updates_delta,
                    markets=scanner_stats.get("markets", 0),
                )

            except Exception as e:
                log.error("Stats history task error", error=str(e))

            # Wait for next record
            await asyncio.sleep(self.STATS_HISTORY_INTERVAL)

    async def _minute_stats_loop(self) -> None:
        """Background task that records minute-level price update stats."""
        from datetime import datetime, timezone
        from rarb.data.repositories import MinuteStatsRepository

        # Wait a bit before first record
        await asyncio.sleep(10)

        # Initialize baseline to current value to avoid huge first delta after restart
        scanner_stats = self.scanner.get_stats()
        self._last_minute_price_updates = scanner_stats.get("price_updates", 0)

        log.info("Minute stats task started", interval=f"{self.MINUTE_STATS_INTERVAL}s")

        while self._running:
            try:
                # Get current scanner stats
                scanner_stats = self.scanner.get_stats()
                current_price_updates = scanner_stats.get("price_updates", 0)

                # Calculate delta since last minute
                price_updates_delta = current_price_updates - self._last_minute_price_updates
                self._last_minute_price_updates = current_price_updates

                # Get current minute for grouping
                now = datetime.now(timezone.utc)
                minute = now.strftime("%Y-%m-%d %H:%M")

                # Record stats (non-blocking)
                asyncio.create_task(MinuteStatsRepository.insert(
                    timestamp=now.isoformat(),
                    minute=minute,
                    price_updates=price_updates_delta,
                    ws_connected=scanner_stats.get("ws_connected", False),
                ))

            except Exception as e:
                log.error("Minute stats task error", error=str(e))

            # Wait for next record
            await asyncio.sleep(self.MINUTE_STATS_INTERVAL)

    async def _refresh_balance(self) -> Decimal:
        """Fetch current USDC balance from chain and update cache."""
        from rarb.tracking.portfolio import PortfolioTracker, BalanceSnapshot

        try:
            tracker = PortfolioTracker()
            balances = await tracker.get_current_balances()
            balance = Decimal(str(balances.get("polymarket_usdc", 0)))

            async with self._balance_lock:
                self._cached_balance = balance

            # Record snapshot for daily balance chart
            # Fetch positions value for total portfolio tracking
            positions_value = 0.0
            try:
                async_client = await self.executor._ensure_async_client()
                if async_client:
                    positions = await async_client.get_positions()
                    for p in positions:
                        size = float(p.get("size", 0) or 0)
                        cur_price = float(p.get("curPrice", 0) or 0)
                        positions_value += size * cur_price
            except Exception as e:
                log.debug("Failed to fetch positions for snapshot", error=str(e))

            snapshot = BalanceSnapshot(
                timestamp=balances.get("timestamp", ""),
                polymarket_usdc=float(balance),
                total_usd=float(balance) + positions_value,
                positions_value=positions_value,
            )
            await tracker.record_snapshot_async(snapshot)

            log.debug("Balance refreshed", balance=f"${float(balance):.2f}")
            return balance
        except Exception as e:
            log.error("Failed to refresh balance", error=str(e))
            return self._cached_balance

    async def _balance_refresh_loop(self) -> None:
        """Background task that periodically refreshes the cached balance."""
        # Initial fetch
        balance = await self._refresh_balance()
        log.info(
            "Balance tracking initialized",
            balance=f"${float(balance):.2f}",
            interval=f"{self.BALANCE_REFRESH_INTERVAL}s",
        )

        while self._running:
            await asyncio.sleep(self.BALANCE_REFRESH_INTERVAL)
            try:
                await self._refresh_balance()
            except Exception as e:
                log.error("Balance refresh loop error", error=str(e))

    async def run(self) -> None:
        """Run the real-time bot."""
        settings = get_settings()
        self._running = True

        mode = "DRY RUN" if settings.dry_run else "LIVE"
        log.info(
            f"Starting REAL-TIME arbitrage bot [{mode}]",
            min_profit=f"{settings.min_profit_threshold * 100:.1f}%",
            max_position=f"${settings.max_position_size}",
        )

        if not settings.dry_run and not self.executor.signer.is_configured:
            log.warning(
                "Trading credentials not configured. "
                "Set PRIVATE_KEY and WALLET_ADDRESS in .env for live trading."
            )

        # Send startup notification
        try:
            notifier = get_notifier()
            await notifier.notify_startup(mode=mode)
        except Exception as e:
            log.debug("Startup notification failed", error=str(e))

        # Start background tasks
        if not settings.dry_run:
            self._redemption_task = asyncio.create_task(self._auto_redemption_loop())
            log.info("Auto-redemption task scheduled")

            # Start balance tracking for trade validation
            self._balance_refresh_task = asyncio.create_task(self._balance_refresh_loop())
            log.info("Balance refresh task scheduled")

        # Always start stats history task (for monitoring)
        self._stats_history_task = asyncio.create_task(self._stats_history_loop())
        log.info("Stats history task scheduled")

        # Start minute-level stats for real-time charting
        self._minute_stats_task = asyncio.create_task(self._minute_stats_loop())
        log.info("Minute stats task scheduled")

        try:
            await self.scanner.run()
        except asyncio.CancelledError:
            log.info("Bot cancelled")
        finally:
            await self.shutdown()

    def stop(self) -> None:
        """Stop the bot."""
        log.info("Stopping bot...")
        self._running = False
        self.scanner.stop()

    async def shutdown(self) -> None:
        """Clean shutdown."""
        log.info("Shutting down...")
        self.stop()

        # Cancel background tasks
        if self._redemption_task and not self._redemption_task.done():
            self._redemption_task.cancel()
            try:
                await self._redemption_task
            except asyncio.CancelledError:
                pass
            log.info("Auto-redemption task cancelled")

        if self._stats_history_task and not self._stats_history_task.done():
            self._stats_history_task.cancel()
            try:
                await self._stats_history_task
            except asyncio.CancelledError:
                pass
            log.info("Stats history task cancelled")

        if self._minute_stats_task and not self._minute_stats_task.done():
            self._minute_stats_task.cancel()
            try:
                await self._minute_stats_task
            except asyncio.CancelledError:
                pass
            log.info("Minute stats task cancelled")

        if self._balance_refresh_task and not self._balance_refresh_task.done():
            self._balance_refresh_task.cancel()
            try:
                await self._balance_refresh_task
            except asyncio.CancelledError:
                pass
            log.info("Balance refresh task cancelled")

        # Send shutdown notification
        try:
            notifier = get_notifier()
            await notifier.notify_shutdown(reason="normal")
            await notifier.close()
        except Exception:
            pass

        await self.scanner.close()
        await self.executor.close()
        self._log_stats()

    def _log_stats(self) -> None:
        """Log statistics."""
        runtime = datetime.utcnow() - self.stats.started_at
        hours = runtime.total_seconds() / 3600

        scanner_stats = self.scanner.get_stats()

        log.info(
            "Bot statistics",
            runtime=f"{hours:.1f}h",
            markets=scanner_stats.get("markets", 0),
            price_updates=scanner_stats.get("price_updates", 0),
            opportunities=self.stats.opportunities_found,
            trades=self.stats.trades_executed,
            successful=self.stats.trades_successful,
            profit=f"${float(self.stats.total_profit):.2f}",
        )

    async def __aenter__(self) -> "RealtimeArbitrageBot":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.shutdown()


async def run_realtime_bot() -> None:
    """Entry point for running the real-time bot."""
    settings = get_settings()
    setup_logging(settings.log_level)

    async with RealtimeArbitrageBot() as bot:
        await bot.run()
