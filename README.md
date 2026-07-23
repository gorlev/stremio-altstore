# Stremio — Unofficial AltStore Source

[![Update source](https://github.com/gorlev/stremio-altstore/actions/workflows/update.yml/badge.svg)](https://github.com/gorlev/stremio-altstore/actions/workflows/update.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stremio iOS versions](https://img.shields.io/badge/iOS-11%20versions-7055D9)](stremio-ios.json)
[![Stremio tvOS versions](https://img.shields.io/badge/tvOS-7%20versions-7055D9)](stremio-tvos.json)

An **unofficial** AltStore-format source collection for Stremio iOS and tvOS, compatible with any signing app that consumes the standard AltStore source format — Feather, AltStore Classic, AltStore PAL, ESign, Scarlet, Sideloadly, and others. Stremio's official source at [`dl.strem.io/apple/altstore/source.json`](https://dl.strem.io/apple/altstore/source.json) cannot be parsed by most third-party signing apps because it uses Apple's encrypted App Store Connect manifest format — this repo publishes standard AltStore-format JSON sources that point to Stremio's plain IPA artifacts.

## Table of contents

- [Why does this repo exist?](#why-does-this-repo-exist)
- [Compatible signing apps](#compatible-signing-apps)
- [Quick start](#quick-start)
- [Self-host your own copy](#self-host-your-own-copy)
- [Available versions](#available-versions)
- [Automatic updates](#automatic-updates)
- [Manual updates](#manual-updates)
- [Architecture](#architecture)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License and attribution](#license-and-attribution)

---

## Why does this repo exist?

Starting in June 2026, Stremio moved iOS distribution entirely to Apple's **App Store Connect marketplace** format. This format:

1. Packages IPAs as encrypted variant chunks
2. Distributes a `manifest.json` metadata file
3. Grants the decryption key only to AltStore PAL

Most third-party signing apps (Feather, ESign, Scarlet, Sideloadly, etc.) cannot break this encryption, so importing the official source results in "no apps", "invalid format", or "failed to download" errors.

However, Stremio keeps the plain IPA files **publicly available on the same CDN**:

```
https://dl.strem.io/apple/{X.Y.Z}b{buildN}/{ios|tvos}/stremio_{Platform}.ipa
```

This repo discovers those IPAs and writes them into standard AltStore-format JSON sources.

> 📜 Related discussions:
> - [Stremio #2384 — Publish Stremio iOS on AltStore as an official source](https://github.com/Stremio/stremio-bugs/issues/2384)
> - [Stremio blog — Sideloadable IPA Release](https://blog.stremio.com/stremio-fully-featured-sideloadable-ipa-release-for-ios-ipados-apple-tv-tvos/)
> - [@blksmr — original unofficial source](https://github.com/blksmr/altstore-stremio)

---

## Compatible signing apps

Any signing app that consumes the standard AltStore source format can use this repo. Tested or known-compatible apps include:

- **[Feather](https://github.com/claration/Feather)** — open-source on-device signer
- **[AltStore Classic](https://altstore.io)** — the original desktop-paired signer (requires AltServer on a Mac/PC)
- **[AltStore PAL](https://altstore.io)** — AltStore's European Union alternative marketplace
- **[ESign](https://github.com/jakepoz/esign)** — popular on-device signer
- **[Scarlet](https://usescarlet.com)** — on-device IPA installer
- **[Sideloadly](https://sideloadly.io)** — desktop-based sideloader with source support

If your signing app supports adding a source by URL pointing to an `apps.json`-style document, it will work. If you find an app that does not work, please open an issue.

---

## Quick start

**No fork required.** This source is already hosted and auto-updated every 6 hours. Just add it to your signing app.

### One-tap install

Open this page **on your iPhone / iPad** and tap your app — the source opens prefilled:

<p align="center">
  <a href="https://gorlev.github.io/stremio-altstore/install.html">
    <img src="https://img.shields.io/badge/%E2%9E%95%20Add%20to%20AltStore%20%2F%20SideStore-one%20tap-7b5bf5?style=for-the-badge&logo=apple&logoColor=white" alt="Add to AltStore / SideStore" height="42" />
  </a>
</p>

Direct deep links (tap on-device, or paste into Safari):

| Platform | AltStore | SideStore |
|---|---|---|
| iOS / iPadOS | [Open in AltStore](altstore://source?url=https://gorlev.github.io/stremio-altstore/stremio-ios.json) | [Open in SideStore](sidestore://source?url=https://gorlev.github.io/stremio-altstore/stremio-ios.json) |
| tvOS | [Open in AltStore](altstore://source?url=https://gorlev.github.io/stremio-altstore/stremio-tvos.json) | [Open in SideStore](sidestore://source?url=https://gorlev.github.io/stremio-altstore/stremio-tvos.json) |

> GitHub strips `altstore://`-style links in this README, so the table links only work once pasted into Safari. The **Add to AltStore / SideStore** button above routes through a landing page and works directly.

### Or add the URL manually

Works with **any** signing app (Feather, AltStore Classic/PAL, ESign, Scarlet, Sideloadly…). Paste the URL into the app's **Sources** / **Repositories** section:

| Platform | Source URL |
|---|---|
| iOS / iPadOS | `https://gorlev.github.io/stremio-altstore/stremio-ios.json` |
| tvOS | `https://gorlev.github.io/stremio-altstore/stremio-tvos.json` |

Once added, Stremio appears in the app's source list. Pick a version and tap **Get** (or the equivalent) to download and sign.

### Alternative: raw GitHub URL (no Pages)

`sourceURL` also works with `raw.githubusercontent.com`:

```
https://raw.githubusercontent.com/gorlev/stremio-altstore/main/stremio-ios.json
https://raw.githubusercontent.com/gorlev/stremio-altstore/main/stremio-tvos.json
```

Some signing apps require the `Content-Type: application/json` header, which GitHub Pages guarantees; raw URLs occasionally delay that header — prefer the `gorlev.github.io` URLs above.

---

## Self-host your own copy

Prefer to run your own source (own URL, own update schedule)? Fork and host it in a couple of minutes:

1. **Fork** this repository.
2. Enable Pages: **Settings → Pages → Source: Deploy from a branch → Branch: `main` / `(root)`**. After a few minutes your sources are live at `https://<your-github-username>.github.io/stremio-altstore/stremio-{ios,tvos}.json`.
3. Point `sourceURL` at your fork:
   ```bash
   python3 stremio-updater.py \
     --source-url-ios  "https://<your-github-username>.github.io/stremio-altstore/stremio-ios.json" \
     --source-url-tvos "https://<your-github-username>.github.io/stremio-altstore/stremio-tvos.json"
   ```
4. Commit the change. The included GitHub Actions workflow keeps your fork updated every 6 hours.

---

## Available versions

<!-- BEGIN:AVAILABLE_VERSIONS -->

### iOS / iPadOS — `stremio-ios.json`

#### Stremio (PAL, full-featured) — `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.0.6 | 21 | 2026-07-22 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/ios/stremio_iOS.ipa) |
| 2.0.4 | 19 | 2026-07-10 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.4b19/ios/stremio_iOS.ipa) |
| 2.0.3 | 18 | 2026-07-09 | 72 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/ios/stremio_iOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/ios/stremio_iOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/ios/stremio_iOS.ipa) |
| 2.0.1 | 15 | 2026-06-15 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.1b15/ios/stremio_iOS.ipa) |
| 2.0.0 | 14 | 2026-06-05 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b14/ios/stremio_iOS.ipa) |
| 2.0.0 | 13 | 2026-06-05 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b13/ios/stremio_iOS.ipa) |
| 2.0.0 | 11 | 2026-05-30 | 74 MB | [IPA](https://dl.strem.io/apple/2.0.0b11/ios/stremio_iOS.ipa) |

#### Stremio Lite (legacy) — `com.stremio.ios`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 1.3.6 | 7 | 2026-01-31 | 75 MB | [IPA](https://dl.strem.io/apple/1.3.6b7/ios/stremio_iOS.ipa) |

### tvOS — `stremio-tvos.json`

#### Stremio (PAL, full-featured) — `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.0.6 | 21 | 2026-07-22 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/tvos/stremio_tvOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/tvos/stremio_tvOS.ipa) |
| 2.0.3 | 18 | 2026-07-09 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/tvos/stremio_tvOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 15 | 2026-06-15 | 70 MB | [IPA](https://dl.strem.io/apple/2.0.1b15/tvos/stremio_tvOS.ipa) |

#### Stremio Lite (legacy) — `com.stremio.ios`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 1.3.6 | 7 | 2026-01-31 | 73 MB | [IPA](https://dl.strem.io/apple/1.3.6b7/tvos/stremio_tvOS.ipa) |

<!-- END:AVAILABLE_VERSIONS -->

> 🤖 The tables above are auto-generated from the JSON sources by `scripts/render_readme.py` on every update — do not edit them by hand.

> 📦 Every version was verified against the IPA's Info.plist (downloaded via HTTP Range, < 5 KB each). Bundle identifiers, version strings, and `MinimumOSVersion` values were read directly from the IPAs.

---

## Automatic updates

The repo includes a GitHub Actions workflow that runs `stremio-updater.py` every 6 hours, discovers new Stremio versions, updates the JSON files, and auto-commits. With GitHub Pages enabled, new versions appear in your signing app within minutes.

Each run also, in the same job:

- **Backfills integrity hashes** — `scripts/add_hashes.py` computes the `sha256` of a few IPAs per run (newest first, budget-limited so it never risks the job's time limit), so every version eventually carries a hash that signing apps can verify the download against.
- **Regenerates the version tables** in this README from the JSON.

A separate **CDN health canary** (`scripts/check_cdn.py`) runs on the same schedule. Because the updater exits successfully whether it finds new versions or finds nothing, a broken CDN (a changed URL scheme, an outage, or a pulled build) would otherwise be invisible. The canary HEAD-checks the newest known IPA for each platform and **opens a GitHub issue** (deduplicated — one at a time) if the source may be serving dead downloads.

To enable the workflow: **Actions → Update Stremio source → Enable workflow**.

To trigger manually: **Actions → Update Stremio source → Run workflow**.

Configuration lives in `.github/workflows/update.yml`.

---

## Manual updates

```bash
# Clone the repo
git clone https://github.com/gorlev/stremio-altstore.git
cd stremio-altstore

# Virtual environment (optional but recommended)
python3 -m venv .venv && source .venv/bin/activate

# Dry run — see what would change without writing files
python3 stremio-updater.py --dry-run --verbose

# Real update — write changes to JSON files
python3 stremio-updater.py

# Parse Info.plist for unknown IPAs to verify bundle IDs (slower)
python3 stremio-updater.py --info-plist

# Only iOS (or only tvOS)
python3 stremio-updater.py --platform ios
python3 stremio-updater.py --platform tvos

# Update sourceURL fields
python3 stremio-updater.py \
  --source-url-ios  "https://<your-github-username>.github.io/stremio-altstore/stremio-ios.json" \
  --source-url-tvos "https://<your-github-username>.github.io/stremio-altstore/stremio-tvos.json"

# Commit and push
git add stremio-ios.json stremio-tvos.json
git commit -m "chore: update Stremio source"
git push
```

Shorter aliases via `make`:

```bash
make help         # List all targets
make dry-run      # Dry run
make update       # Real update
make verify       # Update with Info.plist verification
make set-urls     # Set sourceURL fields interactively
```

---

## Architecture

```
stremio-altstore/
├── README.md                   ← this file
├── LICENSE                     ← MIT
├── CHANGELOG.md                ← version history
├── CONTRIBUTING.md             ← contribution guide
├── SECURITY.md                 ← security policy
├── Makefile                    ← shortcut commands
├── .gitignore                  ← Python / macOS / IDE
├── stremio-ios.json            ← main source (iOS / iPadOS)
├── stremio-tvos.json           ← main source (tvOS)
├── stremio-updater.py          ← CDN scanner + JSON updater
├── ipa_plist.py                ← shared HTTP-Range IPA Info.plist parser
├── install.html                ← one-tap install landing page (GitHub Pages)
├── .github/
│   ├── workflows/
│   │   └── update.yml          ← auto-update every 6 hours + CDN canary
│   └── ISSUE_TEMPLATE/
│       ├── bug_report.yml
│       ├── feature_request.yml
│       └── source_broken.yml
└── scripts/
    ├── verify_bundle_ids.py    ← standalone IPA Info.plist verifier
    ├── render_readme.py        ← regenerates the version tables above
    ├── add_hashes.py           ← backfills sha256 integrity hashes (budgeted)
    └── check_cdn.py            ← CDN health canary (opens an issue if broken)
```

### Why two JSON files?

Stremio uses the **same bundle identifier** on both iOS and tvOS: `com.stremio.pal`. Most signing apps do not allow two apps with the same `bundleIdentifier` inside one source (signing/conflict reasons). That's why:

- `stremio-ios.json`  → iPhone / iPad (`com.stremio.pal` and `com.stremio.ios`)
- `stremio-tvos.json` → Apple TV (`com.stremio.pal` and `com.stremio.ios`, in separate sources — no conflict)

You can add both to your signing app; the appropriate one shows up per device type.

### How the updater works

1. **`scan_cdn`**: Probes `dl.strem.io/apple/{semver}b{build}/{ios|tvos}/...` URLs in parallel with a `ThreadPoolExecutor` (16 workers). Scans the last known build + buffer range.
2. **`get_main_app_info_plist`**: Fetches only the relevant chunks of the IPA via HTTP `Range` requests (ZIP EOCD + Central Directory + compressed Info.plist), parses binary or XML plist with `plistlib`. Typical download: < 5 KB per IPA. The function filters out framework and appex Info.plists, keeping only the main app entry.
3. **`process_platform`**: Adds discovered versions to the JSON or refreshes metadata of existing ones. Keeps versions sorted by (version, build) descending.

---

## Limitations

- **Unofficial** — Stremio does not support this source. It can change IPA URLs or shut down the CDN at any time.
- **Signature expiry** — Apps signed with a free Apple ID expire after **7 days**, with a paid developer account after **1 year**. You'll need to re-sign through your signing app.
- **Missing features** — Per Stremio's blog, some features (Apple Login, Handoff) don't work in sideloaded builds: *"these features cannot be available within sideloadable apps"*.
- **CDN dependency** — If Stremio changes its `dl.strem.io` infrastructure, this repo breaks. Run `updater.py --dry-run` periodically to verify.

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

Especially helpful:

- 🆕 **Reporting new versions** — open an Issue or PR if the updater missed one
- 🐛 **Bug fixes** — particularly parse errors and edge cases
- 📚 **Documentation** — README translations, clarifications, examples
- 🧪 **Testing** — compatibility with different signing apps
- 🆕 **Adding new signing app support** — if a signing app has trouble parsing our JSON, file an Issue with the parsing error message

For security issues please see [SECURITY.md](SECURITY.md).

---

## License and attribution

This repository is licensed under the [MIT License](LICENSE).

- **Stremio** is a trademark of SmartCode OOD. This repo is not affiliated with, endorsed by, or sponsored by Stremio or SmartCode OOD.
- **AltStore** and the source format are defined by [AltStore](https://altstore.io).
- **Feather** is an open-source project by [@claration](https://github.com/claration/Feather).
- Original unofficial source inspiration: [@blksmr/altstore-stremio](https://github.com/blksmr/altstore-stremio).

---

<p align="center">
  <sub>This source is maintained by the community, with love 🍿</sub>
</p>