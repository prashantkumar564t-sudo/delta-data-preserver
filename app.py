import os
import sys
import time
import json
import threading
import subprocess
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# --- CONFIGURATION & TIMEZONE ---
IST = timezone(timedelta(hours=5, minutes=30))
PORT = int(os.getenv("PORT", 7860))
SCHEDULE_HOUR_IST = 18
SCHEDULE_MINUTE_IST = 15

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "data", ".scheduler_state.json")

# In-memory application state
APP_START_TIME = time.time()
STATE = {
    "status": "HEALTHY",
    "service": "Delta Data Preserver v2.0",
    "uptime_start_ist": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
    "last_run_date_ist": None,
    "last_run_status": "NONE",
    "last_run_duration_sec": 0.0,
    "last_run_completed_ist": None,
    "is_running_now": False,
    "next_scheduled_run_ist": None,
    "last_log_tail": "No run executed yet."
}

def load_persisted_state():
    """Loads previous run state from disk to prevent duplicate executions on restart."""
    global STATE
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                STATE["last_run_date_ist"] = saved.get("last_run_date_ist")
                STATE["last_run_status"] = saved.get("last_run_status", "NONE")
                STATE["last_run_completed_ist"] = saved.get("last_run_completed_ist")
                print(f"[*] Restored previous scheduler state: last run date {STATE['last_run_date_ist']}")
        except Exception as e:
            print(f"[!] Warning reading scheduler state file: {e}")

def save_persisted_state():
    """Persists run state to disk."""
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "last_run_date_ist": STATE["last_run_date_ist"],
                "last_run_status": STATE["last_run_status"],
                "last_run_completed_ist": STATE["last_run_completed_ist"]
            }, f, indent=2)
    except Exception as e:
        print(f"[!] Warning saving scheduler state: {e}")

def compute_next_run(now_ist: datetime) -> str:
    """Calculates the exact next 18:15 IST execution timestamp."""
    today_target = now_ist.replace(hour=SCHEDULE_HOUR_IST, minute=SCHEDULE_MINUTE_IST, second=0, microsecond=0)
    if now_ist >= today_target:
        next_run = today_target + timedelta(days=1)
    else:
        next_run = today_target
    return next_run.strftime("%Y-%m-%d %H:%M:%S IST")

def execute_preserver_job(target_date: str = None) -> bool:
    """Spawns main.py in a controlled subprocess and captures real-time status."""
    global STATE
    if STATE["is_running_now"]:
        print("[!] Execution already in progress. Skipping duplicate request.")
        return False

    STATE["is_running_now"] = True
    start_ts = time.time()
    today_ist = target_date or datetime.now(IST).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"[*] LAUNCHING DAILY PRESERVER JOB FOR: {today_ist}")
    print(f"{'='*60}\n")

    cmd = [sys.executable, "main.py", today_ist]
    try:
        proc = subprocess.run(
            cmd,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1800  # 30 min safety cap
        )
        duration = time.time() - start_ts
        STATE["last_run_duration_sec"] = round(duration, 2)
        STATE["last_run_completed_ist"] = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        STATE["last_run_date_ist"] = today_ist
        STATE["last_log_tail"] = "\n".join(proc.stdout.strip().splitlines()[-25:])

        if proc.returncode == 0:
            STATE["last_run_status"] = "SUCCESS"
            print(f"[✓] Preserver job completed successfully in {duration:.2f}s")
            save_persisted_state()
            STATE["is_running_now"] = False
            return True
        else:
            STATE["last_run_status"] = "FAILED"
            print(f"[!] Preserver job failed with return code {proc.returncode}")
            save_persisted_state()
            STATE["is_running_now"] = False
            return False

    except Exception as e:
        STATE["last_run_status"] = f"ERROR: {e}"
        STATE["is_running_now"] = False
        print(f"[CRITICAL] Error running preserver job: {e}")
        return False

def scheduler_daemon_loop():
    """Background thread monitoring the daily 18:15 IST schedule."""
    print(f"[*] Scheduler daemon thread started. Monitoring for daily {SCHEDULE_HOUR_IST}:{SCHEDULE_MINUTE_IST:02d} IST...")
    while True:
        try:
            now_ist = datetime.now(IST)
            STATE["next_scheduled_run_ist"] = compute_next_run(now_ist)
            today_str = now_ist.strftime("%Y-%m-%d")

            # Condition to trigger:
            # 1. Current time is >= 18:15 IST today
            # 2. It has NOT already run for today
            # 3. Not currently executing
            target_time_today = now_ist.replace(hour=SCHEDULE_HOUR_IST, minute=SCHEDULE_MINUTE_IST, second=0, microsecond=0)

            if now_ist >= target_time_today and STATE["last_run_date_ist"] != today_str and not STATE["is_running_now"]:
                print(f"[*] Daily schedule triggered at {now_ist.strftime('%H:%M:%S')} IST! Target: {today_str}")
                execute_preserver_job(today_str)

        except Exception as e:
            print(f"[!] Scheduler exception: {e}")

        time.sleep(20)

class StatusHTTPHandler(BaseHTTPRequestHandler):
    """Zero-dependency HTTP server responding to health checks & dashboard views."""
    def log_message(self, format, *args):
        # Silence routine HTTP polling logs to keep stdout clean
        pass

    def do_GET(self):
        now_ist = datetime.now(IST)
        uptime_sec = int(time.time() - APP_START_TIME)

        if self.path in ("/status", "/health", "/api/status"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            data = {
                "status": STATE["status"],
                "service": STATE["service"],
                "uptime_seconds": uptime_sec,
                "current_time_ist": now_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
                "last_run_date_ist": STATE["last_run_date_ist"],
                "last_run_status": STATE["last_run_status"],
                "last_run_duration_sec": STATE["last_run_duration_sec"],
                "last_run_completed_ist": STATE["last_run_completed_ist"],
                "is_running_now": STATE["is_running_now"],
                "next_scheduled_run_ist": STATE["next_scheduled_run_ist"] or compute_next_run(now_ist)
            }
            self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))
            return

        elif self.path == "/trigger":
            # Manual trigger on-demand
            threading.Thread(target=execute_preserver_job, daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"message": "Job execution triggered asynchronously."}).encode("utf-8"))
            return

        # Default: Modern Web Dashboard
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        status_color = "#10b981" if STATE["last_run_status"] == "SUCCESS" else ("#f59e0b" if STATE["last_run_status"] == "NONE" else "#ef4444")
        running_badge = "<span style='color: #3b82f6;'>🔄 Executing Now...</span>" if STATE["is_running_now"] else "<span style='color: #10b981;'>⏳ Idle / Waiting for 18:15 IST</span>"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Delta Data Preserver v2.0</title>
    <meta http-equiv="refresh" content="30">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 30px; }}
        .card {{ background: #1e293b; border-radius: 12px; padding: 24px; max-width: 760px; margin: 0 auto; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }}
        h1 {{ margin-top: 0; font-size: 24px; display: flex; align-items: center; gap: 10px; }}
        .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 20px 0; }}
        .stat {{ background: #334155; padding: 14px; border-radius: 8px; }}
        .stat-label {{ font-size: 12px; text-transform: uppercase; color: #94a3b8; font-weight: bold; }}
        .stat-val {{ font-size: 16px; font-weight: bold; margin-top: 4px; }}
        pre {{ background: #090d16; padding: 14px; border-radius: 8px; font-size: 12px; overflow-x: auto; color: #38bdf8; }}
        .btn {{ display: inline-block; background: #2563eb; color: #fff; padding: 10px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; border: none; cursor: pointer; }}
        .btn:hover {{ background: #1d4ed8; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>🚀 Delta Data Preserver v2.0</h1>
        <p style="color: #94a3b8; font-size: 14px;">Continuous Multi-Asset Futures & All-Expiry Options Archiver to Google Drive.</p>
        
        <div class="grid">
            <div class="stat">
                <div class="stat-label">Current Time (IST)</div>
                <div class="stat-val">{now_ist.strftime("%Y-%m-%d %H:%M:%S")}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Scheduler State</div>
                <div class="stat-val">{running_badge}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Next Scheduled Run</div>
                <div class="stat-val" style="color: #facc15;">{STATE["next_scheduled_run_ist"] or compute_next_run(now_ist)}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Last Execution Status</div>
                <div class="stat-val" style="color: {status_color};">{STATE["last_run_status"]} ({STATE["last_run_date_ist"] or 'N/A'})</div>
            </div>
        </div>

        <div style="margin: 20px 0;">
            <a href="/trigger" class="btn" onclick="alert('Trigger request submitted! It will run in the background.');">⚡ Run Preserver Now</a>
            <a href="/status" style="margin-left: 12px; color: #38bdf8; font-size: 14px; text-decoration: none;">View JSON API &rarr;</a>
        </div>

        <div class="stat-label">Recent Run Log Tail</div>
        <pre>{STATE["last_log_tail"]}</pre>
    </div>
</body>
</html>
"""
        self.wfile.write(html.encode("utf-8"))

def run_server():
    load_persisted_state()
    # Start scheduler daemon in background
    scheduler_thread = threading.Thread(target=scheduler_daemon_loop, daemon=True)
    scheduler_thread.start()

    server = HTTPServer(("0.0.0.0", PORT), StatusHTTPHandler)
    print(f"[✓] Delta Data Preserver HTTP server listening on port {PORT} (0.0.0.0:{PORT})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server shutting down...")
        server.server_close()

if __name__ == "__main__":
    run_server()

