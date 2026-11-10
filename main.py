import sys
import time
import os
from datetime import datetime
from src.config import IST, OPTIONS_DATA_DIR, RATE_LIMIT_SLEEP, DEFAULT_GDRIVE_FOLDER_ID
from src.delta_client import (
    get_epoch_range,
    parse_option_symbol,
    fetch_expired_symbols,
    fetch_contract_candles
)
from src.storage import save_records_to_parquet, verify_parquet_file
from src.gdrive_uploader import upload_file_to_drive

def run_preserver(target_date: str = "2026-11-09", underlying: str = "BTC"):
    dt = datetime.strptime(target_date, "%Y-%m-%d")
    date_tag = dt.strftime("%d%m%y")
    from_ts, to_ts = get_epoch_range(target_date)

    start_readable = datetime.fromtimestamp(from_ts, IST).strftime("%Y-%m-%d %H:%M:%S IST")
    end_readable = datetime.fromtimestamp(to_ts, IST).strftime("%Y-%m-%d %H:%M:%S IST")

    print(f"\n{'='*60}")
    print(f"DELTA DATA PRESERVER - PIPELINE RUN")
    print(f"Underlying   : {underlying}")
    print(f"Expiry Date  : {target_date} (Tag: {date_tag})")
    print(f"Window Start : {start_readable} ({from_ts})")
    print(f"Window End   : {end_readable} ({to_ts})")
    print(f"{'='*60}\n")

    symbols = fetch_expired_symbols(date_tag, underlying=underlying)
    print(f"[*] Found {len(symbols)} candidate expired contracts.")

    if not symbols:
        print("[!] No contracts to process. Exiting.")
        return

    all_records = []
    active_count = 0

    print("[*] Streaming and auditing contract candles (24-Hour Cycle)...")
    for idx, sym in enumerate(symbols, start=1):
        opt_type, base_asset, strike = parse_option_symbol(sym)
        data = fetch_contract_candles(sym, from_ts, to_ts)

        timestamps = data.get("t", []) if data else []
        candles_len = len(timestamps)

        if candles_len > 0:
            active_count += 1
            print(f"  [{idx:02d}/{len(symbols):02d}] [ACTIVE] {sym:<25} -> {candles_len} candles")

            for i in range(candles_len):
                bar_time = timestamps[i]
                readable_ist = datetime.fromtimestamp(bar_time, IST).strftime("%Y-%m-%d %H:%M:%S")

                record = {
                    "timestamp": bar_time,
                    "datetime_ist": readable_ist,
                    "symbol": sym,
                    "underlying": base_asset,
                    "strike": strike,
                    "type": opt_type,
                    "open": float(data["o"][i]),
                    "high": float(data["h"][i]),
                    "low": float(data["l"][i]),
                    "close": float(data["c"][i]),
                    "volume": float(data["v"][i])
                }
                all_records.append(record)
        else:
            print(f"  [{idx:02d}/{len(symbols):02d}] [EMPTY]  {sym:<25} -> 0 candles")

        time.sleep(RATE_LIMIT_SLEEP)

    print(f"\n[*] Processing Complete:")
    print(f"    - Scanned Contracts : {len(symbols)}")
    print(f"    - Active Contracts  : {active_count}")
    print(f"    - Total Data Points : {len(all_records)}")

    if all_records:
        output_file = os.path.join(OPTIONS_DATA_DIR, underlying, f"{underlying}_options_{target_date}.parquet")
        success = save_records_to_parquet(all_records, output_file)
        if success:
            verify_parquet_file(output_file)
            
            # --- AUTO UPLOAD TO GOOGLE DRIVE VIA OAUTH ---
            folder_id = os.getenv("GDRIVE_FOLDER_ID", DEFAULT_GDRIVE_FOLDER_ID)
            upload_file_to_drive(output_file, folder_id)
    else:
        print("[!] Zero trades found across all contracts. No file written.")

if __name__ == "__main__":
    date_arg = sys.argv[1] if len(sys.argv) > 1 else "2026-11-09"
    run_preserver(target_date=date_arg, underlying="BTC")