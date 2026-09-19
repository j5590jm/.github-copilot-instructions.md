# Crypto Trading Assistant — Project Instructions

You are helping build a production-quality cryptocurrency trading research and execution system in Python 3.11+ on Windows 11.

## Safety and trading-mode requirements

- The system is initially **BACKTEST** and **PAPER** trading only.
- Do **not** enable live trading unless configuration is explicitly changed to allow it.
- Default to `TRADING_MODE = "BACKTEST"`.
- Supported trading modes are `BACKTEST`, `PAPER`, `TESTNET`, and `LIVE`.
- `LIVE` mode must require an explicit `ENABLE_LIVE_TRADING=false` style gate, and no live order endpoint may be called unless that flag is enabled.
- The system must fail closed.

## Risk controls

- The `RiskManager` is an absolute veto layer.
- Every order must pass `RiskManager` before reaching `ExecutionEngine`.
- Never allow an ML model, strategy, signal generator, or execution module to bypass risk controls.
- Every order decision must be journaled.
- If market data is stale, stop trading.
- If exchange metadata is stale, stop trading.
- If account state is uncertain, stop opening new positions.
- If a position cannot be reconciled, stop opening new positions.
- If the protective stop cannot be confirmed, stop opening new positions and invoke the emergency risk procedure.

## Required architecture order

Implement and preserve this flow:

`market data -> normalized events -> bars/order book state -> features -> regime detection -> ML prediction -> strategy -> risk manager -> execution -> reconciliation -> journal`

## Numeric and exchange-rule requirements

- Use `Decimal` for balances, prices, quantities, fees, notionals, risk calculations, and order sizing.
- Float may be used for machine-learning features, statistical calculations, and indicators.
- Never mix `float` and `Decimal` implicitly.
- Obtain exchange trading rules dynamically from exchange metadata.
- Do **not** hard-code tick sizes, quantity step sizes, minimum quantities, minimum notionals, maximum quantities, leverage limits, or maintenance margin rates.
- Validate prices and quantities against current exchange metadata before order submission.

## Initial capital and position limits

- `ACCOUNT_EQUITY = Decimal("1000.00")`
- `MAX_GROSS_NOTIONAL = Decimal("1000.00")`
- `MAX_RISK_PER_TRADE = Decimal("10.00")`
- `MAX_DAILY_LOSS = Decimal("25.00")`
- `MAX_CONCURRENT_POSITIONS = 1`

## Secrets and credentials

- Never put Binance API keys or secrets directly in source code.
- Use `.env` for secrets.
- Keep `.env` out of version control.

## Research, ML, and backtesting requirements

- Do not claim any strategy guarantees profit.
- Validate profitability claims with out-of-sample testing.
- Avoid lookahead bias.
- Every feature must document exactly which historical observations it uses.
- Every ML model must have a training dataset, validation dataset, test dataset, model version, feature version, training timestamp, performance metrics, and a saved artifact.
- Do not optimize directly against the final test set.
- Backtests must be reproducible.
- All important decisions must be observable through structured logs.

## Networking and exchange behavior

- Do not implement techniques intended to disguise account identity or evade exchange monitoring.
- A proxy may be supported for legitimate networking or reliability purposes, but it must not be described as making the account anonymous or untraceable.
- Prefer official exchange documentation and exchange-provided metadata over assumptions.
- When a requirement conflicts with documented exchange API behavior, follow the documented behavior and explain the conflict in a code comment.

## Coding requirements

- Write clear Python suitable for someone who is not an experienced programmer.
- Every new module must contain type hints, docstrings, error handling, and unit-testable functions.
- Before modifying an existing file, inspect it first.
- Do not silently overwrite existing working functionality.
.\.venv\Scripts\Activate.ps1
pytest tests/test_config.py -q