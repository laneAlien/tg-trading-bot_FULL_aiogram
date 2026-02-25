from functools import lru_cache

from . import market_data
from .market_data import MarketDataError


def top_movers(limit: int = 10, direction: str = "gainers") -> list[tuple[str, float]]:
    tickers = market_data.fetch_tickers()
    items = []
    for sym, ticker in tickers.items():
        if not sym.endswith("/USDT"):
            continue
        pct = ticker.get("percentage")
        if pct is None:
            opened = ticker.get("open")
            last = ticker.get("last")
            if opened and last:
                pct = (last - opened) / opened * 100
        if pct is None:
            continue
        items.append((sym, float(pct)))

    if direction == "gainers":
        items.sort(key=lambda x: x[1], reverse=True)
    else:
        items.sort(key=lambda x: x[1])

    if items:
        return items[:limit]
    raise MarketDataError(
        "Нет данных по активам сейчас. Попробуйте чуть позже.",
        "No /USDT tickers with valid percentage found.",
    )


@lru_cache(maxsize=1)
def _load_market_symbols() -> frozenset[str]:
    markets = market_data.load_markets()
    return frozenset(markets.keys())


def symbol_exists(symbol: str) -> bool:
    try:
        return symbol in _load_market_symbols()
    except MarketDataError:
        return False
