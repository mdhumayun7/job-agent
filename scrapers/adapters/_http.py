"""
Small shared HTTP helper for the newer adapters (Workday, Ashby, Workable,
Amazon). Same contract as the original adapters:

  * retries a few times on network / 5xx errors
  * returns None on a confirmed 404 (the board/slug does not exist)
  * raises RuntimeError once retries are exhausted, so the pipeline treats
    the company as "failed this run" instead of "has zero jobs" -- which
    protects job history from false CLOSED statuses.
"""

import time
import requests

USER_AGENT = "job-agent-bot/2.0 (+https://github.com/mdhumayun7/job-agent)"
TIMEOUT = 20


def request_json(url, method="GET", json_body=None, params=None, max_retries=3,
                 tag="http", extra_headers=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if json_body is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.request(method, url, json=json_body, params=params,
                                    headers=headers, timeout=TIMEOUT)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001 -- we re-raise below after retries
            last_error = e
            print(f"[{tag}] attempt {attempt}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"{tag} request failed after {max_retries} attempts: {url} -- {last_error}")
