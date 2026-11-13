import os
import tempfile
from datetime import datetime
from src.config import IST
from src.delta_client import parse_option_symbol, get_epoch_range
from main import get_default_target_date
from src.storage import (
    save_futures_records_to_parquet,
    save_options_records_to_parquet
)
from src.auditor import audit_parquet_file
from src.telegram_notifier import build_telegram_report
from src.gdrive_uploader import resolve_target_folder
from app import compute_next_run

def test_parse_option_symbol_standard():
    opt_type, underlying, strike, expiry_date = parse_option_symbol("C-BTC-72600-091126")
    assert opt_type == "CE"
    assert underlying == "BTC"
    assert strike == 72600
    assert expiry_date == "2026-11-09"

    opt_type, underlying, strike, expiry_date = parse_option_symbol("P-ETH-3200-141126")
    assert opt_type == "PE"
    assert underlying == "ETH"
    assert strike == 3200
    assert expiry_date == "2026-11-14"

def test_parse_option_symbol_float_strike():
    opt_type, underlying, strike, expiry_date = parse_option_symbol("C-SOL-145.5-141126")
    assert opt_type == "CE"
    assert underlying == "SOL"
    assert strike == 145.5
    assert expiry_date == "2026-11-14"

def test_parse_option_symbol_invalid():
    opt_type, underlying, strike, expiry_date = parse_option_symbol("C-BTC-BADSTRIKE-091126")
    assert opt_type == "CE"
    assert underlying == "BTC"
    assert strike == 0.0
    assert expiry_date == "2026-11-09"

    opt_type, underlying, strike, expiry_date = parse_option_symbol("INVALID_SYMBOL")
    assert opt_type == "UNKNOWN"
    assert strike == 0.0
    assert expiry_date == "UNKNOWN"

def test_get_epoch_range_24_hours():
    date_str = "2026-11-09"
    from_ts, to_ts = get_epoch_range(date_str)
    
    # 24 hours must be exactly 86400 seconds
    assert to_ts - from_ts == 86400

    # End timestamp must correspond to 17:30:00 IST on expiry date
    dt_end = datetime.fromtimestamp(to_ts, IST)
    assert dt_end.strftime("%Y-%m-%d") == date_str
    assert dt_end.hour == 17
    assert dt_end.minute == 30
    assert dt_end.second == 0

def test_dynamic_default_target_date():
    today_ist = datetime.now(IST).strftime("%Y-%m-%d")
    assert get_default_target_date() == today_ist
    assert len(today_ist.split("-")) == 3

def test_futures_storage_and_audit():
    sample_records = [
        {
            "timestamp": 1794484800,
            "datetime_ist": "2026-11-12 17:30:00",
            "symbol": "BTCUSD",
            "asset": "BTC",
            "open": 91200.0,
            "high": 91350.5,
            "low": 91100.0,
            "close": 91300.0,
            "volume": 150.2
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = os.path.join(tmpdir, "BTC_futures_test.parquet")
        saved = save_futures_records_to_parquet(sample_records, tmp_file)
        assert saved is True
        assert os.path.exists(tmp_file)

        audit_res = audit_parquet_file(tmp_file, expected_type="futures")
        assert audit_res["is_valid"] is True
        assert audit_res["total_rows"] == 1
        assert audit_res["unique_symbols"] == 1
        assert audit_res["null_counts"]["open"] == 0

def test_options_storage_and_audit():
    sample_records = [
        {
            "timestamp": 1794484800,
            "datetime_ist": "2026-11-12 17:30:00",
            "symbol": "C-BTC-95000-141126",
            "underlying": "BTC",
            "expiry_date": "2026-11-14",
            "type": "CE",
            "strike": 95000.0,
            "open": 450.0,
            "high": 480.0,
            "low": 420.0,
            "close": 460.0,
            "volume": 22.0
        },
        {
            "timestamp": 1794484860,
            "datetime_ist": "2026-11-12 17:31:00",
            "symbol": "P-BTC-90000-201126",
            "underlying": "BTC",
            "expiry_date": "2026-11-20",
            "type": "PE",
            "strike": 90000.0,
            "open": 850.0,
            "high": 870.0,
            "low": 830.0,
            "close": 840.0,
            "volume": 12.0
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = os.path.join(tmpdir, "BTC_options_test.parquet")
        saved = save_options_records_to_parquet(sample_records, tmp_file)
        assert saved is True
        assert os.path.exists(tmp_file)

        audit_res = audit_parquet_file(tmp_file, expected_type="options")
        assert audit_res["is_valid"] is True
        assert audit_res["total_rows"] == 2
        assert audit_res["unique_symbols"] == 2
        assert audit_res["unique_expiries"] == 2
        assert audit_res["null_counts"]["expiry_date"] == 0

def test_telegram_report_builder():
    sample_summary = {
        "target_date": "2026-11-13",
        "duration_sec": 42.5,
        "overall_status": "SUCCESS",
        "futures": [
            {"asset": "BTC", "symbol": "BTCUSD", "rows": 1441, "size_kb": 12.5, "drive_verified": True}
        ],
        "options": [
            {"asset": "BTC", "underlying": "BTC", "contracts": 582, "expiries": 14, "rows": 78000, "size_kb": 650.0, "drive_verified": True}
        ]
    }
    html_msg = build_telegram_report(sample_summary)
    assert "DELTA DATA PRESERVER v2.0 - RUN REPORT" in html_msg
    assert "BTCUSD" in html_msg or "BTC:" in html_msg
    assert "ALL VERIFIED" in html_msg

def test_gdrive_subfolder_resolution_root():
    # If subfolder_path is None or empty, returns root_id unchanged
    assert resolve_target_folder("mock_token", "root_123", None) == "root_123"
    assert resolve_target_folder("mock_token", "root_123", "") == "root_123"

def test_app_compute_next_run():
    dt_morning = datetime(2026, 11, 14, 10, 0, 0, tzinfo=IST)
    next_run = compute_next_run(dt_morning)
    assert "2026-11-14 18:15:00 IST" == next_run

    dt_evening = datetime(2026, 11, 14, 19, 0, 0, tzinfo=IST)
    next_run_next_day = compute_next_run(dt_evening)
    assert "2026-11-15 18:15:00 IST" == next_run_next_day
