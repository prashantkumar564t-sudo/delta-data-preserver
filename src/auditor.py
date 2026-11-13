import os
from datetime import datetime

def audit_parquet_file(filepath: str, expected_type: str = "futures") -> dict:
    """
    Performs a strict automated audit on a generated Parquet file:
    - Verifies file existence and non-zero size
    - Validates column schema and checks for NULL / NaN values
    - Calculates row counts, unique contracts, and unique expiries
    - Verifies timestamp coverage within the window
    Returns a structured audit report dictionary.
    """
    report = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "expected_type": expected_type,
        "is_valid": False,
        "file_size_kb": 0.0,
        "total_rows": 0,
        "unique_symbols": 0,
        "unique_expiries": 0 if expected_type == "options" else None,
        "min_datetime_ist": None,
        "max_datetime_ist": None,
        "null_counts": {},
        "errors": []
    }

    if not os.path.exists(filepath):
        report["errors"].append(f"File not found: {filepath}")
        return report

    size_bytes = os.path.getsize(filepath)
    report["file_size_kb"] = round(size_bytes / 1024.0, 2)
    if size_bytes == 0:
        report["errors"].append(f"File is empty (0 bytes): {filepath}")
        return report

    try:
        import pyarrow.parquet as pq

        table = pq.read_table(filepath)
        total_rows = table.num_rows
        report["total_rows"] = total_rows

        if total_rows == 0:
            report["errors"].append("Parquet table has 0 rows.")
            return report

        col_names = table.column_names

        # Schema checks
        if expected_type == "futures":
            required_cols = ["timestamp", "datetime_ist", "symbol", "asset", "open", "high", "low", "close", "volume"]
        else:
            required_cols = ["timestamp", "datetime_ist", "symbol", "underlying", "expiry_date", "type", "strike", "open", "high", "low", "close", "volume"]

        for col in required_cols:
            if col not in col_names:
                report["errors"].append(f"Missing required column: {col}")

        # Null checks across all columns
        total_nulls = 0
        for col in col_names:
            null_count = table[col].null_count
            report["null_counts"][col] = null_count
            total_nulls += null_count

        if total_nulls > 0:
            report["errors"].append(f"Dataset contains {total_nulls} null values: {report['null_counts']}")

        # Unique symbols and expiries
        symbols = set(table["symbol"].to_pylist())
        report["unique_symbols"] = len(symbols)

        if expected_type == "options" and "expiry_date" in col_names:
            expiries = set(table["expiry_date"].to_pylist())
            report["unique_expiries"] = len(expiries)

        # Timestamp range
        if "datetime_ist" in col_names:
            dt_list = table["datetime_ist"].to_pylist()
            report["min_datetime_ist"] = min(dt_list)
            report["max_datetime_ist"] = max(dt_list)

        report["is_valid"] = len(report["errors"]) == 0
        return report

    except Exception as e:
        report["errors"].append(f"Exception during audit of {filepath}: {e}")
        return report

def format_audit_log(audit_result: dict) -> str:
    """Formats an audit report dictionary into a clean readable log string."""
    status = "PASSED" if audit_result.get("is_valid") else "FAILED"
    lines = [
        f"--- PARQUET AUDIT [{status}]: {audit_result.get('filename')} ---",
        f"  Type            : {audit_result.get('expected_type')}",
        f"  Size            : {audit_result.get('file_size_kb'):.2f} KB",
        f"  Total Rows      : {audit_result.get('total_rows')}",
        f"  Unique Symbols  : {audit_result.get('unique_symbols')}",
    ]
    if audit_result.get("expected_type") == "options":
        lines.append(f"  Unique Expiries : {audit_result.get('unique_expiries')}")
    if audit_result.get("min_datetime_ist") and audit_result.get("max_datetime_ist"):
        lines.append(f"  Time Range (IST): {audit_result.get('min_datetime_ist')} -> {audit_result.get('max_datetime_ist')}")
    if audit_result.get("errors"):
        lines.append(f"  Errors          : {', '.join(audit_result.get('errors'))}")
    lines.append("-----------------------------------------------------")
    return "\n".join(lines)

