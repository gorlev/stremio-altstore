#!/usr/bin/env python3
"""
add_hashes.py — backfill SHA-256 integrity hashes into the JSON sources

For a sideload source, an integrity hash lets signing apps verify that the
IPA they downloaded matches what this source vouches for. The AltStore
source format carries this as an optional `sha256` field on each version.

A hash can only be computed by reading the full IPA (~72 MB), so this runs
as a *budgeted* backfill, completely decoupled from stremio-updater.py:

  * It only ever ADDS a `sha256` field to versions that don't have one.
  * The updater refreshes version metadata in place, so it never strips a
    hash this script wrote — the two are safe to run in either order.
  * Each run downloads at most `--budget` IPAs (newest first), so the set
    of existing versions gets hashed over a few runs instead of one heavy
    pass, and thereafter only brand-new versions need a download.

A hash was also, until now, written once and never looked at again. That is
the one way this field can turn from a safety net into an outage: if Stremio
replaces an IPA at the same URL, the recorded hash stops matching the file
and every client that verifies it refuses the download — and nothing here
would notice. `--reverify` closes that: it HEADs each hashed version and
compares Content-Length against the recorded size. A file that changed size
has been replaced, so its stale hash is dropped (and the size corrected) and
the normal backfill recomputes it on the next run.

That check is deliberately cheap — a HEAD per version instead of 72 MB — so
it has one blind spot worth naming: a rebuild that lands on byte-identical
length would slip past it. Catching that needs a real re-download, which is
what the budgeted backfill does for anything whose hash has been dropped.

Usage:
    python3 scripts/add_hashes.py                 # backfill up to the budget
    python3 scripts/add_hashes.py --budget 2       # override the per-run budget
    python3 scripts/add_hashes.py --dry-run        # list what would be hashed
    python3 scripts/add_hashes.py --check          # report coverage, no writes
    python3 scripts/add_hashes.py --reverify       # re-check hashes against the CDN

Budget resolution: --budget arg > SHA256_BUDGET env > default (4).

Exit codes:
    0 — ran successfully (including "nothing to do")
    1 — --check mode and at least one version is still missing a hash
    2 — --reverify found a replaced IPA and dropped its stale hash
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from ipa_plist import http_request  # noqa: E402  (shared HTTP helper)

SOURCES = ["stremio-ios.json", "stremio-tvos.json"]
DEFAULT_BUDGET = 4
USER_AGENT = "stremio-altstore/add_hashes/1.0"
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _has_valid_hash(v: dict) -> bool:
    h = v.get("sha256")
    return isinstance(h, str) and bool(HEX64.match(h))


def _version_key(v: dict) -> tuple:
    parts = [int(c) if c.isdigit() else -1 for c in str(v.get("version", "")).split(".")]
    try:
        build = int(v.get("buildVersion", 0))
    except (TypeError, ValueError):
        build = 0
    return (parts, build)


def _missing(sources: dict[str, dict]) -> list[dict]:
    """All versions lacking a valid hash, newest first, with locating context."""
    items: list[dict] = []
    for fname, data in sources.items():
        for app in data.get("apps", []):
            for v in app.get("versions", []):
                if not _has_valid_hash(v) and v.get("downloadURL"):
                    items.append({
                        "file": fname,
                        "app": app.get("name", "?"),
                        "version": v.get("version", "?"),
                        "build": v.get("buildVersion", "?"),
                        "url": v["downloadURL"],
                        "size": v.get("size"),
                        "_obj": v,
                        "_key": _version_key(v),
                    })
    items.sort(key=lambda it: it["_key"], reverse=True)
    return items


def _set_sha256(v: dict, digest: str) -> None:
    """Insert `sha256` right after `size` for a tidy, stable diff."""
    rebuilt: dict = {}
    for k, val in v.items():
        if k == "sha256":
            continue
        rebuilt[k] = val
        if k == "size":
            rebuilt["sha256"] = digest
    if "sha256" not in rebuilt:  # no `size` key present — append
        rebuilt["sha256"] = digest
    v.clear()
    v.update(rebuilt)


def _reverify(sources: dict[str, dict], *, dry_run: bool = False) -> tuple[int, set[str]]:
    """Re-check every recorded hash against the file now on the CDN.

    Compares the live Content-Length with the recorded size. A version whose
    IPA has been replaced gets its stale hash dropped and its size corrected,
    so the budgeted backfill recomputes the hash on a later run rather than
    leaving a wrong one in place for clients to reject.

    Returns (number of stale hashes found, files that need writing).
    """
    stale = 0
    changed: set[str] = set()
    unreachable = 0
    checked = 0

    print("=== Re-verifying recorded hashes against the CDN ===")
    for fname, data in sources.items():
        for app in data.get("apps", []):
            for v in app.get("versions", []):
                if not _has_valid_hash(v) or not v.get("downloadURL"):
                    continue
                label = (f"{fname}: {app.get('name')} {v.get('version')} "
                         f"build {v.get('buildVersion')}")
                resp = http_request(v["downloadURL"], method="HEAD", timeout=20)
                if resp.status != 200:
                    # Not a verdict — prune_dead.py owns deciding what is gone.
                    print(f"  [????] {label} → HTTP {resp.status}, skipped")
                    unreachable += 1
                    continue
                checked += 1
                live = int(resp.headers.get("Content-Length") or 0)
                recorded = v.get("size")
                if live and recorded and live != recorded:
                    stale += 1
                    changed.add(fname)
                    print(f"  [STALE] {label}: recorded {recorded} bytes, CDN now serves "
                          f"{live} — the IPA was replaced, so the stored hash is wrong")
                    if not dry_run:
                        v.pop("sha256", None)
                        v["size"] = live
                        print("          dropped sha256 and corrected size; "
                              "the backfill will re-hash it")
                else:
                    print(f"  [ok  ] {label}")

    print(f"\nRe-verified {checked} hashed version(s): {stale} stale, "
          f"{unreachable} unreachable.")
    return stale, changed


def _hash_url(url: str, *, timeout: int = 90, chunk: int = 1 << 20) -> dict:
    """Stream the IPA and compute its SHA-256 without holding it in memory."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    h = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if getattr(r, "status", 200) != 200:
                return {"ok": False, "error": f"HTTP {getattr(r, 'status', '?')}"}
            while True:
                buf = r.read(chunk)
                if not buf:
                    break
                h.update(buf)
                total += len(buf)
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return {"ok": False, "error": str(e)}
    if total == 0:
        return {"ok": False, "error": "empty body"}
    return {"ok": True, "sha256": h.hexdigest(), "bytes": total}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=None,
                    help="Max IPAs to download this run (default: SHA256_BUDGET env or 4)")
    ap.add_argument("--dry-run", action="store_true", help="List what would be hashed, download nothing")
    ap.add_argument("--check", action="store_true", help="Report coverage only; exit 1 if any hash is missing")
    ap.add_argument("--reverify", action="store_true",
                    help="Re-check recorded hashes against the CDN and drop any that went stale")
    args = ap.parse_args()

    sources = {f: json.loads((REPO / f).read_text(encoding="utf-8")) for f in SOURCES}
    total_versions = sum(len(a.get("versions", [])) for d in sources.values() for a in d.get("apps", []))
    missing = _missing(sources)
    have = total_versions - len(missing)

    print(f"[INFO] SHA-256 coverage: {have}/{total_versions} versions hashed, {len(missing)} missing.")

    if args.reverify:
        stale, changed = _reverify(sources, dry_run=args.dry_run)
        if not stale:
            print("[OK] Every recorded hash still describes the file on the CDN.")
            return 0
        if args.dry_run:
            print(f"[DRY-RUN] {stale} stale hash(es) would be dropped.")
            return 2
        for fname in sorted(changed):
            (REPO / fname).write_text(
                json.dumps(sources[fname], indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(f"[WRITE] {fname} updated")
        print(f"[DONE] Dropped {stale} stale hash(es); the backfill will recompute them.")
        return 2

    if args.check:
        for it in missing:
            print(f"  [MISSING] {it['file']} · {it['app']} {it['version']} (build {it['build']})")
        return 1 if missing else 0

    if not missing:
        print("[OK] Every version already has a hash. Nothing to do.")
        return 0

    budget = args.budget if args.budget is not None else int(os.environ.get("SHA256_BUDGET", DEFAULT_BUDGET))
    todo = missing[:max(0, budget)]

    if args.dry_run:
        print(f"[DRY-RUN] Would hash {len(todo)} IPA(s) this run (budget {budget}):")
        for it in todo:
            print(f"  - {it['file']} · {it['app']} {it['version']} (build {it['build']}) → {it['url']}")
        return 0

    changed_files: set[str] = set()
    done = 0
    for it in todo:
        print(f"[HASH] {it['app']} {it['version']} (build {it['build']}) — downloading {it['url']}")
        res = _hash_url(it["url"])
        if not res["ok"]:
            print(f"  [WARN] skipped ({res['error']}) — will retry next run")
            continue
        # Cross-check the byte count against the recorded size. The hash and
        # the size must describe the same file: recording a hash of the live
        # download while leaving a stale size behind is how a source ends up
        # self-contradicting, so correct the size too.
        if it["size"] and res["bytes"] != it["size"]:
            print(f"  [WARN] size mismatch: recorded {it['size']}, downloaded {res['bytes']} "
                  f"— recording the live file's hash and correcting the size")
            it["_obj"]["size"] = res["bytes"]
        _set_sha256(it["_obj"], res["sha256"])
        changed_files.add(it["file"])
        done += 1
        print(f"  [OK] sha256={res['sha256']}")

    for fname in sorted(changed_files):
        (REPO / fname).write_text(
            json.dumps(sources[fname], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[WRITE] {fname} updated")

    remaining = len(missing) - done
    print(f"[DONE] Hashed {done} this run. {remaining} still missing "
          f"(will be filled on the next {remaining and 'run(s)' or 'run'}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
