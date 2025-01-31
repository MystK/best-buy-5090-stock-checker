import time
import os
from collections import deque
import re
import datetime
from dotenv import load_dotenv
import requests
from twilio.rest import Client

# ------------------------------------------------------------------------
# 1. Configuration
# ------------------------------------------------------------------------
load_dotenv()  # Reads variables from .env
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
FROM_PHONE = os.getenv("FROM_PHONE")  # Must be voice-capable Twilio number
TO_PHONE = os.getenv("TO_PHONE")

CHECK_URL = os.getenv("CHECK_URL")

# How long to wait between checks in monitor mode (in seconds)
WAIT_TIME = 60  # 1 minute by default

# How many HTML files to keep in test interactive mode (when fetching & saving)
MAX_SAVED_RESPONSES = 10

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
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0"
}

# ------------------------------------------------------------------------
# 2. Extract SKU from CHECK_URL to build the add-to-cart marker
# ------------------------------------------------------------------------
def extract_sku(url):
    """Extracts 'skuId=1234567' from the URL. Returns the digits as a string."""
    match = re.search(r"skuId=(\d+)", url)
    if match:
        return match.group(1)
    return None

SKU = extract_sku(CHECK_URL)
if not SKU:
    print("Warning: Could not extract SKU from the CHECK_URL. Check the URL format.")
    SKU = "0000000"

ADD_TO_CART_MARKER = f'data-sku-id="{SKU}" data-button-state="ADD_TO_CART"'

# ------------------------------------------------------------------------
# 3. Check Status (Fetch & Determine)
# ------------------------------------------------------------------------
def check_status(save_html=False, saved_files_queue=None):
    """
    Fetches the page with disguised headers.
    Returns "sold_out", "in_stock", or "fail".

    If save_html=True, saves the response to disk with the final status in the file name.
    Only keeps the last N in saved_files_queue (a deque).
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
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
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
        print(f"Error fetching the URL: {e}")
        return "fail"

# ------------------------------------------------------------------------
# 4. Place Call (Only if in stock)
# ------------------------------------------------------------------------
def place_call(message: str):
    """
    Places a phone call via Twilio and reads `message` with text-to-speech.
    """
    try:
        call = twilio_client.calls.create(
            twiml=f'<Response><Say>{message}</Say></Response>',
            to=TO_PHONE,
            from_=FROM_PHONE
        )
        print(f"[CALL PLACED] {message} | Call SID: {call.sid}")
    except Exception as e:
        print(f"Error placing call: {e}")

# ------------------------------------------------------------------------
# 5. Shared Logic (Monitor-Style)
# ------------------------------------------------------------------------
def handle_status_change(current_status, last_status):
    """
    This is the same logic used by monitor mode to handle status changes:
      - Only call if in_stock
      - Just print for sold_out / fail
      - If no change, we say 'No change'.
    Returns the updated last_status after applying logic.
    """
    if current_status != last_status:
        # There's a change
        if current_status == "in_stock":
            place_call("Hurry. The 5090 is now in stock at Best Buy.")
        elif current_status == "sold_out":
            print("Update: The 5090 is sold out. (No call made.)")
        else:  # "fail"
            print("Alert: The page might have failed or changed unexpectedly. (No call made.)")
        return current_status
    else:
        # No change
        print(f"No change. Current status: {current_status}")
        return last_status

# ------------------------------------------------------------------------
# 6. Monitor Mode
# ------------------------------------------------------------------------
def monitor_mode():
    """
    Repeatedly checks Best Buy every WAIT_TIME seconds,
    and uses handle_status_change() for consistent logic.
    """
    last_status = None
    print(f"Starting monitor mode. Checking every {WAIT_TIME} second(s). Press Ctrl+C to stop.\n")

    while True:
        current_status = check_status(save_html=False)
        # Use the shared logic block:
        last_status = handle_status_change(current_status, last_status)
        time.sleep(WAIT_TIME)

# ------------------------------------------------------------------------
# 7. Test Interactive Mode
# ------------------------------------------------------------------------
def test_interactive_mode():
    """
    Lets you:
      - 's'/'i'/'f': Force that status and run the same logic as monitor mode.
      - [Enter] -> fetch real page + run same logic.
      - 'q' -> quit
    """
    saved_files_queue = deque(maxlen=MAX_SAVED_RESPONSES)
    last_status = None  # We'll track changes just like monitor mode

    print("Entering TEST INTERACTIVE MODE.")
    print("Options:")
    print("  s -> Force 'sold_out' logic")
    print("  i -> Force 'in_stock' logic")
    print("  f -> Force 'fail' logic")
    print("  [Enter] -> Fetch page, save HTML, apply monitor logic to new status")
    print("  q -> Quit\n")

    while True:
        user_input = input("Your choice (s/i/f/Enter/q): ").strip().lower()

        if user_input == "q":
            print("Exiting Test Interactive Mode.\n")
            break

        elif user_input in ["s", "i", "f"]:
            # We forced a status
            forced_status = {
                "s": "sold_out",
                "i": "in_stock",
                "f": "fail"
            }[user_input]

            last_status = handle_status_change(forced_status, last_status)

        elif user_input == "":
            # fetch real page + same logic
            current_status = check_status(save_html=True, saved_files_queue=saved_files_queue)
            last_status = handle_status_change(current_status, last_status)

        else:
            print("Unrecognized input. Try again.\n")

# ------------------------------------------------------------------------
# 8. Main Launcher
# ------------------------------------------------------------------------
if __name__ == "__main__":
    print("Select a Mode:\n")
    print("1) Monitor Mode (checks every X seconds, calls if in stock, else prints)")
    print("2) Test Interactive Mode (force statuses or fetch page, same logic as monitor)")
    mode_choice = input("Enter 1 or 2: ").strip()

    if mode_choice == "1":
        monitor_mode()
    elif mode_choice == "2":
        test_interactive_mode()
    else:
        print("Invalid selection. Exiting.")
