# Delta Data Preserver v2.0 🚀

Automated, resilient daily ETL pipeline designed to preserve 1-minute OHLCV candle data for **Multi-Asset Perpetual Futures** and **All-Expiry Options** from Delta Exchange India into snappy-compressed Parquet archives, audited automatically, and synchronized to Google Drive via OAuth 2.0 with Telegram execution notifications. Built strictly with standard library + `pyarrow` (zero heavy external cloud SDKs).

---

## 📌 What's New in v2.0

1. **Perpetual Futures (5 Assets):**
   - Preserves continuous 1-minute candles for Bitcoin (`BTCUSD`), Ethereum (`ETHUSD`), Solana (`SOLUSD`), Gold (`XAUTUSD`), and Silver (`SLVONUSD`).
2. **Options All-Expiries (3 Assets):**
   - Captures all Call (`CE`) and Put (`PE`) option contracts across **every available expiry** (0-DTE, 1-DTE, Next-Day, Weekly, Monthly) for `BTC`, `ETH`, and `GOLD` (`XAUT`).
3. **Automated Data Auditing (`src/auditor.py`):**
   - Strict pre-upload quality audit validating file non-zero size, row counts, unique contracts, unique expiries, null checks, and time ranges.
4. **Google Drive Upload Verification (`src/gdrive_uploader.py`):**
   - Direct multipart OAuth 2.0 uploader verifying returned file `id` and remote byte `size > 0`.
5. **Zero-Dependency Telegram Notifier (`src/telegram_notifier.py`):**
   - Instant HTML notification with execution duration, row counts, file sizes, and verification badges dispatched only after end-to-end success.

---

## 📁 Repository Structure

```text
delta-data-preserver/
├── .github/
│   └── workflows/
│       └── daily_preserver.yml     # Daily cron (18:00 IST) + workflow_dispatch
├── data/                           # Local storage (Git-ignored)
│   ├── futures/                    # data/futures/{asset}/{asset}_futures_{date}.parquet
│   └── options/                    # data/options/{asset}/{asset}_options_{date}.parquet
├── src/
│   ├── __init__.py
│   ├── config.py                   # Multi-asset registry, timeouts & IST timezone
│   ├── delta_client.py             # REST API client for Futures & Options candles
│   ├── storage.py                  # PyArrow snappy Parquet writers & schema validator
│   ├── auditor.py                  # Strict automated data quality auditor
│   ├── gdrive_uploader.py          # Zero-dependency Google OAuth multipart uploader
│   └── telegram_notifier.py        # Zero-dependency Telegram HTML notifier
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py            # Unit test suite (100% pytest pass)
├── .env.example                    # Template for environment variables
├── .gitignore                      # Git ignore rules for data, secrets, caches, and logs
├── get_token.py                    # Local developer tool for Google OAuth token generation
├── main.py                         # Production CLI entrypoint & v2.0 pipeline orchestrator
├── requirements.txt                # Lightweight production dependencies (pyarrow, pytest)
└── README.md                       # Comprehensive architecture & operational documentation
```

---

## 🔐 Environment Variables

| Variable | Description | Required |
| :--- | :--- | :---: |
| `GDRIVE_CLIENT_ID` | Google Cloud OAuth 2.0 Client ID | **Yes** |
| `GDRIVE_CLIENT_SECRET` | Google Cloud OAuth 2.0 Client Secret | **Yes** |
| `GDRIVE_REFRESH_TOKEN` | Long-lived OAuth 2.0 Refresh Token (`drive.file` scope) | **Yes** |
| `GDRIVE_FOLDER_ID` | Target Google Drive Folder ID for uploads | **Yes** |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token for run notifications | *Optional* |
| `TELEGRAM_CHAT_ID` | Telegram Chat ID for run notifications | *Optional* |

---

## 💻 CLI Usage

```bash
# Run full v2.0 pipeline (Futures + Options) for today's IST cycle:
python main.py

# Backfill a specific date (YYYY-MM-DD):
python main.py 2026-11-13

# Run Perpetual Futures only:
python main.py --futures-only

# Run Options only:
python main.py --options-only

# Target a specific asset only (e.g. BTC):
python main.py --asset=BTC
```

---

## 🧪 Testing

```bash
python -m pytest tests/ -v
```

---

## 🌐 24x7 Deployment on Hugging Face Spaces (Docker)

1. Create a new Space on [Hugging Face](https://huggingface.co/new-space):
   - **Space SDK**: `Docker` (Blank)
   - **Hardware**: Free (2 vCPU, 16 GB RAM)
2. Add your Space Secrets under **Settings -> Variables and secrets -> New secret**:
   - `GDRIVE_CLIENT_ID`
   - `GDRIVE_CLIENT_SECRET`
   - `GDRIVE_REFRESH_TOKEN`
   - `GDRIVE_FOLDER_ID`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. Push repository to Hugging Face Spaces remote:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/delta-data-preserver
   git push space main
   ```
4. The Space will automatically:
   - Expose the HTTP status dashboard on port `7860` (`/` and `/status`).
   - Run the background scheduler at **`18:15 IST` (6:15 PM IST)** daily.
   - Route Parquet archives into `Crypto/Futures` & `Crypto/Options` on Google Drive.
   - Send Telegram summary reports to your phone.
   - Stay awake 24x7 via health-check polling or external uptime monitors.
