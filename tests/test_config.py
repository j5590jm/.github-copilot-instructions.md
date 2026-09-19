"""Safety tests for runtime configuration."""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from src.config import Settings, TradingMode


def test_default_mode_is_backtest() -> None:
    settings = Settings(_env_file=None)

    assert settings.trading_mode is TradingMode.BACKTEST
    assert settings.is_backtest_mode()
    assert not settings.is_live_enabled()


def test_live_mode_requires_explicit_enablement() -> None:
    with pytest.raises(ValidationError, match="ENABLE_LIVE_TRADING=true"):
        Settings(trading_mode=TradingMode.LIVE, enable_live_trading=False, _env_file=None)

    settings = Settings(trading_mode=TradingMode.LIVE, enable_live_trading=True, _env_file=None)
    assert settings.is_live_enabled()


def test_missing_api_credentials_do_not_prevent_backtesting() -> None:
    settings = Settings(_env_file=None)

    assert settings.binance_api_key is None
    assert settings.binance_api_secret is None
    assert settings.is_backtest_mode()


def test_secrets_are_redacted_from_repr_and_logs(caplog: pytest.LogCaptureFixture) -> None:
    api_key = "api-key-that-must-not-appear"
    api_secret = "api-secret-that-must-not-appear"
    settings = Settings(
        binance_api_key=api_key,
        binance_api_secret=api_secret,
        _env_file=None,
    )

    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("Settings: %r", settings)

    rendered = f"{settings!r}\n{caplog.text}"
    assert api_key not in rendered
    assert api_secret not in rendered
    assert "**********" in rendered