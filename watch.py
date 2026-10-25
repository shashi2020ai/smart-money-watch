#!/usr/bin/env python3
"""
Smart Money Watch: checks SEC EDGAR for new 13F filings from the managers in managers.json and writes status.json.

Runs on GitHub Actions (see .github/workflows/watch.yml). Standard library only. Everything it reads and writes is
public SEC data: manager names, CIKs, and filing accession numbers / dates.

  SEC_EMAIL   contact email for the SEC User-Agent (a GitHub secret; SEC requires one on every request)
  --force     run even outside the filing window
"""
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
WINDOW_DAYS = (30, 47)          # days after quarter end during which filings arrive: checked daily
HISTORY_QUARTERS = 6
MIN_GAP = 1 / 8                 # SEC allows 10 requests/second; stay well under
_last = [0.0]


def quarter_ends(today, n):
    """The n most recent quarter-end dates on or before today, newest first."""
    out, y = [], today.year
    for yy in range(y, y - 4, -1):
        for md in ("12-31", "09-30", "06-30", "03-31"):
            d = date.fromisoformat(f"{yy}-{md}")
            if d <= today:
                out.append(d)
    return out[:n]


def in_window(today):
    q = quarter_ends(today, 1)[0]
    return WINDOW_DAYS[0] <= (today - q).days <= WINDOW_DAYS[1]


def should_run(today, force=False):
    """Daily inside the filing window, otherwise once a week (Mondays)."""
    return force or in_window(today) or today.weekday() == 0


def fetch(url, ua):
    delay = 2.0
    for attempt in range(5):
        wait = _last[0] + MIN_GAP - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Encoding": "identity"})
            with urllib.request.urlopen(req, timeout=45) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(delay)
        delay = min(delay * 2, 30)
    raise RuntimeError(f"gave up on {url}")


def filings_for(cik, since, ua):
    sub = fetch(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", ua)
    r = sub["filings"]["recent"]
    out = []
    for i, form in enumerate(r["form"]):
        if form in ("13F-HR", "13F-HR/A", "13F-NT") and r["reportDate"][i] and r["reportDate"][i] >= since:
            out.append({"cik": f"{int(cik):010d}", "accession": r["accessionNumber"][i], "form": form,
                        "filed": r["filingDate"][i], "period": r["reportDate"][i]})
    return out


def build_status(managers, today, ua, fetch_filings=filings_for):
    periods = quarter_ends(today, HISTORY_QUARTERS)
    since = periods[-1].isoformat()
    active = [m for m in managers if m.get("active")]
    result = {}
    for m in active:
        seen = {}
        for cik in [m["cik"]] + list(m.get("alias_ciks") or []):
            for f in fetch_filings(cik, since, ua):
                seen[f["accession"]] = f
        result[m["id"]] = {"name": m["name"], "filings": sorted(seen.values(), key=lambda f: (f["period"], f["filed"]), reverse=True)}
    quarters = []
    for p in periods[:2]:
        have = [mid for mid, v in result.items() if any(f["period"] == p.isoformat() and f["form"].startswith("13F-HR") for f in v["filings"])]
        quarters.append({"period": p.isoformat(), "received": len(have), "total": len(active),
                         "missing": [result[m["id"]]["name"] for m in active if m["id"] not in have]})
    return {"managers": result, "quarters": quarters}


def stable_hash(status):
    """Hash of the content that matters (not the timestamps), so we only report a change when filings change."""
    return hashlib.sha256(json.dumps({"managers": status["managers"], "quarters": status["quarters"]}, sort_keys=True).encode()).hexdigest()[:16]


def main(argv):
    force = "--force" in argv
    today = datetime.now(timezone.utc).date()
    if not should_run(today, force):
        print(f"{today}: outside the filing window and not Monday - nothing to do")
        return 0
    email = os.environ.get("SEC_EMAIL", "").strip()
    if "@" not in email:
        print("SEC_EMAIL is not set (add it under Settings > Secrets and variables > Actions)", file=sys.stderr)
        return 1
    managers = json.loads((HERE / "managers.json").read_text())
    status = build_status(managers, today, f"Options Position Analysis {email}")
    status["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    status["in_filing_window"] = in_window(today)
    status["content_hash"] = stable_hash(status)
    path = HERE / "status.json"
    path.write_text(json.dumps(status, indent=1, sort_keys=True) + "\n")
    q = status["quarters"][0]
    print(f"{q['period']}: {q['received']}/{q['total']} managers have filed; content {status['content_hash']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
