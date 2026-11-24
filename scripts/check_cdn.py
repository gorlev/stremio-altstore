#!/usr/bin/env python3
"""
check_cdn.py — canary for silent updater failure

The whole value of this repo is "always current". But the updater exits 0
whether it found new versions or found nothing — so a broken CDN (URL
scheme change, outage, or a pulled build) looks identical to "no news".
This canary makes that distinction observable.

Two independent signals, derived only from the committed JSON sources:

  1. Reachability (CRITICAL): the newest known IPA for each platform must
     still return HTTP 200. If it doesn't, either the CDN moved or the build
     was pulled — either way the source is likely serving a dead download.

  2. Freshness (WARNING): if the newest version is older than the staleness
     threshold, we may be silently missing releases. This is a soft signal
     (Stremio genuinely goes quiet sometimes), so it never fails the run.

Usage:
    python3 scripts/check_cdn.py                 # check both sources
    python3 scripts/check_cdn.py --max-age-days 60

Thresholds: --max-age-days arg > CDN_MAX_AGE_DAYS env > default (45).

Exit codes:
    0 — healthy (warnings allowed)
    2 — CRITICAL: at least one newest IPA is unreachable
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ipa_plist import http_request  # noqa: E402  (reuse the shared HTTP helper)

SOURCES = ["stremio-ios.json", "stremio-tvos.json"]
DEFAULT_MAX_AGE_DAYS = 45


def _newest(data: dict) -> dict | None:
    """Newest version across all apps in a source, by (version, build)."""
    best = None
    best_key = None
    for app in data.get("apps", []):
        for v in app.get("versions", []):
            parts = [int(c) if c.isdigit() else -1 for c in str(v.get("version", "")).split(".")]
            try:
                build = int(v.get("buildVersion", 0))
            except (TypeError, ValueError):
                build = 0
            key = (parts, build)
            if best_key is None or key > best_key:
                best_key, best = key, v
    return best


def _age_days(date_str: str) -> int | None:
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return (date.today() - d).days


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-age-days", type=int, default=None,
                    help="Freshness warning threshold (default: CDN_MAX_AGE_DAYS env or 45)")
    args = ap.parse_args()
    max_age = args.max_age_days if args.max_age_days is not None \
        else int(os.environ.get("CDN_MAX_AGE_DAYS", DEFAULT_MAX_AGE_DAYS))

    critical: list[str] = []
    warnings: list[str] = []
    # Both sources point at the same icon; fetch it once.
    seen_icons: dict[str, int] = {}

    print("=== CDN health check ===")
    for fname in SOURCES:
        path = REPO / fname
        if not path.exists():
            critical.append(f"{fname}: file not found")
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        v = _newest(data)
        if not v:
            warnings.append(f"{fname}: no versions listed")
            print(f"  {fname}: (no versions)")
            continue

        label = f"{v.get('version')} build {v.get('buildVersion')}"
        url = v.get("downloadURL", "")
        resp = http_request(url, method="HEAD", timeout=15)
        status = resp.status
        reach_ok = status == 200
        line = f"  {fname}: newest {label} → HTTP {status}"

        age = _age_days(v.get("date", ""))
        if age is not None:
            line += f", {age}d old"
        print(line)

        if not reach_ok:
            critical.append(f"{fname}: newest IPA {label} unreachable (HTTP {status}) — {url}")

        # The source's icon is what every signing app shows next to the entry.
        # It is cosmetic, so a dead icon is a warning rather than a failure —
        # but it has to be visible: the previous icon URL 404'd silently for
        # an unknown length of time because nothing here ever looked at it.
        icon = data.get("iconURL")
        if isinstance(icon, str) and icon:
            if icon in seen_icons:
                icon_status = seen_icons[icon]
            else:
                icon_status = http_request(icon, method="HEAD", timeout=15).status
                seen_icons[icon] = icon_status
            print(f"  {fname}: iconURL → HTTP {icon_status}")
            if icon_status != 200:
                warnings.append(f"{fname}: iconURL unreachable (HTTP {icon_status}) — "
                                f"signing apps will show a broken icon — {icon}")
        if age is not None and age > max_age:
            warnings.append(f"{fname}: newest version {label} is {age} days old (> {max_age}d threshold) — "
                            f"scanner may be missing releases, or Stremio has not shipped")

    print()
    for w in warnings:
        print(f"[WARN] {w}")
    for c in critical:
        print(f"[CRITICAL] {c}")

    if critical:
        print("\nResult: CRITICAL — the source may be serving dead downloads or the CDN layout changed.")
        return 2
    if warnings:
        print("\nResult: OK with warnings.")
        return 0
    print("\nResult: healthy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
