import ccxt

def top_movers(limit: int = 10, direction: str = "gainers") -> list[tuple[str, float]]:
    ex = ccxt.gateio({"enableRateLimit": True})
    tickers = ex.fetch_tickers()
    items=[]
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
    return items[:limit]
