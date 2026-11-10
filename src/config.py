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
    "User-Agent": "DeltaDataPreserver/1.0"
}

# --- TIMEZONE SETTINGS (IST: UTC + 5:30) ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- PROJECT DIRECTORIES ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OPTIONS_DATA_DIR = os.path.join(DATA_DIR, "options")

# --- NETWORK & RETRY SETTINGS ---
REQUEST_TIMEOUT = 15  # seconds
RATE_LIMIT_SLEEP = 0.1  # seconds between strike candle requests
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # seconds

# --- GOOGLE DRIVE DEFAULT FALLBACK ---
DEFAULT_GDRIVE_FOLDER_ID = "1aVINc1rkrbnaVfATjkMj8yw-JlidKFpe"