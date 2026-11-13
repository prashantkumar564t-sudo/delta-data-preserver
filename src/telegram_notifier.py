import os
import json
import urllib.request
import urllib.error

TELEGRAM_API_URL = "https://api.telegram.org"

def send_telegram_message(message: str, bot_token: str = None, chat_id: str = None) -> bool:
    """
    Sends a formatted HTML message to a Telegram chat using zero external packages.
    Gracefully skips if credentials are not configured.
    """
    token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
    chat = chat_id or os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat:
        print("[i] Telegram notifications skipped (TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured).")
        return False

    url = f"{TELEGRAM_API_URL}/bot{token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                print("[✓] Telegram notification delivered successfully.")
                return True
            else:
                print(f"[!] Telegram API returned error: {data}")
                return False
    except urllib.error.HTTPError as e:
        print(f"[!] Telegram send HTTP error: {e.code} - {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"[!] Network error sending Telegram message: {e}")
        return False

def build_telegram_report(summary: dict) -> str:
    """Constructs a clean, informative Telegram HTML report from the pipeline summary."""
    target_date = summary.get("target_date", "N/A")
    duration = summary.get("duration_sec", 0.0)
    overall_status = summary.get("overall_status", "UNKNOWN")

    status_badge = "✅ <b>ALL VERIFIED &amp; SAVED TO GOOGLE DRIVE</b>" if overall_status == "SUCCESS" else "❌ <b>PIPELINE EXECUTION FAILED</b>"

    lines = [
        "🚀 <b>DELTA DATA PRESERVER v2.0 - RUN REPORT</b>",
        f"📅 <b>Date (IST):</b> <code>{target_date}</code>",
        f"⏱️ <b>Duration:</b> <code>{duration:.1f}s</code>",
        ""
    ]

    # Perpetual Futures section
    futures_data = summary.get("futures", [])
    if futures_data:
        lines.append("⚡ <b>PERPETUAL FUTURES (1m OHLCV):</b>")
        for item in futures_data:
            asset = item.get("asset", "")
            rows = item.get("rows", 0)
            size_kb = item.get("size_kb", 0.0)
            drive_icon = "✅" if item.get("drive_verified") else "⚠️"
            lines.append(f"• <b>{asset}:</b> {rows:,} rows | {size_kb:.1f} KB | {drive_icon} Drive")
        lines.append("")

    # Options section
    options_data = summary.get("options", [])
    if options_data:
        lines.append("🎯 <b>OPTIONS (ALL EXPIRIES - 1m OHLCV):</b>")
        for item in options_data:
            asset = item.get("asset", "")
            expiries = item.get("expiries", 0)
            contracts = item.get("contracts", 0)
            rows = item.get("rows", 0)
            size_kb = item.get("size_kb", 0.0)
            drive_icon = "✅" if item.get("drive_verified") else "⚠️"
            lines.append(
                f"• <b>{asset}:</b> {expiries} Expiries | {contracts} Contracts | {rows:,} rows | {size_kb:.1f} KB | {drive_icon} Drive"
            )
        lines.append("")

    lines.append(status_badge)
    return "\n".join(lines)

def send_pipeline_report(summary: dict) -> bool:
    """Helper to format and dispatch the full pipeline report."""
    report_text = build_telegram_report(summary)
    return send_telegram_message(report_text)

def send_failure_alert(error_msg: str, target_date: str = "") -> bool:
    """Sends an immediate critical failure alert via Telegram."""
    msg = (
        "🚨 <b>DELTA PRESERVER ALERT: EXECUTION FAILED</b>\n"
        f"📅 <b>Date:</b> {target_date}\n\n"
        f"<b>Error Details:</b>\n<code>{error_msg}</code>"
    )
    return send_telegram_message(msg)

