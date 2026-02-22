import io

import matplotlib.pyplot as plt
import pandas as pd

from . import market_data


EXCHANGE_IDS = ["gateio", "bybit", "mexc"]


def _get_exchange(exchange_id: str):
    cls = getattr(ccxt, exchange_id)
    return cls({"enableRateLimit": True, "timeout": 10000})


def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 220) -> pd.DataFrame:
    last_error = None
    for ex_id in EXCHANGE_IDS:
        try:
            ex = _get_exchange(ex_id)
            ohlcv = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
            df["dt"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
            return df
        except Exception as e:
            last_error = f"{ex_id}: {e}"
            continue
    raise RuntimeError(last_error or "Не удалось получить OHLCV")



def add_ma30(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ma30"] = df["close"].rolling(30).mean()
    return df


def detect_regime(df: pd.DataFrame) -> str:
    ma = df["ma30"].dropna()
    if len(ma) < 12:
        return "UNKNOWN"
    slope = ma.iloc[-1] - ma.iloc[-10]
    price = df["close"].iloc[-1]
    ma_last = ma.iloc[-1]
    eps = abs(ma_last) * 0.0005 + 1e-9
    if slope > eps and price >= ma_last:
        return "TREND"
    if abs(slope) <= eps:
        return "RANGE"
    if slope < -eps and price <= ma_last:
        return "WEAKNESS"
    return "RANGE"


def render_png(df: pd.DataFrame, title: str) -> bytes:
    fig = plt.figure(figsize=(10, 5))
    ax = fig.add_subplot(111)
    ax.plot(df["dt"], df["close"], label="close")
    ax.plot(df["dt"], df["ma30"], label="MA30")
    ax.set_title(title)
    ax.legend()
    fig.autofmt_xdate()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
