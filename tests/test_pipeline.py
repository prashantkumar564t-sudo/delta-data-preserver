import os
import tempfile
from datetime import datetime, timezone, timedelta
from src.config import IST
from src.delta_client import parse_option_symbol, get_epoch_range
from main import get_default_target_date
from src.storage import save_records_to_parquet, verify_parquet_file

def test_parse_option_symbol_standard():
    opt_type, underlying, strike = parse_option_symbol("C-BTC-72600-091126")
    assert opt_type == "CE"
    assert underlying == "BTC"
    assert strike == 72600

    opt_type, underlying, strike = parse_option_symbol("P-ETH-3200-091126")
    assert opt_type == "PE"
    assert underlying == "ETH"
    assert strike == 3200

def test_parse_option_symbol_float_strike():
    # Tests safe conversion of decimal strikes (e.g. 145.5 -> 145)
    opt_type, underlying, strike = parse_option_symbol("C-SOL-145.5-091126")
    assert opt_type == "CE"
    assert underlying == "SOL"
    assert strike == 145

def test_parse_option_symbol_invalid():
    opt_type, underlying, strike = parse_option_symbol("C-BTC-BADSTRIKE-091126")
    assert opt_type == "CE"
    assert underlying == "BTC"
    assert strike == 0

    opt_type, underlying, strike = parse_option_symbol("INVALID_SYMBOL")
    assert opt_type == "UNKNOWN"
    assert strike == 0

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
    # Verify YYYY-MM-DD pattern
    assert len(today_ist.split("-")) == 3
    assert len(today_ist.split("-")[0]) == 4

def test_parquet_storage_roundtrip():
    sample_records = [
        {
            "timestamp": 1794226200,
            "datetime_ist": "2026-11-09 17:30:00",
            "symbol": "C-BTC-72000-091126",
            "underlying": "BTC",
            "strike": 72000,
            "type": "CE",
            "open": 105.5,
            "high": 110.0,
            "low": 102.0,
            "close": 108.0,
            "volume": 25.5
        }
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_file = os.path.join(tmpdir, "test.parquet")
        success = save_records_to_parquet(sample_records, tmp_file)
        assert success is True
        assert os.path.exists(tmp_file)
        
        import pyarrow.parquet as pq
        table = pq.read_table(tmp_file)
        assert table.num_rows == 1
        assert table.num_columns == 11
        assert "timestamp" in table.column_names
        assert "strike" in table.column_names
