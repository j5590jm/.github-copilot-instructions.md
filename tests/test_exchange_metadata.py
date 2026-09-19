"""Tests for exchange metadata safety and Decimal trading-rule validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from src.exchange_metadata import (
    ExchangeMetadataError,
    ExchangeMetadataService,
    SymbolRules,
    floor_quantity_to_step,
    round_price_to_tick,
    validate_notional,
    validate_price,
    validate_quantity,
)


class FakeExchangeClient:
    """Provides realistic exchange metadata without network access."""

    def get_exchange_info(self) -> dict[str, object]:
        return {
            "symbols": [
                {
                    "symbol": "TESTUSDT",
                    "status": "TRADING",
                    "baseAsset": "TEST",
                    "quoteAsset": "USDT",
                    "quotePrecision": 2,
                    "baseAssetPrecision": 3,
                    "orderTypes": ["LIMIT", "MARKET", "STOP_LOSS_LIMIT"],
                    "filters": [
                        {"filterType": "PRICE_FILTER", "tickSize": "0.05"},
                        {"filterType": "LOT_SIZE", "minQty": "0.010", "maxQty": "5.000", "stepSize": "0.010"},
                        {"filterType": "MIN_NOTIONAL", "minNotional": "10.00"},
                    ],
                }
            ]
        }


@pytest.fixture
def rules() -> SymbolRules:
    service = ExchangeMetadataService(
        FakeExchangeClient(),
        supported_symbols=("TESTUSDT",),
        stale_after=timedelta(minutes=5),
    )
    service.refresh()
    return service.get_symbol_rules("TESTUSDT")


def test_prices_round_down_to_exchange_tick(rules: SymbolRules) -> None:
    assert round_price_to_tick(Decimal("12.349"), rules) == Decimal("12.30")


def test_quantities_floor_to_exchange_step(rules: SymbolRules) -> None:
    assert floor_quantity_to_step(Decimal("1.239"), rules) == Decimal("1.230")


def test_invalid_step_quantity_is_rejected(rules: SymbolRules) -> None:
    with pytest.raises(ExchangeMetadataError, match="step size"):
        validate_quantity(Decimal("1.239"), rules)


def test_quantities_outside_exchange_bounds_are_rejected(rules: SymbolRules) -> None:
    with pytest.raises(ExchangeMetadataError, match="below"):
        validate_quantity(Decimal("0.009"), rules)
    with pytest.raises(ExchangeMetadataError, match="exceeds"):
        validate_quantity(Decimal("5.010"), rules)


def test_invalid_tick_price_is_rejected(rules: SymbolRules) -> None:
    with pytest.raises(ExchangeMetadataError, match="tick size"):
        validate_price(Decimal("12.34"), rules)


def test_notional_below_exchange_minimum_is_rejected(rules: SymbolRules) -> None:
    with pytest.raises(ExchangeMetadataError, match="notional"):
        validate_notional(Decimal("10.00"), Decimal("0.010"), rules)


def test_stale_metadata_blocks_new_orders() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock_value = [now]
    service = ExchangeMetadataService(
        FakeExchangeClient(),
        supported_symbols=("TESTUSDT",),
        stale_after=timedelta(seconds=30),
        clock=lambda: clock_value[0],
    )
    service.refresh()
    clock_value[0] = now + timedelta(seconds=31)

    assert not service.can_submit_new_orders()
    with pytest.raises(ExchangeMetadataError, match="stale"):
        service.require_fresh_metadata()


def test_failed_refresh_invalidates_cached_metadata() -> None:
    class FailingExchangeClient:
        def get_exchange_info(self) -> dict[str, object]:
            raise TimeoutError("network timed out")

    service = ExchangeMetadataService(
        FailingExchangeClient(),
        supported_symbols=("TESTUSDT",),
        stale_after=timedelta(minutes=5),
    )

    with pytest.raises(ExchangeMetadataError, match="could not be retrieved"):
        service.refresh()
    assert not service.can_submit_new_orders()