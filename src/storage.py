import os
import json

def _write_table_snappy(records: list[dict], schema, output_filepath: str) -> bool:
    """Internal helper to write records with a specified PyArrow schema."""
    if not records:
        print(f"[!] No records to save for {output_filepath}.")
        return False

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        table_dict = {field.name: [row.get(field.name) for row in records] for field in schema}
        table = pa.Table.from_pydict(table_dict, schema=schema)
        pq.write_table(table, output_filepath, compression="snappy")
        print(f"[✓] Successfully wrote {len(records)} records to Parquet: {output_filepath}")
        return True

    except ImportError:
        try:
            import pandas as pd
            df = pd.DataFrame(records)
            df.to_parquet(output_filepath, engine="auto", compression="snappy", index=False)
            print(f"[✓] Saved {len(records)} records using Pandas Parquet engine: {output_filepath}")
            return True
        except ImportError:
            fallback_jsonl = output_filepath.replace(".parquet", ".jsonl")
            with open(fallback_jsonl, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            print(f"[!] PyArrow/Pandas not installed. Fallback saved to: {fallback_jsonl}")
            return True
    except Exception as e:
        print(f"[!] Error writing Parquet file {output_filepath}: {e}")
        return False

def save_futures_records_to_parquet(records: list[dict], output_filepath: str) -> bool:
    """
    Saves Perpetual Futures records with strict schema:
    [timestamp, datetime_ist, symbol, asset, open, high, low, close, volume]
    """
    try:
        import pyarrow as pa
        schema = pa.schema([
            ('timestamp', pa.int64()),
            ('datetime_ist', pa.string()),
            ('symbol', pa.string()),
            ('asset', pa.string()),
            ('open', pa.float32()),
            ('high', pa.float32()),
            ('low', pa.float32()),
            ('close', pa.float32()),
            ('volume', pa.float32())
        ])
    except ImportError:
        schema = None

    return _write_table_snappy(records, schema, output_filepath)

def save_options_records_to_parquet(records: list[dict], output_filepath: str) -> bool:
    """
    Saves All-Expiries Options records with strict schema:
    [timestamp, datetime_ist, symbol, underlying, expiry_date, type, strike, open, high, low, close, volume]
    """
    try:
        import pyarrow as pa
        schema = pa.schema([
            ('timestamp', pa.int64()),
            ('datetime_ist', pa.string()),
            ('symbol', pa.string()),
            ('underlying', pa.string()),
            ('expiry_date', pa.string()),
            ('type', pa.string()),
            ('strike', pa.float32()),
            ('open', pa.float32()),
            ('high', pa.float32()),
            ('low', pa.float32()),
            ('close', pa.float32()),
            ('volume', pa.float32())
        ])
    except ImportError:
        schema = None

    return _write_table_snappy(records, schema, output_filepath)

def save_records_to_parquet(records: list[dict], output_filepath: str) -> bool:
    """Backwards-compatible options saver."""
    return save_options_records_to_parquet(records, output_filepath)

def verify_parquet_file(filepath: str) -> dict:
    """
    Reads and prints basic summary of the preserved Parquet file.
    Returns basic metrics dict.
    """
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return {"exists": False}

    file_size_kb = os.path.getsize(filepath) / 1024.0

    try:
        import pyarrow.parquet as pq
        table = pq.read_table(filepath)
        print("\n--- PARQUET VERIFICATION REPORT ---")
        print(f"File Path      : {filepath}")
        print(f"Total Rows     : {table.num_rows}")
        print(f"Total Columns  : {table.num_columns}")
        print(f"Schema Columns : {table.column_names}")
        print(f"File Size      : {file_size_kb:.2f} KB")
        print("-----------------------------------\n")
        return {
            "exists": True,
            "rows": table.num_rows,
            "columns": table.num_columns,
            "column_names": table.column_names,
            "size_kb": file_size_kb
        }
    except Exception as e:
        print(f"[!] Verification error on {filepath}: {e}")
        return {"exists": True, "error": str(e), "size_kb": file_size_kb}
