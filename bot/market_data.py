import logging
import time
from typing import Any

import ccxt

logger = logging.getLogger(__name__)

PRIMARY_EXCHANGE = "gateio"
FALLBACK_EXCHANGE = "bybit"
COMMON_EXCHANGE_PARAMS: dict[str, Any] = {
    "enableRateLimit": True,
    "timeout": 10000,
    "options": {
        "adjustForTimeDifference": True,
    },
}


class MarketDataError(Exception):
    def __init__(self, user_message: str, details: str):
        super().__init__(details)
        self.user_message = user_message
        self.details = details


def get_exchange(exchange_id: str = PRIMARY_EXCHANGE) -> ccxt.Exchange:
    try:
        exchange_cls = getattr(ccxt, exchange_id)
    except AttributeError as exc:
        raise MarketDataError(
            "Сервис котировок временно недоступен. Попробуйте позже.",
            f"Exchange class not found: {exchange_id}",
        ) from exc
    return exchange_cls(COMMON_EXCHANGE_PARAMS)


def _retry_call(
    endpoint: str,
    symbol: str | None,
    timeframe: str | None,
    *args: Any,
    retries: int = 3,
    retry_delay_s: float = 0.8,
    **kwargs: Any,
) -> Any:
    last_exc: Exception | None = None
    for exchange_id in (PRIMARY_EXCHANGE, FALLBACK_EXCHANGE):
        exchange = get_exchange(exchange_id)
        method = getattr(exchange, endpoint)
        for attempt in range(1, retries + 1):
            try:
                return method(*args, **kwargs)
            except (ccxt.NetworkError, ccxt.ExchangeError) as exc:
                last_exc = exc
                logger.warning(
                    "Market data request failed: exchange=%s endpoint=%s symbol=%s timeframe=%s attempt=%s/%s error_type=%s error=%s",
                    exchange_id,
                    endpoint,
                    symbol,
                    timeframe,
                    attempt,
                    retries,
                    type(exc).__name__,
                    str(exc),
                )
                if attempt < retries:
                    time.sleep(retry_delay_s)
                    continue
                # switch to fallback exchange after final attempt on current one

    details = (
        f"All exchanges failed: endpoint={endpoint} symbol={symbol} "
        f"timeframe={timeframe} last_error_type={type(last_exc).__name__ if last_exc else 'Unknown'} "
        f"last_error={str(last_exc) if last_exc else 'N/A'}"
    )
    raise MarketDataError(
        "Биржа временно недоступна. Попробуйте через минуту.",
        details,
    )


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 220) -> list[list[Any]]:
    return _retry_call(
        "fetch_ohlcv",
        symbol,
        timeframe,
        symbol,
        timeframe=timeframe,
        limit=limit,
    )


def fetch_tickers() -> dict[str, Any]:
    return _retry_call("fetch_tickers", None, None)


def load_markets() -> dict[str, Any]:
    return _retry_call("load_markets", None, None)
