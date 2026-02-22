from . import market_data


EXCHANGE_IDS = ["gateio", "bybit", "mexc"]


def _get_exchange(exchange_id: str):
    cls = getattr(ccxt, exchange_id)
    return cls({"enableRateLimit": True, "timeout": 10000})


def top_movers(limit: int = 10, direction: str = "gainers") -> list[tuple[str, float]]:
    last_error = None
    for ex_id in EXCHANGE_IDS:
        try:
            ex = _get_exchange(ex_id)
            tickers = ex.fetch_tickers()
            items = []
            for sym, t in tickers.items():
                if not sym.endswith("/USDT"):
                    continue
                pct = t.get("percentage")
                if pct is None:
                    o = t.get("open")
                    last = t.get("last")
                    if o and last:
                        pct = (last - o) / o * 100
                if pct is None:
                    continue
                items.append((sym, float(pct)))
            if direction == "gainers":
                items.sort(key=lambda x: x[1], reverse=True)
            else:
                items.sort(key=lambda x: x[1])
            if items:
                return items[:limit]
        except Exception as e:
            last_error = f"{ex_id}: {e}"
            continue
    raise RuntimeError(last_error or "No exchange data available")


def symbol_exists(symbol: str) -> bool:
    for ex_id in EXCHANGE_IDS:
        try:
            ex = _get_exchange(ex_id)
            markets = ex.load_markets()
            if symbol in markets:
                return True
        except Exception:
            continue
    return False
