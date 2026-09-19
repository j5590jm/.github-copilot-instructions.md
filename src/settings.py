"""Strongly typed, fail-closed application settings."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TradingMode(StrEnum):
    """Operating modes supported by the trading system."""

    BACKTEST = "BACKTEST"
    PAPER = "PAPER"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and an optional ``.env`` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        enable_decoding=False,
        extra="ignore",
    )

    account_equity: Decimal = Decimal("1000.00")
    max_gross_notional: Decimal = Decimal("1000.00")
    max_risk_per_trade: Decimal = Decimal("10.00")
    max_daily_loss: Decimal = Decimal("25.00")
    max_concurrent_positions: int = Field(default=1, ge=1)

    trading_mode: TradingMode = TradingMode.BACKTEST
    enable_live_trading: bool = False
    supported_symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

    binance_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_API_KEY"),
    )
    binance_api_secret: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("BINANCE_API_SECRET"),
    )

    log_level: str = "INFO"
    database_path: Path = Path("data/trading.db")
    data_directory: Path = Path("data")
    model_directory: Path = Path("models")

    network_connect_timeout_seconds: float = Field(default=5.0, gt=0)
    network_read_timeout_seconds: float = Field(default=10.0, gt=0)
    network_write_timeout_seconds: float = Field(default=10.0, gt=0)
    network_pool_timeout_seconds: float = Field(default=5.0, gt=0)

    market_data_stale_after_seconds: float = Field(default=30.0, gt=0)
    exchange_metadata_stale_after_seconds: float = Field(default=300.0, gt=0)
    account_state_stale_after_seconds: float = Field(default=60.0, gt=0)

    max_order_notional: Decimal = Decimal("1000.00")
    max_daily_trade_count: int = Field(default=100, ge=1)
    max_slippage_bps: Decimal = Field(default=Decimal("25"), ge=Decimal("0"))

    ml_min_prediction_confidence: float = Field(default=0.60, ge=0, le=1)
    ml_min_validation_score: float = Field(default=0.50, ge=0, le=1)

    @field_validator("supported_symbols", mode="before")
    @classmethod
    def parse_symbols(cls, value: object) -> tuple[str, ...]:
        """Accept a comma-separated environment value while storing normalized symbols."""
        if isinstance(value, str):
            return tuple(symbol.strip().upper() for symbol in value.split(",") if symbol.strip())
        if isinstance(value, (list, tuple)):
            return tuple(str(symbol).strip().upper() for symbol in value if str(symbol).strip())
        raise ValueError("SUPPORTED_SYMBOLS must be a comma-separated string or sequence")

    @model_validator(mode="after")
    def require_live_trading_gate(self) -> Settings:
        """Reject live operation unless the deliberate safety gate is set."""
        if self.trading_mode is TradingMode.LIVE and not self.enable_live_trading:
            raise ValueError("LIVE mode requires ENABLE_LIVE_TRADING=true")
        return self

    def is_live_enabled(self) -> bool:
        """Return whether live order execution is explicitly permitted."""
        return self.trading_mode is TradingMode.LIVE and self.enable_live_trading

    def is_paper_mode(self) -> bool:
        """Return whether paper trading is selected."""
        return self.trading_mode is TradingMode.PAPER

    def is_backtest_mode(self) -> bool:
        """Return whether backtesting is selected."""
        return self.trading_mode is TradingMode.BACKTEST

    def is_testnet_mode(self) -> bool:
        """Return whether exchange testnet trading is selected."""
        return self.trading_mode is TradingMode.TESTNET