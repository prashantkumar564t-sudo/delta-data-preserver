import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from src.config import (
    DELTA_BASE_URL, 
    DEFAULT_HEADERS, 
    IST, 
    REQUEST_TIMEOUT, 
    RATE_LIMIT_SLEEP, 
    MAX_RETRIES, 
    RETRY_DELAY
)

def get_epoch_range(date_str: str) -> tuple[int, int]:
    """
    date_str: 'YYYY-MM-DD' (Target Expiry Date, e.g. '2026-11-09')
    Returns: (start_epoch, end_epoch) covering exactly 24 hours:
      Previous Day 17:30:00 IST to Target Expiry Day 17:30:00 IST.
    """
    expiry_dt = datetime.strptime(f"{date_str} 17:30:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    start_dt = expiry_dt - timedelta(days=1)
    return int(start_dt.timestamp()), int(expiry_dt.timestamp())

def parse_option_symbol(symbol: str) -> tuple[str, str, float, str]:
    """
    Parses option symbol format: 'C-BTC-72600-091126' or 'P-ETH-3200.5-141126'
    Returns: (option_type ['CE'/'PE'], underlying, strike_price, expiry_date ['YYYY-MM-DD'])
    """
    parts = symbol.split("-")
    if len(parts) >= 4:
        opt_type = "CE" if parts[0].upper() == "C" else "PE"
        underlying = parts[1]
        try:
            strike = float(parts[2])
            if strike.is_integer():
                strike = int(strike)
        except (ValueError, TypeError):
            strike = 0.0

        raw_tag = parts[3][:6]
        try:
            expiry_date = datetime.strptime(raw_tag, "%d%m%y").strftime("%Y-%m-%d")
        except Exception:
            expiry_date = "UNKNOWN"

        return opt_type, underlying, strike, expiry_date

    return "UNKNOWN", "BTC", 0.0, "UNKNOWN"

def _safe_get_request(url: str) -> dict | None:
    """Internal helper to make resilient HTTP GET requests with retries and exponential backoff."""
    req = urllib.request.Request(url, headers=DEFAULT_HEADERS)
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.HTTPError, urllib.error.URLError) as e:
            if attempt == MAX_RETRIES:
                print(f"[!] Request failed after {MAX_RETRIES} attempts: {url} -> {e}")
                return None
            time.sleep(RETRY_DELAY * attempt)
        except Exception as e:
            print(f"[!] Unexpected error requesting {url}: {e}")
            return None
    return None

def fetch_contract_candles(symbol: str, from_ts: int, to_ts: int, resolution: str = "1") -> dict | None:
    """
    Fetches 1-minute OHLCV candles for a single contract between from_ts and to_ts.
    Resolution '1' represents 1-minute candles on Delta Exchange.
    """
    url = f"{DELTA_BASE_URL}/chart/history?symbol={symbol}&resolution={resolution}&from={from_ts}&to={to_ts}"
    payload = _safe_get_request(url)
    if not payload:
        return None
    return payload.get("result", {})

def fetch_perpetual_candles(symbol: str, asset: str, from_ts: int, to_ts: int) -> list[dict]:
    """
    Fetches 1-minute OHLCV candles for a perpetual futures contract over the 24h window.
    Returns structured record dicts matching the futures schema.
    """
    print(f"[*] Fetching Perpetual Futures candles for {asset} ({symbol})...")
    data = fetch_contract_candles(symbol, from_ts, to_ts, resolution="1")
    timestamps = data.get("t", []) if data else []
    records = []

    for i in range(len(timestamps)):
        bar_time = timestamps[i]
        readable_ist = datetime.fromtimestamp(bar_time, IST).strftime("%Y-%m-%d %H:%M:%S")
        record = {
            "timestamp": int(bar_time),
            "datetime_ist": readable_ist,
            "symbol": symbol,
            "asset": asset,
            "open": float(data["o"][i]),
            "high": float(data["h"][i]),
            "low": float(data["l"][i]),
            "close": float(data["c"][i]),
            "volume": float(data["v"][i])
        }
        records.append(record)

    print(f"[✓] Received {len(records)} 1-minute candles for {symbol}.")
    return records

def fetch_all_expiry_options_symbols(underlying: str, date_tag: str) -> list[str]:
    """
    Discovers all candidate option contracts for an underlying:
    1. All LIVE contracts (covering all future expiries: 0-DTE, 1-DTE, weekly, monthly).
    2. All EXPIRED contracts that expired on the target date (date_tag).
    """
    matched = set()

    # 1. Fetch all live options
    live_url = (
        f"{DELTA_BASE_URL}/products"
        f"?contract_types=call_options,put_options"
        f"&states=live"
        f"&underlying_asset_symbols={underlying}"
    )
    live_res = _safe_get_request(live_url)
    if live_res and "result" in live_res:
        for p in live_res["result"]:
            sym = p.get("symbol")
            if sym:
                matched.add(sym)

    # 2. Fetch contracts that expired on target date
    expired_url = (
        f"{DELTA_BASE_URL}/products"
        f"?contract_types=call_options,put_options"
        f"&states=expired"
        f"&underlying_asset_symbols={underlying}"
    )
    exp_res = _safe_get_request(expired_url)
    if exp_res and "result" in exp_res:
        for p in exp_res["result"]:
            sym = p.get("symbol", "")
            if date_tag in sym:
                matched.add(sym)

    return sorted(list(matched))

def fetch_options_dataset(underlying: str, date_tag: str, from_ts: int, to_ts: int) -> list[dict]:
    """
    Fetches all active 1-minute candles for all candidate options across all expiries.
    """
    symbols = fetch_all_expiry_options_symbols(underlying, date_tag)
    print(f"[*] Found {len(symbols)} candidate option contracts for {underlying} (All Expiries).")
    
    all_records = []
    active_count = 0

    for idx, sym in enumerate(symbols, start=1):
        opt_type, base_asset, strike, expiry_date = parse_option_symbol(sym)
        data = fetch_contract_candles(sym, from_ts, to_ts, resolution="1")

        timestamps = data.get("t", []) if data else []
        candles_len = len(timestamps)

        if candles_len > 0:
            active_count += 1
            print(f"  [{idx:03d}/{len(symbols):03d}] [ACTIVE] {sym:<25} ({expiry_date}) -> {candles_len} candles")

            for i in range(candles_len):
                bar_time = timestamps[i]
                readable_ist = datetime.fromtimestamp(bar_time, IST).strftime("%Y-%m-%d %H:%M:%S")

                record = {
                    "timestamp": int(bar_time),
                    "datetime_ist": readable_ist,
                    "symbol": sym,
                    "underlying": underlying,
                    "expiry_date": expiry_date,
                    "type": opt_type,
                    "strike": float(strike),
                    "open": float(data["o"][i]),
                    "high": float(data["h"][i]),
                    "low": float(data["l"][i]),
                    "close": float(data["c"][i]),
                    "volume": float(data["v"][i])
                }
                all_records.append(record)

        time.sleep(RATE_LIMIT_SLEEP)

    print(f"[✓] {underlying} Options Scan Complete: {active_count}/{len(symbols)} active contracts, {len(all_records)} total candles.")
    return all_records
