#!/usr/bin/env python3
"""Fetch /public/exchange/mat-details from the Galactic Tycoons API and save a timestamped snapshot."""
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_BASE_URL = "https://api.g2.galactictycoons.com"
ENDPOINT = "/public/exchange/mat-details"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "mat-details"


def fetch(api_key: str) -> dict:
    req = urllib.request.Request(
        f"{API_BASE_URL}{ENDPOINT}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main() -> int:
    api_key = os.environ.get("GALACTIC_TYCOONS_API_KEY")
    if not api_key:
        print("GALACTIC_TYCOONS_API_KEY is not set", file=sys.stderr)
        return 1

    try:
        data = fetch(api_key)
    except urllib.error.HTTPError as e:
        print(f"API request failed: HTTP {e.code} {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"API request failed: {e.reason}", file=sys.stderr)
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    out_path = DATA_DIR / f"{timestamp}.json"
    out_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
