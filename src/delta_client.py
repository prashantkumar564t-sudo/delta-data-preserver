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

def parse_option_symbol(symbol: str) -> tuple[str, str, int]:
    """
    Parses symbol format like 'C-BTC-72600-091126' or 'P-BTC-72600-091126'
    Returns: (option_type ['CE'/'PE'], underlying, strike_price)
    """
    parts = symbol.split("-")
    if len(parts) >= 4:
        opt_type = "CE" if parts[0].upper() == "C" else "PE"
        underlying = parts[1]
        try:
            strike = int(float(parts[2]))
        except (ValueError, TypeError):
            strike = 0
        return opt_type, underlying, strike
    return "UNKNOWN", "BTC", 0

def _safe_get_request(url: str) -> dict | None:
    """Internal helper to make resilient HTTP GET requests with retries."""
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

def fetch_expired_symbols(date_tag: str, underlying: str = "BTC") -> list[str]:
    """
    Fetches all expired option contracts for given date tag (DDMMYY) and asset.
    Example: date_tag='091126', underlying='BTC'
    """
    url = (
        f"{DELTA_BASE_URL}/products"
        f"?contract_types=call_options,put_options"
        f"&states=expired"
        f"&underlying_asset_symbols={underlying}"
    )
    payload = _safe_get_request(url)
    if not payload:
        return []
    
    results = payload.get("result", [])
    matched_symbols = [
        item["symbol"] for item in results 
        if date_tag in item.get("symbol", "")
    ]
    return matched_symbols

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