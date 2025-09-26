#!/usr/bin/env python3
"""
interactive_polite_gets_simple.py

Simplified polite GET requester.

Run:
  python interactive_polite_gets_simple.py

Then follow prompts:
 - Enter URL (use {n} if you want request numbers inserted, or leave plain to repeat the same URL)
 - Enter how many requests to send
"""

import time
import sys
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# ---- Configuration defaults ----
DEFAULT_DELAY = 0.000001
DEFAULT_CONCURRENCY = 100
DEFAULT_MAX_REQUESTS = 50000000000
USER_AGENT = "PoliteRequester/1.0 (+mailto:someone@gmail.com)"  # change email

def is_valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def polite_get(session, url, timeout=15, max_retries=5):
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, timeout=timeout)
        except requests.RequestException as e:
            if attempt == max_retries:
                return {"url": url, "error": f"network error: {e}", "status": None}
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue

        status = r.status_code
        if status == 200:
            return {"url": url, "status": status, "len": len(r.content)}
        if status in (429, 500, 502, 503, 504) and attempt < max_retries:
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        return {"url": url, "status": status, "len": len(r.content)}
    return {"url": url, "error": "max retries exhausted", "status": None}

def worker_task(session, template, n, delay):
    if "{n}" in template:
        url = template.format(n=n)
    else:
        url = template
    result = polite_get(session, url)
    time.sleep(delay)
    return result

def prompt_input(prompt_text, validate=None, allow_empty=False):
    while True:
        val = input(prompt_text).strip()
        if val == "" and allow_empty:
            return val
        if validate is None:
            return val
        try:
            if validate(val):
                return val
            else:
                print("Invalid input, please try again.")
        except Exception as e:
            print("Invalid input:", e)

def main():
    print("WARNING: Only use this on sites you own or have explicit permission to test.\n")

    url = prompt_input('Enter URL (use "{n}" if you want a numeric placeholder) : ',
                       validate=lambda v: is_valid_url(v.replace("{n}", "1")))

    total = int(prompt_input("How many requests do you want to send? ",
                             validate=lambda v: v.isdigit() and int(v) > 0))

    conc = prompt_input(f"Concurrency (default {DEFAULT_CONCURRENCY}) : ",
                        validate=lambda v: v.isdigit() and int(v) > 0 if v else True, allow_empty=True)
    delay = prompt_input(f"Per-worker delay in seconds (default {DEFAULT_DELAY}) : ",
                         validate=lambda v: v.replace(".","",1).isdigit() if v else True, allow_empty=True)

    concurrency = int(conc) if conc else DEFAULT_CONCURRENCY
    delay = float(delay) if delay else DEFAULT_DELAY

    if total > DEFAULT_MAX_REQUESTS:
        print(f"\nRequested {total} exceeds safe cap ({DEFAULT_MAX_REQUESTS}).")
        conf = prompt_input("Type 'yes' to proceed anyway, anything else to cancel: ", allow_empty=True)
        if conf.lower() != "yes":
            print("Canceled.")
            sys.exit(1)

    print(f"\nWill send {total} requests. Concurrency={concurrency}, delay={delay}s per worker.")
    confirm = prompt_input("Type 'go' to start or anything else to cancel: ", allow_empty=True)
    if confirm.lower() != "go":
        print("Canceled.")
        sys.exit(0)

    headers = {"User-Agent": USER_AGENT}
    session = requests.Session()
    session.headers.update(headers)

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = []
        for n in range(1, total + 1):
            futures.append(ex.submit(worker_task, session, url, n, delay))
        try:
            for future in as_completed(futures):
                res = future.result()
                results.append(res)
                if res.get("status") == 200:
                    print(f"[OK] {res['url']} 200 len={res.get('len')}")
                elif res.get("status"):
                    print(f"[HTTP {res['status']}] {res['url']}")
                else:
                    print(f"[ERR] {res.get('url')} -> {res.get('error')}")
        except KeyboardInterrupt:
            print("Interrupted by user. Exiting.")
            ex.shutdown(wait=False)
            sys.exit(1)

    ok = sum(1 for r in results if r.get("status") == 200)
    errors = total - ok
    print("\nDone. Summary:")
    print(f"  Total requested: {total}")
    print(f"  200 OK: {ok}")
    print(f"  Other/Errors: {errors}")

if __name__ == "__main__":
    main()
