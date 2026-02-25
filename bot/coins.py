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


def _normalize_symbol_input(raw_query: str) -> str:
    return raw_query.strip().upper().replace("-", "/").replace("_", "/")


def search_market_symbols(query: str, limit: int = 10) -> list[str]:
    needle = _normalize_symbol_input(query)
    if not needle:
        return []

    try:
        symbols = sorted(_load_market_symbols())
    except MarketDataError:
        return []

    ranked: list[tuple[int, str]] = []
    has_slash = "/" in needle
    base_q, quote_q = (needle.split("/", maxsplit=1) + [""])[:2]

    for symbol in symbols:
        upper_symbol = symbol.upper()
        if "/" in upper_symbol:
            base, quote = upper_symbol.split("/", maxsplit=1)
        else:
            base, quote = upper_symbol, ""

        score = -1
        if upper_symbol == needle:
            score = 0
        elif has_slash:
            if base_q and quote_q and base.startswith(base_q) and quote.startswith(quote_q):
                score = 1
            elif base_q and quote_q and base_q in base and quote_q in quote:
                score = 2
            elif needle in upper_symbol:
                score = 3
        else:
            if base == needle or quote == needle:
                score = 1
            elif base.startswith(needle) or quote.startswith(needle):
                score = 2
            elif needle in base or needle in quote:
                score = 3
            elif needle in upper_symbol:
                score = 4

        if score >= 0:
            ranked.append((score, symbol))

    ranked.sort(key=lambda item: (item[0], item[1]))
    return [symbol for _, symbol in ranked[:limit]]
