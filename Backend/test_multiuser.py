"""
test_multiuser.py — Verifies that two "users" hitting the Flask app at the
same time get their own isolated session state (no cross-talk).

HOW TO RUN:
  1. In one terminal: start your Flask app as usual (python app.py or app/run.py — whatever you normally do)
  2. In a second terminal: python test_multiuser.py
  3. Read the PASS/FAIL lines it prints

No real webcam is used — we send a small blank fake image instead, just to
exercise the /process_frame route.

Requires: requests (pip install requests) — you likely already have cv2/numpy
since your Flask app uses them.
"""

import base64
import cv2
import numpy as np
import requests

BASE_URL = "http://127.0.0.1:5000"


def make_dummy_frame_b64():
    """Create a small blank fake 'webcam frame' and base64-encode it,
    the same format the real browser sends to /process_frame."""
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    ok, buffer = cv2.imencode('.jpg', blank)
    b64 = base64.b64encode(buffer).decode('utf-8')
    return 'data:image/jpeg;base64,' + b64


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


def main():
    dummy_image = make_dummy_frame_b64()

    # Two separate requests.Session() objects = two separate "browsers".
    # Each one will get its own Flask session cookie automatically.
    user_a = requests.Session()
    user_b = requests.Session()

    all_passed = True

    print("\nStep 1: User A starts detection")
    r = user_a.post(f"{BASE_URL}/start")
    all_passed &= check("User A /start succeeded", r.ok and r.json().get('status') == 'success')

    print("\nStep 2: Check User B is NOT accidentally active")
    r = user_b.get(f"{BASE_URL}/stats")
    stats_b = r.json()
    all_passed &= check(
        "User B still shows 'Stopped' (unaffected by User A starting)",
        stats_b.get('posture_status') == 'Stopped'
    )

    print("\nStep 3: User B starts their own detection")
    r = user_b.post(f"{BASE_URL}/start")
    all_passed &= check("User B /start succeeded", r.ok and r.json().get('status') == 'success')

    print("\nStep 4: Both users send a frame (simulating live video)")
    r_a = user_a.post(f"{BASE_URL}/process_frame", json={"image": dummy_image})
    r_b = user_b.post(f"{BASE_URL}/process_frame", json={"image": dummy_image})
    all_passed &= check("User A /process_frame succeeded", r_a.ok and r_a.json().get('status') == 'success')
    all_passed &= check("User B /process_frame succeeded", r_b.ok and r_b.json().get('status') == 'success')

    print("\nStep 5: User A stops detection")
    r = user_a.post(f"{BASE_URL}/stop", json={"user_name": "Tester A"})
    all_passed &= check("User A /stop succeeded", r.ok and r.json().get('status') == 'success')

    print("\nStep 6: Check User B is STILL active (A stopping shouldn't affect B)")
    r = user_b.get(f"{BASE_URL}/stats")
    stats_b_after = r.json()
    all_passed &= check(
        "User B still NOT showing 'Stopped' (unaffected by User A stopping)",
        stats_b_after.get('posture_status') != 'Stopped'
    )

    print("\nStep 7: Check User A is now Stopped (their own state updated correctly)")
    r = user_a.get(f"{BASE_URL}/stats")
    stats_a_after = r.json()
    all_passed &= check(
        "User A shows 'Stopped' after their own /stop",
        stats_a_after.get('posture_status') == 'Stopped'
    )

    print("\nStep 8: User B stops detection (cleanup)")
    r = user_b.post(f"{BASE_URL}/stop", json={"user_name": "Tester B"})
    all_passed &= check("User B /stop succeeded", r.ok and r.json().get('status') == 'success')

    print("\n" + "=" * 50)
    if all_passed:
        print("ALL CHECKS PASSED — sessions are correctly isolated.")
    else:
        print("SOME CHECKS FAILED — see [FAIL] lines above.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print(f"\nCould not connect to {BASE_URL}")
        print("Make sure your Flask app is running first (python app.py) in another terminal.\n")