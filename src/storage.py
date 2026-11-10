import os
import json
from src.config import OPTIONS_DATA_DIR

def save_records_to_parquet(records: list[dict], output_filepath: str) -> bool:
    """
    Saves list of records into a single snappy-compressed Parquet file.
    Creates parent directories automatically if not existing.
    """
    if not records:
        print("[!] No records to save.")
        return False

    os.makedirs(os.path.dirname(output_filepath), exist_ok=True)

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq

        schema = pa.schema([
            ('timestamp', pa.int64()),
            ('datetime_ist', pa.string()),
            ('symbol', pa.string()),
            ('underlying', pa.string()),
            ('strike', pa.int32()),
            ('type', pa.string()),
            ('open', pa.float32()),
            ('high', pa.float32()),
            ('low', pa.float32()),
            ('close', pa.float32()),
            ('volume', pa.float32())
        ])

        table_dict = {field.name: [row[field.name] for row in records] for field in schema}
        table = pa.Table.from_pydict(table_dict, schema=schema)
        pq.write_table(table, output_filepath, compression="snappy")
        print(f"[✓] Successfully wrote {len(records)} candles to Parquet: {output_filepath}")
        return True

    except ImportError:
        try:
            import pandas as pd
            df = pd.DataFrame(records)
            df.to_parquet(output_filepath, engine="auto", compression="snappy", index=False)
            print(f"[✓] Saved {len(records)} candles using Pandas Parquet engine: {output_filepath}")
            return True
        except ImportError:
            fallback_jsonl = output_filepath.replace(".parquet", ".jsonl")
            with open(fallback_jsonl, "w", encoding="utf-8") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")
            print(f"[!] PyArrow/Pandas not installed. Fallback saved to: {fallback_jsonl}")
            return True
    except Exception as e:
        print(f"[!] Error writing Parquet file: {e}")
        return False

def verify_parquet_file(filepath: str):
    """
    Reads and prints basic summary of the preserved Parquet file.
    """
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}")
        return

    try:
        import pyarrow.parquet as pq
        table = pq.read_table(filepath)
        print("\n--- PARQUET VERIFICATION REPORT ---")
        print(f"File Path      : {filepath}")
        print(f"Total Rows     : {table.num_rows}")
        print(f"Total Columns  : {table.num_columns}")
        print(f"Schema Columns : {table.column_names}")
        print(f"File Size      : {os.path.getsize(filepath) / 1024:.2f} KB")
        print("-----------------------------------\n")
    except ImportError:
        import pandas as pd
        df = pd.read_parquet(filepath)
        print("\n--- PARQUET VERIFICATION REPORT (Pandas) ---")
        print(f"File Path  : {filepath}")
        print(f"Total Rows : {len(df)}")
        print(f"File Size  : {os.path.getsize(filepath) / 1024:.2f} KB")
        print("--------------------------------------------\n")