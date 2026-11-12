# Delta Data Preserver 🚀

Automated, resilient daily ETL pipeline designed to preserve 1-minute OHLCV candle data for expired Delta Exchange India options contracts into snappy-compressed Parquet files, synchronized directly to Google Drive via OAuth 2.0 with zero external cloud SDK dependencies.

---

## 📌 Project Overview

Delta Exchange options contracts expire daily at **17:30 IST**. This service runs once daily at **18:00 IST (12:30 UTC)** to:
1. Scan all expired Call (`CE`) and Put (`PE`) option contracts settled on the target date.
2. Stream 1-minute historical OHLCV candles covering the complete 24-hour cycle (Previous Day 17:30 IST -> Expiry Day 17:30 IST).
3. Validate and serialize candle records into high-efficiency snappy-compressed Parquet archives using PyArrow.
4. Upload the dataset directly to Google Drive using standard HTTP multipart REST API requests authenticated with OAuth 2.0 refresh tokens.

---

## 📁 Repository Structure

```text
delta-data-preserver/
├── .github/
│   └── workflows/
│       └── daily_preserver.yml     # GitHub Actions workflow (daily cron + workflow_dispatch)
├── src/
│   ├── __init__.py
│   ├── config.py                   # Zero-dependency .env loader, timeouts & IST timezone
│   ├── delta_client.py             # Delta Exchange REST API client (Products & OHLCV candles)
│   ├── gdrive_uploader.py          # Zero-dependency Google OAuth multipart Drive uploader
│   └── storage.py                  # PyArrow snappy Parquet writer & schema validator
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py            # Unit test suite (symbols, float strikes, epoch windows, dates)
├── .env.example                    # Template for environment variables
├── .gitignore                      # Git ignore rules for data, secrets, caches, and logs
├── get_token.py                    # Local developer tool for Google OAuth token generation
├── main.py                         # Production CLI entrypoint & pipeline orchestrator
├── requirements.txt                # Lightweight production dependencies (pyarrow, pytest)
└── README.md                       # Architecture & deployment documentation
```

---

## 🔐 Environment Variables

The pipeline reads credentials strictly from environment variables (or a local `.env` file for development). 

| Variable | Description | Required |
| :--- | :--- | :---: |
| `GDRIVE_CLIENT_ID` | Google Cloud OAuth 2.0 Client ID | **Yes** |
| `GDRIVE_CLIENT_SECRET` | Google Cloud OAuth 2.0 Client Secret | **Yes** |
| `GDRIVE_REFRESH_TOKEN` | Long-lived OAuth 2.0 Refresh Token (with `drive.file` scope) | **Yes** |
| `GDRIVE_FOLDER_ID` | Target Google Drive Folder ID for uploads | **Yes** |

---

## 💻 Local Setup & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file in the project root:
```ini
GDRIVE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GDRIVE_CLIENT_SECRET="your-client-secret"
GDRIVE_REFRESH_TOKEN="your-refresh-token"
GDRIVE_FOLDER_ID="your-target-folder-id"
```

### 3. Generate OAuth Refresh Token (First-Time Setup)
```bash
python get_token.py
```
*Follow the browser OAuth consent flow, then copy the emitted refresh token to your `.env`.*

### 4. Run the Pipeline
```bash
# Run for today's expiry (automatic current IST date)
python main.py

# Or backfill a specific expiry date
python main.py 2026-11-09
```

---

## 🧪 Testing

Run the automated test suite with `pytest`:
```bash
python -m pytest tests/ -v
```

---

## ☁️ Deployment & Scheduling

### Voroa Cloud (Free Nano Container)
- **Container Plan**: Free Nano (512 MB RAM / 0.5 CPU)
- **Environment Group**: `delta-preserver-env`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Schedule**: `30 12 * * *` (UTC — 18:00 IST daily)

### GitHub Actions
The repository includes `.github/workflows/daily_preserver.yml` pre-configured to run automatically daily at 12:30 UTC or manually via GitHub `workflow_dispatch`.
