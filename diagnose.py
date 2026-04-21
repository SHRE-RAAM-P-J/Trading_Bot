# -*- coding: utf-8 -*-
"""
diagnose.py - Run this to find exactly what is wrong with your API setup.
Usage: python diagnose.py
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
import hashlib
import hmac
import time
from urllib.parse import urlencode
import requests

# ── PASTE YOUR KEYS HERE ──────────────────────────────────────────────────────
API_KEY = "aq41M1eyRCrcUComd4OaciqoCeyCyDorWXQNzCzItFhnu1ihEl1NxKaS2ABN3Hj8"
API_SECRET = "lzD0jgnlR9dCrlK6HiritbaBAlIsn8KihY3dwSsUnyYy2X038cDFm59UPkJbCKMQ"

# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://demo-fapi.binance.com"

def sign(params, secret):
    params["timestamp"] = int(time.time() * 1000)
    query = urlencode(params)
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    params["signature"] = sig
    return params

def check(label, ok, detail=""):
    icon = "OK" if ok else "FAIL"
    print(f"  [{icon}] {label}" + (f" -- {detail}" if detail else ""))

print("\n" + "="*55)
print("  Binance Demo Futures API Diagnostic")
print("="*55)

# 1. Key format check
print("\n[1] Checking key format...")
key_ok = len(API_KEY) > 20 and API_KEY not in ("PASTE_YOUR_API_KEY_HERE", "")
sec_ok = len(API_SECRET) > 20 and API_SECRET not in ("PASTE_YOUR_API_SECRET_HERE", "")
check("API_KEY looks valid", key_ok, f"length={len(API_KEY)}, starts={API_KEY[:6]}...{API_KEY[-4:]}")
check("API_SECRET looks valid", sec_ok, f"length={len(API_SECRET)}")
if not key_ok or not sec_ok:
    print("\n  !! Keys not set. Edit diagnose.py and paste your keys at the top.\n")
    exit(1)

# 2. Connectivity
print("\n[2] Testing connectivity to demo-fapi.binance.com ...")
try:
    r = requests.get(f"{BASE_URL}/fapi/v1/ping", timeout=10)
    check("Ping demo-fapi.binance.com", r.status_code == 200, f"HTTP {r.status_code}")
except Exception as e:
    check("Ping demo-fapi.binance.com", False, str(e))
    print("  !! Cannot reach demo-fapi.binance.com -- check your internet.\n")
    exit(1)

# 3. Server time vs local time
print("\n[3] Checking time sync...")
r = requests.get(f"{BASE_URL}/fapi/v1/time", timeout=10)
server_ms = r.json()["serverTime"]
local_ms  = int(time.time() * 1000)
drift_ms  = abs(server_ms - local_ms)
check("Time drift acceptable (<1000ms)", drift_ms < 1000, f"drift={drift_ms}ms")
if drift_ms >= 1000:
    print(f"  !! Your system clock is off by {drift_ms}ms -- this causes signature failures.")
    print("     Fix: sync your Windows clock via Settings > Time & Language > Sync now\n")

# 4. Unsigned request with API key (read-only)
print("\n[4] Testing API key on public endpoint (no signature)...")
headers = {"X-MBX-APIKEY": API_KEY}
r = requests.get(f"{BASE_URL}/fapi/v1/ticker/price", params={"symbol": "BTCUSDT"}, headers=headers, timeout=10)
check("Public endpoint with API key header", r.status_code == 200, f"HTTP {r.status_code} -- {r.text[:80]}")

# 5. Signed request (private)
print("\n[5] Testing signed request (private endpoint)...")
headers = {"X-MBX-APIKEY": API_KEY}
params  = sign({}, API_SECRET)
r = requests.get(f"{BASE_URL}/fapi/v2/balance", params=params, headers=headers, timeout=10)
if r.status_code == 200:
    check("Signed request /fapi/v2/balance", True, "Keys are working!")
    balances = [b for b in r.json() if float(b.get("balance","0")) > 0]
    if balances:
        print(f"\n  Balances found:")
        for b in balances:
            print(f"    {b['asset']}: {b['balance']}")
    else:
        print("  (No balance yet -- that's normal for a new demo account)")
else:
    data = r.json()
    code = data.get("code")
    msg  = data.get("msg")
    check("Signed request /fapi/v2/balance", False, f"Error {code}: {msg}")

    print(f"\n  Diagnosis:")
    if code == -2015:
        print("  !! -2015 means one of:")
        print("     a) You are using REAL account keys instead of Demo Trading keys")
        print("     b) The key was created on demo but 'Enable Futures' is not checked")
        print("     c) The key has an IP whitelist that excludes your current IP")
        print("")
        print("  ACTION: On the demo trading API page, click your key name ('Cook')")
        print("          and look for 'IP Access Restriction' -- set it to 'Unrestricted'")
    elif code == -1022:
        print("  !! -1022 = bad signature. Your clock may be out of sync.")
    elif code == -2014:
        print("  !! -2014 = API key format wrong. Re-copy the key carefully.")

print("\n" + "="*55 + "\n")