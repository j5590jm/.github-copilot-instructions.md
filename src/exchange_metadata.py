"""Exchange symbol metadata retrieval, caching, and Decimal-based validation."""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from typing import Any, Protocol


class ExchangeMetadataError(RuntimeError):
    """Raised when exchange metadata cannot safely be used."""


class ExchangeMetadataClient(Protocol):
    """Minimal interface required from an exchange adapter."""

    def get_exchange_info(self) -> Mapping[str, Any]:
        """Return exchange metadata in the exchange adapter's normalized format."""


@dataclass(frozen=True, slots=True)
class SymbolRules:
    """Trading constraints supplied by an exchange for one symbol."""

    symbol: str
    status: str
    base_asset: str
    quote_asset: str
    price_precision: int
    quantity_precision: int
    tick_size: Decimal
    step_size: Decimal
    min_quantity: Decimal
    max_quantity: Decimal
    min_notional: Decimal
    market_order_supported: bool
    limit_order_supported: bool
    stop_order_supported: bool


def round_price_to_tick(price: Decimal, rules: SymbolRules) -> Decimal:
    """Floor a price to the exchange tick size using Decimal arithmetic only."""
    _require_positive(price, "price")
    return (price / rules.tick_size).to_integral_value(rounding=ROUND_DOWN) * rules.tick_size


def floor_quantity_to_step(quantity: Decimal, rules: SymbolRules) -> Decimal:
    """Floor position size to the exchange step size; never increase the quantity."""
    _require_positive(quantity, "quantity")
    return (quantity / rules.step_size).to_integral_value(rounding=ROUND_DOWN) * rules.step_size


def validate_price(price: Decimal, rules: SymbolRules) -> None:
    """Raise when a price is non-positive or cannot be submitted at the exchange tick."""
    _require_positive(price, "price")
    if price != round_price_to_tick(price, rules):
        raise ExchangeMetadataError(f"{rules.symbol} price does not align with tick size")


def validate_quantity(quantity: Decimal, rules: SymbolRules) -> None:
    """Raise when a quantity is outside exchange bounds or its step increment."""
    _require_positive(quantity, "quantity")
    if quantity < rules.min_quantity:
        raise ExchangeMetadataError(f"{rules.symbol} quantity is below the exchange minimum")
    if quantity > rules.max_quantity:
        raise ExchangeMetadataError(f"{rules.symbol} quantity exceeds the exchange maximum")
    if quantity != floor_quantity_to_step(quantity, rules):
        raise ExchangeMetadataError(f"{rules.symbol} quantity does not align with step size")


def validate_notional(price: Decimal, quantity: Decimal, rules: SymbolRules) -> None:
    """Raise when the Decimal order notional is below the exchange minimum."""
    validate_price(price, rules)
    validate_quantity(quantity, rules)
    if price * quantity < rules.min_notional:
        raise ExchangeMetadataError(f"{rules.symbol} order notional is below the exchange minimum")


class ExchangeMetadataService:
    """Caches configured-symbol rules and fails closed when they are unavailable or stale."""

    def __init__(
        self,
        exchange_client: ExchangeMetadataClient,
        supported_symbols: Collection[str],
        stale_after: timedelta,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if stale_after <= timedelta(0):
            raise ValueError("stale_after must be positive")
        self._exchange_client = exchange_client
        self._supported_symbols = {symbol.upper() for symbol in supported_symbols}
        self._stale_after = stale_after
        self._clock = clock or (lambda: datetime.now(UTC))
        self._rules_by_symbol: dict[str, SymbolRules] = {}
        self._refreshed_at: datetime | None = None

    @property
    def last_refreshed_at(self) -> datetime | None:
        """Return when the currently cached metadata was last successfully refreshed."""
        return self._refreshed_at

    def refresh(self) -> None:
        """Fetch and atomically replace cached rules for every configured symbol."""
        try:
            payload = self._exchange_client.get_exchange_info()
            rules = self._parse_configured_symbols(payload)
        except Exception as error:
            self.invalidate()
            raise ExchangeMetadataError("exchange metadata could not be retrieved") from error

        self._rules_by_symbol = rules
        self._refreshed_at = self._clock()

    def invalidate(self) -> None:
        """Discard cached metadata so order admission fails until a refresh succeeds."""
        self._rules_by_symbol.clear()
        self._refreshed_at = None

    def is_stale(self) -> bool:
        """Return whether metadata is absent or has exceeded its permitted age."""
        if self._refreshed_at is None or not self._rules_by_symbol:
            return True
        return self._clock() - self._refreshed_at > self._stale_after

    def can_submit_new_orders(self) -> bool:
        """Return whether the RiskManager may consider opening a new order."""
        return not self.is_stale()

    def require_fresh_metadata(self) -> None:
        """Raise a veto error that the RiskManager must treat as an order rejection."""
        if not self.can_submit_new_orders():
            raise ExchangeMetadataError("new orders are blocked because exchange metadata is stale")

    def get_symbol_rules(self, symbol: str) -> SymbolRules:
        """Return current rules for a configured symbol or reject order admission."""
        self.require_fresh_metadata()
        try:
            return self._rules_by_symbol[symbol.upper()]
        except KeyError as error:
            raise ExchangeMetadataError(f"no cached metadata for configured symbol {symbol}") from error

    def _parse_configured_symbols(self, payload: Mapping[str, Any]) -> dict[str, SymbolRules]:
        symbols = payload["symbols"]
        parsed = {
            entry["symbol"].upper(): _parse_symbol_rules(entry)
            for entry in symbols
            if entry["symbol"].upper() in self._supported_symbols
        }
        missing = self._supported_symbols - parsed.keys()
        if missing:
            raise ExchangeMetadataError(f"metadata missing configured symbols: {', '.join(sorted(missing))}")
        return parsed


def _parse_symbol_rules(symbol: Mapping[str, Any]) -> SymbolRules:
    filters = {entry["filterType"]: entry for entry in symbol["filters"]}
    price_filter = filters["PRICE_FILTER"]
    quantity_filter = filters["LOT_SIZE"]
    notional_filter = filters.get("NOTIONAL") or filters["MIN_NOTIONAL"]
    order_types = set(symbol.get("orderTypes", ()))
    return SymbolRules(
        symbol=symbol["symbol"].upper(),
        status=symbol["status"],
        base_asset=symbol["baseAsset"],
        quote_asset=symbol["quoteAsset"],
        price_precision=int(symbol.get("pricePrecision", symbol["quotePrecision"])),
        quantity_precision=int(symbol.get("quantityPrecision", symbol["baseAssetPrecision"])),
        tick_size=Decimal(price_filter["tickSize"]),
        step_size=Decimal(quantity_filter["stepSize"]),
        min_quantity=Decimal(quantity_filter["minQty"]),
        max_quantity=Decimal(quantity_filter["maxQty"]),
        min_notional=Decimal(notional_filter["minNotional"]),
        market_order_supported="MARKET" in order_types,
        limit_order_supported="LIMIT" in order_types,
        stop_order_supported=bool(order_types & {"STOP_LOSS", "STOP_LOSS_LIMIT", "TAKE_PROFIT", "TAKE_PROFIT_LIMIT"}),
    )


def _require_positive(value: Decimal, field_name: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{field_name} must be a Decimal")
    if value <= Decimal("0"):
        raise ExchangeMetadataError(f"{field_name} must be positive")