# BestBuy 5090 Checker (Voice Call Edition)

This script checks a **Best Buy** product page (e.g., the RTX 5090) to see if it’s **in stock**.  
If the item is in stock, the script will **call** your phone using **Twilio** and read an alert message.  
Otherwise, it just prints a status message to your screen.

---

## Table of Contents

1. [Requirements](#requirements)  
2. [Installation](#installation)  
3. [Configuration](#configuration)  
4. [How to Run](#how-to-run)  
   - [Monitor Mode](#monitor-mode)  
   - [Test Interactive Mode](#test-interactive-mode)  
5. [Troubleshooting](#troubleshooting)

---

## Requirements

1. **Python 3.8 or higher**  
2. A **Twilio** account with a **voice-capable** Twilio phone number  
3. Internet access to check the Best Buy page  

---

## Installation

1. **Download Python**  
   - If you don’t already have Python 3, go to [python.org/downloads](https://www.python.org/downloads/) and install it.  
   - On Windows, check “Add Python to PATH” during the install.

2. **Clone or Download** this repository  
   - You should see two critical files:
     - **`bestbuy_5090_checker.py`** (the main script)  
     - **`requirements.txt`** (the list of dependencies)

3. **Open a Command Prompt / Terminal**  
   - **Windows**: Press `Win + R`, type `cmd`, and press Enter.  
   - **Mac/Linux**: Open the **Terminal** app.

4. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```
   This will install everything the script needs, including **requests**, **python-dotenv**, and **twilio**.

---

## Configuration

1. **Create a `.env` File**  
   In the same folder as `bestbuy_5090_checker.py`, create a file named **`.env`** (no filename, just `.env`).  
   Paste in something like:
   ```ini
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
   FROM_PHONE=+12223334444
   TO_PHONE=+15556667777
   CHECK_URL=https://www.bestbuy.com/site/nvidia-geforce-rtx-5090-32gb-gddr7-graphics-card-dark-gun-metal/6614151.p?skuId=6614151
   ```

   - **TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN**: Found on your Twilio dashboard.  
   - **FROM_PHONE**: A Twilio **voice-capable** number (format: `+1XXXXXXXXXX`).  
   - **TO_PHONE**: The phone number you want called in `+1XXXXXXXXXX` format.  
   - **CHECK_URL**: The Best Buy product page URL (must include `?skuId=####`).  

2. **Save** the file.

---

## How to Run

1. **Open your Command Prompt / Terminal** in the folder containing `bestbuy_5090_checker.py`.  
2. Run:
   ```bash
   python bestbuy_5090_checker.py
   ```
3. You’ll see a menu with two modes:

### Monitor Mode
- **Checks** the Best Buy page every 60 seconds (by default).  
- If the product is **in stock**, you get an **immediate phone call**.  
- If sold out or it fails, it **prints** a message in the console (no call).  

**Select “1”** at the prompt to run in **Monitor Mode**.

### Test Interactive Mode
- **Manually** test calls or do an instant fetch:  
  - **s** → Force “sold out” (prints console message only)  
  - **i** → Force “in stock” (places a call)  
  - **f** → Force “fail” (prints message)  
  - **Enter** (no input) → Actually **fetch** the page and behave exactly like Monitor Mode  
  - **q** → Quit  

**Select “2”** at the prompt to run in **Test Interactive Mode**.

---

## Troubleshooting

1. **No module named ‘X’**  
   - Make sure you ran `pip install -r requirements.txt`.

2. **Not getting phone calls**  
   - Double-check **FROM_PHONE** is a **voice-capable** Twilio number.  
   - Check Twilio logs to see if calls are being placed or failing.  
   - Ensure **TO_PHONE** is valid and has the correct country code.

3. **Could not extract `skuId`**  
   - Confirm your URL includes `?skuId=####`. Otherwise, the script can’t detect the product.

4. **Timeout or Connection Error**  
   - The script will try again on its next loop. Ensure you have stable internet.

5. **Called but no voice**  
   - Possibly TwiML issues or Twilio side errors. Check Twilio’s call logs to see if the `<Say>` text was read.

That’s it! Once everything is set, run the script in **Monitor Mode**, and it will notify you by **phone call** when the RTX 5090 is in stock. Enjoy!