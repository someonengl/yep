#!/usr/bin/env python3
"""
interactive_polite_gets_web.py

Flask web-based polite GET requester.
"""

import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse
from flask import Flask, request, render_template_string

# ---- Configuration defaults ----
DEFAULT_DELAY = 0.1
DEFAULT_CONCURRENCY = 1
DEFAULT_MAX_REQUESTS = 1000   # keep small for Render
USER_AGENT = "PoliteRequester/1.0 (+mailto:someone@gmail.com)"  # change email

app = Flask(__name__)

def is_valid_url(u: str) -> bool:
    try:
        p = urlparse(u)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def polite_get(session, url, timeout=15, max_retries=3):
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
        url = request.form.get("url", "").strip()
        if not url or not is_valid_url(url.replace("{n}", "1")):
            return "❌ Invalid or missing URL"

        try:
            total = int(request.form.get("total") or 1)
        except:
            total = 1

        try:
            conc = int(request.form.get("concurrency") or DEFAULT_CONCURRENCY)
        except:
            conc = DEFAULT_CONCURRENCY

        try:
            delay = float(request.form.get("delay") or DEFAULT_DELAY)
        except:
            delay = DEFAULT_DELAY

        if total > DEFAULT_MAX_REQUESTS:
            return f"❌ Too many requests (limit {DEFAULT_MAX_REQUESTS})"

        headers = {"User-Agent": USER_AGENT}
        session = requests.Session()
        session.headers.update(headers)

        results = []
        with ThreadPoolExecutor(max_workers=min(conc, 5)) as ex:  # cap concurrency for Render
            futures = [ex.submit(worker_task, session, url, i, delay) for i in range(1, total + 1)]
            for f in as_completed(futures):
                results.append(f.result())

        ok = sum(1 for r in results if r.get("status") == 200)
        errors = total - ok

        return render_template_string("""
        <h1>Results</h1>
        <p>Total: {{total}}, 200 OK: {{ok}}, Errors: {{errors}}</p>
        <ul>
        {% for r in results %}
          <li>
            {{r.url}} →
            {% if r.status %}
              Status {{r.status}} {% if r.get("len") %}(len={{r.get("len")}}){% endif %}
            {% else %}
              Error: {{r.error}}
            {% endif %}
          </li>
        {% endfor %}
        </ul>
        <a href="/">Go back</a>
        """, results=results, total=total, ok=ok, errors=errors)

    return """
    <h1>Polite GET Requester</h1>
    <form method="post">
      URL (use {n} for numbering): <br><input type="text" name="url" size="60"><br><br>
      Number of requests: <br><input type="number" name="total" value="1"><br><br>
      Concurrency: <br><input type="number" name="concurrency" value="1"><br><br>
      Delay per worker (seconds): <br><input type="text" name="delay" value="0.1"><br><br>
      <input type="submit" value="Start">
    </form>
    """

if __name__ == "__main__":
    # On Render, Flask must listen on 0.0.0.0 and port from $PORT env var
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
