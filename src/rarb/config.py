"""Configuration management for rarb."""

from pathlib import Path
from typing import Optional

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Wallet Configuration
    private_key: Optional[SecretStr] = Field(
        default=None,
        description="Private key for signing transactions (hex string with 0x prefix)",
    )
    wallet_address: Optional[str] = Field(
        default=None,
        description="Wallet address for trading",
    )

    # Network Configuration
    polygon_rpc_url: str = Field(
        default="https://polygon-rpc.com",
        description="Polygon RPC endpoint URL",
    )
    chain_id: int = Field(
        default=137,
        description="Chain ID (137 for Polygon mainnet)",
    )

    # Trading Parameters
    min_profit_threshold: float = Field(
        default=0.005,
        description="Minimum profit threshold (0.005 = 0.5%)",
        ge=0.0,
        le=0.1,
    )
    max_position_size: float = Field(
        default=100.0,
        description="Maximum position size in USD per market",
        ge=1.0,
    )
    poll_interval_seconds: float = Field(
        default=2.0,
        description="Seconds between market polls",
        ge=0.5,
        le=60.0,
    )
    min_liquidity_usd: float = Field(
        default=10000.0,
        description="Minimum liquidity in USD to consider a market",
        ge=0.0,
    )
    max_days_until_resolution: int = Field(
        default=7,
        description="Maximum days until market resolution (skip markets resolving later)",
        ge=1,
        le=365,
    )

    # --- Risk management (5-min / short-term markets) ---
    risk_per_trade_pct: float = Field(
        default=0.8,
        description="Max risk per trade as % of account (0.8 = 0.8%). Use 0.5-1.5% for 5-min markets.",
        ge=0.1,
        le=5.0,
    )
    stop_loss_pct: float = Field(
        default=5.0,
        description="Fixed %% stop distance from entry (e.g. 5 = 5%%). Entry price * (1 - stop_pct/100).",
        ge=1.0,
        le=20.0,
    )
    time_stop_seconds: int = Field(
        default=120,
        description="Time-based stop: do not hold position longer than this (seconds). Avoids dead positions near expiry.",
        ge=30,
        le=300,
    )
    position_cap_pct: float = Field(
        default=25.0,
        description="Max position size as %% of account (e.g. 25 = 25%%). Caps shares * entry even when risk formula allows more.",
        ge=5.0,
        le=100.0,
    )
    take_profit_pct_to_one: float = Field(
        default=55.0,
        description="TP1: sell this %% of 'remaining to 1' (e.g. 55 = sell first portion at entry + 55%% of (1 - entry)).",
        ge=30.0,
        le=95.0,
    )
    take_profit_first_portion_pct: float = Field(
        default=65.0,
        description="%% of position to sell at TP1 (e.g. 65 = sell 65%% at first target, rest at TP2 or stop).",
        ge=20.0,
        le=90.0,
    )
    consecutive_losses_pause: int = Field(
        default=5,
        description="Pause trading for consecutive_loss_pause_minutes after this many consecutive losing trades.",
        ge=2,
        le=20,
    )
    consecutive_loss_pause_minutes: int = Field(
        default=30,
        description="Minutes to pause after consecutive loss limit hit.",
        ge=5,
        le=120,
    )
    session_drawdown_pct: float = Field(
        default=4.0,
        description="Session drawdown %% (vs session start balance) to pause trading for session_pause_minutes.",
        ge=1.0,
        le=20.0,
    )
    session_pause_minutes: int = Field(
        default=60,
        description="Minutes to pause after session drawdown limit hit.",
        ge=10,
        le=240,
    )
    daily_drawdown_pct: float = Field(
        default=8.0,
        description="Daily drawdown %% (vs daily start balance) to stop trading for the day.",
        ge=2.0,
        le=25.0,
    )
    monthly_drawdown_pct: float = Field(
        default=20.0,
        description="Monthly drawdown %% to halt bot (manual review required).",
        ge=5.0,
        le=50.0,
    )
    volatility_skip_1min_std: Optional[float] = Field(
        default=0.028,
        description="Skip new entries if 1-min price std dev exceeds this (e.g. 0.028). None = disabled.",
        ge=0.01,
        le=0.1,
    )
    min_seconds_until_resolution: int = Field(
        default=90,
        description="Do not enter if less than this many seconds until market resolution.",
        ge=0,
        le=600,
    )
    min_volume_60s_usd: Optional[float] = Field(
        default=None,
        description="Skip if last 60s volume < this (USD). None = disabled. Requires volume data.",
        ge=0.0,
    )
    max_zscore_3min: Optional[float] = Field(
        default=2.5,
        description="Skip if |price - 3min mean| > this many std devs (mean reversion filter). None = disabled.",
        ge=1.5,
        le=5.0,
    )
    max_rsi_overbought: Optional[float] = Field(
        default=80.0,
        description="Skip momentum long if RSI(8) > this (overbought). None = disabled.",
        ge=70.0,
        le=95.0,
    )

    num_ws_connections: int = Field(
        default=6,
        description="Number of WebSocket connections for scanner (each handles 250 markets)",
        ge=1,
        le=20,
    )

    # API Endpoints
    clob_base_url: str = Field(
        default="https://clob.polymarket.com",
        description="Polymarket CLOB API base URL",
    )
    gamma_base_url: str = Field(
        default="https://gamma-api.polymarket.com",
        description="Polymarket Gamma API base URL",
    )

    # Polymarket API Credentials (L2 Auth) - generated from private key
    poly_api_key: Optional[str] = Field(
        default=None,
        description="Polymarket API key for L2 authentication",
    )
    poly_api_secret: Optional[SecretStr] = Field(
        default=None,
        description="Polymarket API secret for L2 authentication",
    )
    poly_api_passphrase: Optional[SecretStr] = Field(
        default=None,
        description="Polymarket API passphrase for L2 authentication",
    )

    # Alerts (optional)
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token for alerts",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Telegram chat ID for alerts",
    )
    slack_webhook_url: Optional[str] = Field(
        default=None,
        description="Slack webhook URL for notifications",
    )

    # Mode
    dry_run: bool = Field(
        default=True,
        description="If true, simulate trades without executing",
    )

    # Dashboard
    dashboard_username: str = Field(
        default="admin",
        description="Dashboard login username",
    )
    dashboard_password: str = Field(
        default="",
        description="Dashboard login password",
    )
    dashboard_port: int = Field(
        default=8080,
        description="Dashboard web server port",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

    # SOCKS5 Proxy (for routing order API calls through non-US server)
    socks5_proxy_host: Optional[str] = Field(
        default=None,
        description="SOCKS5 proxy hostname or IP",
    )
    socks5_proxy_port: int = Field(
        default=1080,
        description="SOCKS5 proxy port",
    )
    socks5_proxy_user: Optional[str] = Field(
        default=None,
        description="SOCKS5 proxy username (if authentication required)",
    )
    socks5_proxy_pass: Optional[SecretStr] = Field(
        default=None,
        description="SOCKS5 proxy password (if authentication required)",
    )

    @field_validator("wallet_address", mode="before")
    @classmethod
    def validate_wallet_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("Wallet address must be a valid Ethereum address (0x + 40 hex chars)")
        return v.lower()

    @field_validator("private_key", mode="before")
    @classmethod
    def validate_private_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        if not v.startswith("0x"):
            raise ValueError("Private key must start with 0x")
        if len(v) != 66:  # 0x + 64 hex chars
            raise ValueError("Private key must be 32 bytes (64 hex chars + 0x prefix)")
        return v

    def is_trading_enabled(self) -> bool:
        """Check if Polymarket trading credentials are configured."""
        return self.private_key is not None and self.wallet_address is not None

    def get_socks5_proxy_url(self) -> Optional[str]:
        """Get SOCKS5 proxy URL if configured.

        Uses socks5h:// scheme to ensure DNS resolution happens through the proxy,
        which is required for geo-restriction bypass.
        """
        if not self.socks5_proxy_host:
            return None
        if self.socks5_proxy_user and self.socks5_proxy_pass:
            password = self.socks5_proxy_pass.get_secret_value()
            return f"socks5h://{self.socks5_proxy_user}:{password}@{self.socks5_proxy_host}:{self.socks5_proxy_port}"
        return f"socks5h://{self.socks5_proxy_host}:{self.socks5_proxy_port}"

    def is_proxy_enabled(self) -> bool:
        """Check if SOCKS5 proxy is configured."""
        return self.socks5_proxy_host is not None

    def is_kalshi_enabled(self) -> bool:
        """Check if Kalshi is configured. Deprecated - always returns False."""
        return False


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings
