import sys
import time
import os
from datetime import datetime
from src.config import (
    load_env,
    IST,
    FUTURES_DATA_DIR,
    OPTIONS_DATA_DIR,
    FUTURES_ASSETS,
    OPTIONS_ASSETS
)
from src.delta_client import (
    get_epoch_range,
    fetch_perpetual_candles,
    fetch_options_dataset
)
from src.storage import (
    save_futures_records_to_parquet,
    save_options_records_to_parquet
)
from src.auditor import audit_parquet_file, format_audit_log
from src.gdrive_uploader import upload_file_to_drive
from src.telegram_notifier import send_pipeline_report, send_failure_alert

# Auto-load local environment if present
load_env()

def get_default_target_date() -> str:
    """Returns today's date in IST timezone (YYYY-MM-DD)."""
    return datetime.now(IST).strftime("%Y-%m-%d")

def run_pipeline(target_date: str = None, run_futures: bool = True, run_options: bool = True, specific_asset: str = None):
    start_time = time.time()

    if not target_date:
        target_date = get_default_target_date()

    dt = datetime.strptime(target_date, "%Y-%m-%d")
    date_tag = dt.strftime("%d%m%y")
    from_ts, to_ts = get_epoch_range(target_date)

    start_readable = datetime.fromtimestamp(from_ts, IST).strftime("%Y-%m-%d %H:%M:%S IST")
    end_readable = datetime.fromtimestamp(to_ts, IST).strftime("%Y-%m-%d %H:%M:%S IST")

    print(f"\n{'='*70}")
    print(f"DELTA DATA PRESERVER v2.0 - MULTI-ASSET & ALL-EXPIRIES PIPELINE")
    print(f"Target Expiry Date : {target_date} (Tag: {date_tag})")
    print(f"24-Hour IST Window : {start_readable} ({from_ts}) -> {end_readable} ({to_ts})")
    print(f"{'='*70}\n")

    summary = {
        "target_date": target_date,
        "duration_sec": 0.0,
        "overall_status": "SUCCESS",
        "futures": [],
        "options": []
    }

    pipeline_errors = []
    folder_id = os.getenv("GDRIVE_FOLDER_ID")

    # ==========================================
    # STAGE 1: PERPETUAL FUTURES (5 ASSETS)
    # ==========================================
    if run_futures:
        print(f"\n--- [STAGE 1] PERPETUAL FUTURES PIPELINE (5 ASSETS) ---")
        futures_to_run = (
            {specific_asset: FUTURES_ASSETS[specific_asset]} 
            if specific_asset and specific_asset in FUTURES_ASSETS 
            else FUTURES_ASSETS
        )

        for asset, symbol in futures_to_run.items():
            try:
                records = fetch_perpetual_candles(symbol, asset, from_ts, to_ts)
                if not records:
                    print(f"[!] Warning: No candle data received for {asset} ({symbol}).")
                    continue

                output_file = os.path.join(FUTURES_DATA_DIR, asset, f"{asset}_futures_{target_date}.parquet")
                saved = save_futures_records_to_parquet(records, output_file)
                if not saved:
                    pipeline_errors.append(f"Failed to write Parquet for {asset} futures.")
                    continue

                # Run automated audit
                audit_res = audit_parquet_file(output_file, expected_type="futures")
                print(format_audit_log(audit_res))
                if not audit_res.get("is_valid"):
                    err = f"Audit failed for {asset} futures: {audit_res.get('errors')}"
                    pipeline_errors.append(err)
                    continue

                # Upload to Google Drive and verify under Crypto/Futures
                upload_res = upload_file_to_drive(output_file, folder_id, subfolder_path="Crypto/Futures")
                drive_verified = upload_res.get("success", False) and upload_res.get("size_bytes", 0) > 0

                if not drive_verified:
                    err = f"Google Drive verification failed for {asset} futures: {upload_res.get('error')}"
                    pipeline_errors.append(err)

                summary["futures"].append({
                    "asset": asset,
                    "symbol": symbol,
                    "rows": audit_res.get("total_rows", 0),
                    "size_kb": audit_res.get("file_size_kb", 0.0),
                    "drive_verified": drive_verified,
                    "drive_file_id": upload_res.get("file_id")
                })

            except Exception as e:
                err = f"Unexpected exception in futures pipeline for {asset}: {e}"
                print(f"[CRITICAL] {err}")
                pipeline_errors.append(err)

    # ==========================================
    # STAGE 2: OPTIONS (ALL EXPIRIES - 3 ASSETS)
    # ==========================================
    if run_options:
        print(f"\n--- [STAGE 2] OPTIONS ALL-EXPIRIES PIPELINE (3 ASSETS) ---")
        options_to_run = (
            {specific_asset: OPTIONS_ASSETS[specific_asset]} 
            if specific_asset and specific_asset in OPTIONS_ASSETS 
            else OPTIONS_ASSETS
        )

        for asset, underlying in options_to_run.items():
            try:
                records = fetch_options_dataset(underlying, date_tag, from_ts, to_ts)
                if not records:
                    print(f"[!] Warning: No options candle data found for {asset} ({underlying}).")
                    continue

                output_file = os.path.join(OPTIONS_DATA_DIR, asset, f"{asset}_options_{target_date}.parquet")
                saved = save_options_records_to_parquet(records, output_file)
                if not saved:
                    pipeline_errors.append(f"Failed to write Parquet for {asset} options.")
                    continue

                # Run automated audit
                audit_res = audit_parquet_file(output_file, expected_type="options")
                print(format_audit_log(audit_res))
                if not audit_res.get("is_valid"):
                    err = f"Audit failed for {asset} options: {audit_res.get('errors')}"
                    pipeline_errors.append(err)
                    continue

                # Upload to Google Drive and verify under Crypto/Options
                upload_res = upload_file_to_drive(output_file, folder_id, subfolder_path="Crypto/Options")
                drive_verified = upload_res.get("success", False) and upload_res.get("size_bytes", 0) > 0

                if not drive_verified:
                    err = f"Google Drive verification failed for {asset} options: {upload_res.get('error')}"
                    pipeline_errors.append(err)

                summary["options"].append({
                    "asset": asset,
                    "underlying": underlying,
                    "contracts": audit_res.get("unique_symbols", 0),
                    "expiries": audit_res.get("unique_expiries", 0),
                    "rows": audit_res.get("total_rows", 0),
                    "size_kb": audit_res.get("file_size_kb", 0.0),
                    "drive_verified": drive_verified,
                    "drive_file_id": upload_res.get("file_id")
                })

            except Exception as e:
                err = f"Unexpected exception in options pipeline for {asset}: {e}"
                print(f"[CRITICAL] {err}")
                pipeline_errors.append(err)

    # ==========================================
    # STAGE 3: TELEGRAM NOTIFICATION & FINALIZE
    # ==========================================
    duration = time.time() - start_time
    summary["duration_sec"] = duration

    if pipeline_errors:
        summary["overall_status"] = "FAILED"
        print(f"\n[CRITICAL] Pipeline encountered {len(pipeline_errors)} error(s):")
        for e in pipeline_errors:
            print(f"  - {e}")
        send_failure_alert("\n".join(pipeline_errors), target_date)
    else:
        summary["overall_status"] = "SUCCESS"
        print(f"\n[✓] ALL STAGES VERIFIED & SUCCESSFULLY SAVED TO GOOGLE DRIVE!")

    send_pipeline_report(summary)

    print(f"\n{'='*70}")
    print(f"PIPELINE RUN COMPLETED in {duration:.2f}s | STATUS: {summary['overall_status']}")
    print(f"{'='*70}\n")

    if summary["overall_status"] != "SUCCESS":
        sys.exit(1)

if __name__ == "__main__":
    date_input = None
    run_fut = True
    run_opt = True
    asset_filter = None

    args = sys.argv[1:]
    for arg in args:
        if arg == "--futures-only":
            run_opt = False
        elif arg == "--options-only":
            run_fut = False
        elif arg.startswith("--asset="):
            asset_filter = arg.split("=", 1)[1].upper()
        elif not arg.startswith("--") and date_input is None:
            date_input = arg

    run_pipeline(
        target_date=date_input,
        run_futures=run_fut,
        run_options=run_opt,
        specific_asset=asset_filter
    )
