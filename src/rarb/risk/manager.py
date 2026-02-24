"""
Risk manager for 5-minute / short-term Polymarket crypto prediction markets.

Implements:
- Position sizing (Kelly-inspired, conservative): risk_per_trade = balance * risk_pct, shares = risk / (entry - stop)
- Circuit breakers: consecutive losses, session drawdown, daily drawdown, monthly drawdown, volatility kill
- Pre-trade filters: min seconds to resolution, optional volume/z-score/RSI/volatility
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional

from rarb.config import get_settings
from rarb.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class PreTradeFilterResult:
    """Result of pre-trade filters. allowed=False means skip the trade."""

    allowed: bool
    reason: str = ""


class RiskManager:
    """
    Layered risk control: per-trade position sizing, circuit breakers, and pre-trade filters.

    State is session-scoped (consecutive losses, pause until, session/daily/monthly start balances).
    """

    def __init__(self) -> None:
        self._consecutive_losses: int = 0
        self._pause_until: Optional[datetime] = None
        self._session_start_balance: Optional[Decimal] = None
        self._daily_start_balance: Optional[Decimal] = None
        self._monthly_start_balance: Optional[Decimal] = None
        self._last_daily_date: Optional[str] = None
        self._last_monthly_key: Optional[str] = None

    def is_paused(self) -> bool:
        """True if we are in a cooldown (consecutive losses or drawdown pause)."""
        if self._pause_until is None:
            return False
        if datetime.now(timezone.utc) >= self._pause_until:
            self._pause_until = None
            log.info("Risk pause expired - resuming trading")
            return False
        return True

    def pause_until_utc(self) -> Optional[datetime]:
        """When the current pause ends (UTC). None if not paused."""
        return self._pause_until

    def _ensure_session_daily_monthly(self, current_balance: Decimal) -> None:
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        month_key = now.strftime("%Y-%m")

        if self._session_start_balance is None:
            self._session_start_balance = current_balance
        if self._last_daily_date != today:
            self._daily_start_balance = current_balance
            self._last_daily_date = today
        if self._last_monthly_key != month_key:
            self._monthly_start_balance = current_balance
            self._last_monthly_key = month_key

    def check_circuit_breakers(
        self,
        current_balance: Decimal,
        *,
        volatility_1min_std: Optional[float] = None,
    ) -> tuple[bool, str]:
        """
        Check session/daily/monthly drawdown and volatility kill.
        Returns (allowed, reason). allowed=False means do not take new trades.
        """
        settings = get_settings()
        self._ensure_session_daily_monthly(current_balance)
        assert self._session_start_balance is not None
        assert self._daily_start_balance is not None
        assert self._monthly_start_balance is not None

        # Session drawdown
        if self._session_start_balance > 0:
            session_pnl_pct = float(
                (current_balance - self._session_start_balance) / self._session_start_balance * 100
            )
            if session_pnl_pct <= -settings.session_drawdown_pct:
                self._pause_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.session_pause_minutes
                )
                return False, (
                    f"session_drawdown: {session_pnl_pct:.2f}% <= -{settings.session_drawdown_pct}%"
                )

        # Daily drawdown
        if self._daily_start_balance > 0:
            daily_pnl_pct = float(
                (current_balance - self._daily_start_balance) / self._daily_start_balance * 100
            )
            if daily_pnl_pct <= -settings.daily_drawdown_pct:
                # Stop for the day: pause until next UTC day
                tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                self._pause_until = tomorrow
                return False, (
                    f"daily_drawdown: {daily_pnl_pct:.2f}% <= -{settings.daily_drawdown_pct}%"
                )

        # Monthly drawdown
        if self._monthly_start_balance > 0:
            monthly_pnl_pct = float(
                (current_balance - self._monthly_start_balance)
                / self._monthly_start_balance
                * 100
            )
            if monthly_pnl_pct <= -settings.monthly_drawdown_pct:
                return False, (
                    f"monthly_drawdown: {monthly_pnl_pct:.2f}% <= -{settings.monthly_drawdown_pct}% "
                    "(halt bot - manual review required)"
                )

        # Volatility kill
        if settings.volatility_skip_1min_std is not None and volatility_1min_std is not None:
            if volatility_1min_std > settings.volatility_skip_1min_std:
                return False, (
                    f"volatility_kill: 1min_std={volatility_1min_std:.4f} > "
                    f"{settings.volatility_skip_1min_std}"
                )

        return True, ""

    def record_trade(self, success: bool, pnl: Decimal = Decimal("0")) -> None:
        """
        Record trade result for consecutive-loss and drawdown tracking.
        success=True for filled/winning, False for loss or failed fill.
        pnl is profit/loss in USD (negative for loss).
        """
        if success:
            self._consecutive_losses = 0
            return

        settings = get_settings()
        self._consecutive_losses += 1
        log.info(
            "Consecutive loss recorded",
            count=self._consecutive_losses,
            limit=settings.consecutive_losses_pause,
            pnl=float(pnl),
        )
        if self._consecutive_losses >= settings.consecutive_losses_pause:
            self._pause_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.consecutive_loss_pause_minutes
            )
            log.warning(
                "Circuit breaker: pausing after consecutive losses",
                consecutive=self._consecutive_losses,
                pause_minutes=settings.consecutive_loss_pause_minutes,
            )

    def position_size(
        self,
        account_balance: Decimal,
        entry_price: Decimal,
        *,
        stop_price: Optional[Decimal] = None,
        risk_fraction: Optional[float] = None,
        position_cap_fraction: Optional[float] = None,
        max_position_usd: Optional[float] = None,
    ) -> tuple[Decimal, Decimal]:
        """
        Kelly-inspired conservative position size.

        risk_per_trade = balance * risk_fraction
        expected_loss_if_stopped = entry_price - stop_price
        shares = risk_per_trade / expected_loss_if_stopped
        usd_amount = shares * entry_price, capped by position_cap of balance and max_position_usd.

        Returns (shares, usd_amount).
        """
        settings = get_settings()
        risk_frac = (risk_fraction if risk_fraction is not None else settings.risk_per_trade_pct / 100)
        cap_frac = (
            position_cap_fraction
            if position_cap_fraction is not None
            else settings.position_cap_pct / 100
        )
        max_usd = max_position_usd if max_position_usd is not None else settings.max_position_size

        if stop_price is None:
            # Fixed % stop: stop_price = entry * (1 - stop_pct/100)
            stop_pct = Decimal(str(settings.stop_loss_pct / 100))
            stop_price = entry_price * (Decimal("1") - stop_pct)

        risk_distance = entry_price - stop_price
        if risk_distance <= 0:
            log.warning("Risk distance <= 0, using minimal size")
            risk_distance = entry_price * Decimal("0.01")

        risk_per_trade = account_balance * Decimal(str(risk_frac))
        shares = (risk_per_trade / risk_distance).quantize(Decimal("1"), rounding="ROUND_DOWN")
        usd_amount = (shares * entry_price).quantize(Decimal("0.01"), rounding="ROUND_DOWN")

        # Cap by % of account
        cap_usd = account_balance * Decimal(str(cap_frac))
        if usd_amount > cap_usd and cap_usd > 0:
            usd_amount = cap_usd
            shares = (usd_amount / entry_price).quantize(Decimal("1"), rounding="ROUND_DOWN")
            usd_amount = (shares * entry_price).quantize(Decimal("0.01"), rounding="ROUND_DOWN")

        # Cap by max_position_size
        if usd_amount > Decimal(str(max_usd)):
            usd_amount = Decimal(str(max_usd))
            shares = (usd_amount / entry_price).quantize(Decimal("1"), rounding="ROUND_DOWN")
            usd_amount = (shares * entry_price).quantize(Decimal("0.01"), rounding="ROUND_DOWN")

        return shares, usd_amount

    def pre_trade_filters(
        self,
        *,
        seconds_until_resolution: Optional[float] = None,
        volume_60s_usd: Optional[float] = None,
        zscore_3min: Optional[float] = None,
        rsi_8: Optional[float] = None,
    ) -> PreTradeFilterResult:
        """
        Run pre-trade filters. Skip if any fail.
        All optional args: if not provided, that filter is skipped.
        """
        settings = get_settings()

        if seconds_until_resolution is not None and settings.min_seconds_until_resolution > 0:
            if seconds_until_resolution < settings.min_seconds_until_resolution:
                return PreTradeFilterResult(
                    allowed=False,
                    reason=f"time_to_resolution: {seconds_until_resolution:.0f}s < {settings.min_seconds_until_resolution}s",
                )

        if settings.min_volume_60s_usd is not None and volume_60s_usd is not None:
            if volume_60s_usd < settings.min_volume_60s_usd:
                return PreTradeFilterResult(
                    allowed=False,
                    reason=f"volume_60s: ${volume_60s_usd:.0f} < ${settings.min_volume_60s_usd}",
                )

        if settings.max_zscore_3min is not None and zscore_3min is not None:
            if abs(zscore_3min) > settings.max_zscore_3min:
                return PreTradeFilterResult(
                    allowed=False,
                    reason=f"zscore_3min: {zscore_3min:.2f} > {settings.max_zscore_3min}",
                )

        if settings.max_rsi_overbought is not None and rsi_8 is not None:
            if rsi_8 > settings.max_rsi_overbought:
                return PreTradeFilterResult(
                    allowed=False,
                    reason=f"rsi_overbought: {rsi_8:.1f} > {settings.max_rsi_overbought}",
                )

        return PreTradeFilterResult(allowed=True)

    def get_state(self) -> dict:
        """Current risk state for logging/dashboard."""
        return {
            "consecutive_losses": self._consecutive_losses,
            "pause_until": self._pause_until.isoformat() if self._pause_until else None,
            "session_start_balance": float(self._session_start_balance) if self._session_start_balance else None,
            "daily_start_balance": float(self._daily_start_balance) if self._daily_start_balance else None,
            "monthly_start_balance": float(self._monthly_start_balance) if self._monthly_start_balance else None,
        }
