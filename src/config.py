import os
from datetime import timezone, timedelta

# --- ZERO-DEPENDENCY .ENV LOADER ---
def load_env(env_path: str = None):
    """Loads key-value pairs from .env into os.environ using only built-in standard library."""
    if env_path is None:
        # Defaults to .env file in project root directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, ".env")

    if not os.path.exists(env_path):
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Auto-execute on import so environment variables are immediately available
load_env()

# --- API ENDPOINTS & HEADERS ---
DELTA_BASE_URL = "https://api.india.delta.exchange/v2"
DEFAULT_HEADERS = {
    "User-Agent": "DeltaDataPreserver/2.0"
}

# --- TIMEZONE SETTINGS (IST: UTC + 5:30) ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- PROJECT DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FUTURES_DATA_DIR = os.path.join(DATA_DIR, "futures")
OPTIONS_DATA_DIR = os.path.join(DATA_DIR, "options")

# --- MULTI-ASSET CONFIGURATION (v2.0) ---
# Perpetual Futures: 5 Assets
FUTURES_ASSETS = {
    "BTC": "BTCUSD",
    "ETH": "ETHUSD",
    "SOL": "SOLUSD",
    "GOLD": "XAUTUSD",
    "SILVER": "SLVONUSD"
}

# Options: 3 Assets (All Expiries)
OPTIONS_ASSETS = {
    "BTC": "BTC",
    "ETH": "ETH",
    "GOLD": "XAUT"
}

# --- NETWORK & RETRY SETTINGS ---
REQUEST_TIMEOUT = 15  # seconds
RATE_LIMIT_SLEEP = 0.1  # seconds between strike candle requests
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

# --- CLOUD & NOTIFICATION SETTINGS ---
GDRIVE_FOLDER_ID = os.getenv("GDRIVE_FOLDER_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
