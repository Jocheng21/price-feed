#!/usr/bin/env python3
"""Pull current prices for Joseph's ledger and write prices.json.

Primary source: yfinance (Yahoo). Fallback: stooq CSV (no API key).
Every price carries the timestamp the source itself reported, so nothing
is ever published with an invented date.
"""
import json, sys, datetime as dt
import urllib.request

# ticker -> (yfinance symbol, stooq symbol or None, currency)
TICKERS = {
    "D05":  ("D05.SI",  "d05.sg", "SGD"),
    "Z74":  ("Z74.SI",  "z74.sg", "SGD"),
    "O39":  ("O39.SI",  "o39.sg", "SGD"),
    "BN4":  ("BN4.SI",  "bn4.sg", "SGD"),
    "AWX":  ("AWX.SI",  "awx.sg", "SGD"),
    "C6L":  ("C6L.SI",  "c6l.sg", "SGD"),
    "VOO":  ("VOO",     "voo.us", "USD"),
    "VTI":  ("VTI",     "vti.us", "USD"),
    "GOOG": ("GOOG",    "goog.us","USD"),
    "AMZN": ("AMZN",    "amzn.us","USD"),
    "NVDA": ("NVDA",    "nvda.us","USD"),
    "SGOL": ("SGOL",    "sgol.us","USD"),
    "BABA": ("BABA",    "baba.us","USD"),
    "AAPL": ("AAPL",    "aapl.us","USD"),
    "FULLERTON": ("0P0001J04G.SI", None, "USD"),
    "LION":      ("0P00019ITU.SI", None, "SGD"),
}
FX_SYMBOL = "SGD=X"   # USD -> SGD

def from_yfinance(symbols):
    """Returns {symbol: (price, iso_date)}; missing symbols simply absent."""
    out = {}
    try:
        import yfinance as yf
    except ImportError:
        return out
    try:
        data = yf.download(symbols, period="5d", interval="1d",
                           progress=False, group_by="ticker", auto_adjust=False)
    except Exception as e:
        print(f"yfinance bulk download failed: {e}", file=sys.stderr)
        return out
    for sym in symbols:
        try:
            df = data[sym] if len(symbols) > 1 else data
            df = df.dropna(subset=["Close"])
            if df.empty:
                continue
            last = df.iloc[-1]
            out[sym] = (round(float(last["Close"]), 4),
                        df.index[-1].date().isoformat())
        except Exception:
            continue
    return out

def from_stooq(sym):
    """Fallback. Returns (price, iso_date) or None."""
    url = f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            lines = r.read().decode().strip().splitlines()
        if len(lines) < 2:
            return None
        cols = lines[0].split(","); vals = lines[1].split(",")
        row = dict(zip(cols, vals))
        close, date = row.get("Close"), row.get("Date")
        if not close or close in ("N/D", "") or not date or date == "N/D":
            return None
        return round(float(close), 4), date
    except Exception as e:
        print(f"stooq {sym} failed: {e}", file=sys.stderr)
        return None

def main():
    y_syms = [v[0] for v in TICKERS.values()] + [FX_SYMBOL]
    y = from_yfinance(y_syms)

    prices, stale = {}, []
    for tk, (ysym, ssym, ccy) in TICKERS.items():
        got = y.get(ysym)
        src = "yfinance"
        if not got and ssym:
            got = from_stooq(ssym)
            src = "stooq"
        if got:
            prices[tk] = {"price": got[0], "asOf": got[1],
                          "currency": ccy, "source": src}
        else:
            stale.append(tk)
            print(f"NO DATED PRICE for {tk} — leaving to the consumer", file=sys.stderr)

    fx = y.get(FX_SYMBOL)
    payload = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "fx": ({"usdsgd": fx[0], "asOf": fx[1], "source": "yfinance"} if fx else None),
        "prices": prices,
        "unavailable": stale,
        "note": "Each price carries the trading date its source reported. "
                "Tickers under 'unavailable' had no dated quote this run — "
                "keep the previous value and mark it stale.",
    }
    with open("prices.json", "w") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    print(json.dumps(payload, indent=2)[:1200])
    print(f"\nwrote {len(prices)}/{len(TICKERS)} prices; unavailable: {stale or 'none'}")

if __name__ == "__main__":
    main()
