import time
import os
import json
from collections import deque
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import requests
from twilio.rest import Client

# ------------------------------------------------------------------------
# 1. Configuration & Logging Setup
# ------------------------------------------------------------------------
load_dotenv()  # Reads variables from .env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_PHONE = os.getenv("FROM_PHONE")  # Must be voice-capable Twilio number
TO_PHONE = os.getenv("TO_PHONE")
CHECK_URL = os.getenv("CHECK_URL")

MAX_SAVED_RESPONSES = 10

# Directory for log files
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)  # Ensure logs directory exists

# Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Strings to check
SOLD_OUT_TEXT = "This item is currently sold out but we are working to get more inventory."

# Disguised request headers (mimicking a real browser)
HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
              "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "cookie": "dtSa=-",
    "dnt": "1",
    "priority": "u=0, i",
    "referer": "https://www.bing.com/",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "cross-site",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0")
}


# ------------------------------------------------------------------------
# 2. Logging Functions
# ------------------------------------------------------------------------
def get_today_log_file():
    """Returns a log filename based on the current date, stored in the logs/ folder."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOGS_DIR, f"log_{today_str}.txt")

def log_message(message: str):
    """
    Prints the message with a timestamp, and also appends it to today's log file.
    """
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp_str}] {message}"
    print(line)

    # Append to today's log
    with open(get_today_log_file(), "a", encoding="utf-8") as f:
        f.write(line + "\n")

def cleanup_old_logs():
    """
    Removes log files older than 30 days in the logs/ folder.
    Expects files named like 'log_YYYY-MM-DD.txt'.
    """
    cutoff = datetime.now() - timedelta(days=30)
    for filename in os.listdir(LOGS_DIR):
        if filename.startswith("log_") and filename.endswith(".txt"):
            date_str = filename[len("log_"):-4]  # Extract 'YYYY-MM-DD'
            try:
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    os.remove(os.path.join(LOGS_DIR, filename))
                    log_message(f"Removed old log file: {filename}")
            except ValueError:
                pass

def log_state_change(old_status, new_status):
    """
    When a status change occurs, record it in 'state_changes.json' as a JSON array of events.
    """
    data = []
    if os.path.exists("state_changes.json"):
        try:
            with open("state_changes.json", "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass

    event = {
        "timestamp": datetime.now().isoformat(),
        "old_status": old_status,
        "new_status": new_status
    }
    data.append(event)

    with open("state_changes.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ------------------------------------------------------------------------
# 3. Dynamic Wait Time (6 AM to 2 PM PT, M-F => 1 min, else => 10 min)
# ------------------------------------------------------------------------
def get_current_wait_time_seconds():
    """
    Monday-Friday (weekday < 5), from 6 AM PT to 1:59 PM PT => 60s
    Otherwise => 600s
    """
    now_pt = datetime.now(ZoneInfo("America/Los_Angeles"))  # Current Pacific Time
    # weekday(): Monday=0, Sunday=6
    # hour in 24h format => 6 <= hour < 14 means 6 AM to 1:59 PM
    if now_pt.weekday() < 5 and 6 <= now_pt.hour < 14:
        return 60
    else:
        return 600

# ------------------------------------------------------------------------
# 4. Extract SKU
# ------------------------------------------------------------------------
def extract_sku(url):
    """Extracts 'skuId=#######' from the URL. Returns the digits as a string."""
    match = re.search(r"skuId=(\d+)", url)
    if match:
        return match.group(1)
    return None

SKU = extract_sku(CHECK_URL)
if not SKU:
    log_message("Warning: Could not extract SKU from the CHECK_URL. Check the URL format.")
    SKU = "0000000"

ADD_TO_CART_MARKER = f'data-sku-id="{SKU}" data-button-state="ADD_TO_CART"'

# ------------------------------------------------------------------------
# 5. check_status()
# ------------------------------------------------------------------------
def check_status(save_html=False, saved_files_queue=None):
    """
    Fetches the page with disguised headers.
    Returns "sold_out", "in_stock", or "fail".

    If save_html=True, saves the response to a timestamped file in the current dir,
    only keeping last N in saved_files_queue.
    """
    try:
        response = requests.get(CHECK_URL, headers=HEADERS, timeout=10)
        page_text = response.text

        if SOLD_OUT_TEXT in page_text:
            current_status = "sold_out"
        elif ADD_TO_CART_MARKER in page_text:
            current_status = "in_stock"
        else:
            current_status = "fail"

        if save_html and saved_files_queue is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bestbuy_{timestamp}_{current_status}.html"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(page_text)
            saved_files_queue.append(filename)
            # Only keep last N
            if len(saved_files_queue) > MAX_SAVED_RESPONSES:
                oldest_file = saved_files_queue.popleft()
                try:
                    os.remove(oldest_file)
                except OSError:
                    pass

        return current_status

    except Exception as e:
        log_message(f"Error fetching the URL: {e}")
        return "fail"

# ------------------------------------------------------------------------
# 6. place_call()
# ------------------------------------------------------------------------
def place_call(message: str):
    """
    Places a phone call via Twilio, reading `message` with text-to-speech.
    """
    try:
        call = twilio_client.calls.create(
            twiml=f'<Response><Say>{message}</Say></Response>',
            to=TO_PHONE,
            from_=FROM_PHONE
        )
        log_message(f"[CALL PLACED] {message} | Call SID: {call.sid}")
    except Exception as e:
        log_message(f"Error placing call: {e}")

# ------------------------------------------------------------------------
# 7. handle_status_change()
# ------------------------------------------------------------------------
def handle_status_change(current_status, last_status):
    """
    - If status changed, log to JSON, call if 'in_stock', else print.
    - If no change, 'No change'.
    Returns updated last_status.
    """
    if current_status != last_status:
        # We have a status change -> log in JSON
        log_state_change(last_status, current_status)

        if current_status == "in_stock":
            place_call("Hurry. The 5090 is now in stock at Best Buy.")
        elif current_status == "sold_out":
            log_message("Update: The 5090 is sold out. (No call made.)")
        else:  # "fail"
            log_message("Alert: The page might have failed or changed unexpectedly. (No call made.)")

        return current_status
    else:
        log_message(f"No change. Current status: {current_status}")
        return last_status

# ------------------------------------------------------------------------
# 8. Monitor Mode
# ------------------------------------------------------------------------
def monitor_mode():
    """
    Checks Best Buy at intervals based on day/time. Logs everything with timestamps.
    Only calls if 'in_stock'.
    """
    cleanup_old_logs()  # Purge logs older than 30 days
    last_status = None
    log_message("Starting monitor mode. Checking at dynamic intervals (PT). Press Ctrl+C to stop.\n")

    while True:
        current_status = check_status(save_html=False)
        last_status = handle_status_change(current_status, last_status)

        wait_time_seconds = get_current_wait_time_seconds()
        log_message(f"Next check in {wait_time_seconds // 60} minute(s).")
        time.sleep(wait_time_seconds)

# ------------------------------------------------------------------------
# 9. Test Interactive Mode
# ------------------------------------------------------------------------
def test_interactive_mode():
    """
    Force statuses or fetch page, applying same status-change logic as monitor mode.
    """
    cleanup_old_logs()  # Purge old logs on start
    saved_files_queue = deque(maxlen=MAX_SAVED_RESPONSES)
    last_status = None

    log_message("Entering TEST INTERACTIVE MODE.")
    log_message("Options: s/sold_out, i/in_stock, f/fail, <Enter>=fetch, q=quit")

    while True:
        user_input = input("Your choice (s/i/f/Enter/q): ").strip().lower()
        if user_input == "q":
            log_message("Exiting Test Interactive Mode.")
            break
        elif user_input in ["s", "i", "f"]:
            forced_status = {
                "s": "sold_out",
                "i": "in_stock",
                "f": "fail"
            }[user_input]
            last_status = handle_status_change(forced_status, last_status)
        elif user_input == "":
            current_status = check_status(save_html=True, saved_files_queue=saved_files_queue)
            last_status = handle_status_change(current_status, last_status)
        else:
            log_message("Unrecognized input. Try again.\n")

# ------------------------------------------------------------------------
# 10. Main Launcher
# ------------------------------------------------------------------------
if __name__ == "__main__":
    log_message("Select a Mode:")
    log_message("1) Monitor Mode (variable intervals M-F 6am-2pm PT => 1 min, else => 10 min)")
    log_message("2) Test Interactive Mode (force statuses or fetch)")

    mode_choice = input("Enter 1 or 2: ").strip()
    if mode_choice == "1":
        monitor_mode()
    elif mode_choice == "2":
        test_interactive_mode()
    else:
        log_message("Invalid selection. Exiting.")
