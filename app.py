#!/usr/bin/env python3
"""
app.py – Flask web-based polite GET requester (Render-safe version)
"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from flask import Flask, request, render_template

# ---- Configuration defaults ----
DEFAULT_DELAY = 0.1
DEFAULT_CONCURRENCY = 5
DEFAULT_MAX_REQUESTS = 500  # capped for Render safety
USER_AGENT = "PoliteRequester/1.0 (+mailto:someone@gmail.com)"  # change email

app = Flask(__name__)

def is_valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def polite_get(session, url, timeout=10, max_retries=3):
    backoff = 1.0
    for attempt in range(1, max_retries + 1):
        try:
            r = session.get(url, timeout=timeout)
        except requests.RequestException as e:
            if attempt == max_retries:
                return {"url": url, "error": f"network error: {e}", "status": None}
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
            continue

        status = r.status_code
        if status == 200:
            return {"url": url, "status": status, "len": len(r.content)}
        if status in (429, 500, 502, 503, 504) and attempt < max_retries:
            time.sleep(backoff)
            backoff = min(backoff * 2, 10)
            continue
        return {"url": url, "status": status, "len": len(r.content)}
    return {"url": url, "error": "max retries exhausted", "status": None}

def worker_task(session, template, n, delay):
    url = template.format(n=n) if "{n}" in template else template
    result = polite_get(session, url)
    time.sleep(delay)
    return result

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        url = request.form["url"].strip()
        try:
            total = int(request.form["total"])
        except Exception:
            return "❌ Invalid total"

        conc = int(request.form.get("concurrency", DEFAULT_CONCURRENCY))
        delay = float(request.form.get("delay", DEFAULT_DELAY))

        if not is_valid_url(url.replace("{n}", "1")):
            return "❌ Invalid URL"

        if total > DEFAULT_MAX_REQUESTS:
            return f"❌ Too many requests (limit {DEFAULT_MAX_REQUESTS})"

        if conc > DEFAULT_CONCURRENCY * 5:
            return f"❌ Concurrency too high (limit {DEFAULT_CONCURRENCY * 5})"

        headers = {"User-Agent": USER_AGENT}
        session = requests.Session()
        session.headers.update(headers)

        results = []
        with ThreadPoolExecutor(max_workers=conc) as ex:
            futures = [ex.submit(worker_task, session, url, i, delay) for i in range(1, total + 1)]
            for f in as_completed(futures):
                results.append(f.result())

        ok = sum(1 for r in results if r.get("status") == 200)
        errors = total - ok

        return render_template("results.html", results=results, total=total, ok=ok, errors=errors)

    return render_template("home.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
