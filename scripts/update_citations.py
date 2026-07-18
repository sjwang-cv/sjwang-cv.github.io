#!/usr/bin/env python3
"""Fetch Google Scholar citation count into data/citations.json."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

SCHOLAR_ID = "XLziKuQAAAAJ"
URL = f"https://scholar.google.com/citations?user={SCHOLAR_ID}&hl=en"
OUT = Path("data/citations.json")


def parse_citations(html: str) -> int | None:
    patterns = [
        r'class="gsc_rsb_std">(\d[\d,]*)</td>',
        r'id="gsc_rsb_st"[\s\S]*?gsc_rsb_std[^>]*>(\d[\d,]*)',
        r">Citations</a></td><td[^>]*>(\d[\d,]*)",
    ]
    for pat in patterns:
        matches = re.findall(pat, html, flags=re.I)
        if matches:
            return int(matches[0].replace(",", ""))
    return None


def fetch_html() -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    cookie = os.environ.get("GOOGLE_SCHOLAR_COOKIE", "").strip()
    if cookie:
        headers["Cookie"] = cookie

    # Prefer Chrome TLS impersonation when available (helps on CI IPs).
    try:
        from curl_cffi import requests as cffi_requests

        resp = cffi_requests.get(URL, headers=headers, impersonate="chrome120", timeout=45)
        resp.raise_for_status()
        return resp.text
    except Exception as exc:
        print(f"curl_cffi fetch failed ({exc!r}); falling back to urllib", file=sys.stderr)

    import urllib.request

    req = urllib.request.Request(URL, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def main() -> int:
    soft_fail = "--soft-fail" in sys.argv
    try:
        html = fetch_html()
    except Exception as exc:
        msg = f"Failed to fetch Google Scholar page: {exc}"
        if soft_fail:
            print(msg, file=sys.stderr)
            return 0
        print(msg, file=sys.stderr)
        return 1

    blocked = any(
        s in html.lower()
        for s in (
            "unusual traffic",
            "automated queries",
            "captcha",
            "please show you're not a robot",
        )
    )
    citations = parse_citations(html)
    if citations is None:
        debug = Path("data/scholar_debug.html")
        debug.parent.mkdir(parents=True, exist_ok=True)
        debug.write_text(html[:20000], encoding="utf-8")
        msg = "Could not parse Google Scholar citations"
        if blocked:
            msg += " (page looks blocked/captcha)"
        msg += f"; wrote debug HTML to {debug}"
        if soft_fail:
            print(msg, file=sys.stderr)
            return 0
        print(msg, file=sys.stderr)
        return 1

    payload = {
        "scholar_id": SCHOLAR_ID,
        "citations": citations,
        "updated": date.today().isoformat(),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
