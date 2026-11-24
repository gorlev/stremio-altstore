# Stremio Unofficial AltStore Source

[![Update source](https://github.com/gorlev/stremio-altstore/actions/workflows/update.yml/badge.svg)](https://github.com/gorlev/stremio-altstore/actions/workflows/update.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stremio iOS versions](https://img.shields.io/badge/iOS-12%20versions-7055D9)](stremio-ios.json)
[![Stremio tvOS versions](https://img.shields.io/badge/tvOS-12%20versions-7055D9)](stremio-tvos.json)

An unofficial AltStore-format source for Stremio on iOS, iPadOS and tvOS, usable by any signing app that reads the standard AltStore source format.

Stremio's official source at [`dl.strem.io/apple/altstore/source.json`](https://dl.strem.io/apple/altstore/source.json) uses Apple's encrypted App Store Connect manifest format, which most third-party signing apps cannot parse. This repository publishes standard AltStore JSON sources that point at Stremio's plain IPA artifacts on the same CDN.

## Table of contents

- [Background](#background)
- [Compatible signing apps](#compatible-signing-apps)
- [Quick start](#quick-start)
- [Self-hosting](#self-hosting)
- [Available versions](#available-versions)
- [Release mirror](#release-mirror)
- [Automation](#automation)
- [Manual updates](#manual-updates)
- [Repository layout](#repository-layout)
- [Design notes](#design-notes)
- [Limitations](#limitations)
- [Contributing](#contributing)
- [License and attribution](#license-and-attribution)

## Background

Since June 2026, Stremio distributes its iOS builds through Apple's App Store Connect marketplace format. That format packages IPAs as encrypted variant chunks, ships a `manifest.json` metadata file, and grants the decryption key only to AltStore PAL. Signing apps such as Feather, ESign, Scarlet and Sideloadly cannot read it, so importing the official source yields "no apps", "invalid format" or "failed to download".

The plain IPA files remain publicly available on the same CDN:

```
https://dl.strem.io/apple/{X.Y.Z}b{buildN}/{ios|tvos}/stremio_{Platform}.ipa
```

This repository discovers those IPAs and writes them into standard AltStore-format JSON sources.

Related discussions:

- [Stremio #2384: Publish Stremio iOS on AltStore as an official source](https://github.com/Stremio/stremio-bugs/issues/2384)
- [Stremio blog: Sideloadable IPA release](https://blog.stremio.com/stremio-fully-featured-sideloadable-ipa-release-for-ios-ipados-apple-tv-tvos/)
- [@blksmr/altstore-stremio: the original unofficial source](https://github.com/blksmr/altstore-stremio)

## Compatible signing apps

Any app that accepts a source URL pointing to an `apps.json`-style document will work. Known-compatible apps:

| App | Type |
|---|---|
| [Feather](https://github.com/claration/Feather) | Open-source on-device signer |
| [AltStore Classic](https://altstore.io) | Desktop-paired signer, requires AltServer |
| [AltStore PAL](https://altstore.io) | EU alternative marketplace |
| [ESign](https://github.com/jakepoz/esign) | On-device signer |
| [Scarlet](https://usescarlet.com) | On-device IPA installer |
| [Sideloadly](https://sideloadly.io) | Desktop sideloader with source support |

If a signing app fails to parse these sources, please open an issue with the error message.

## Quick start

No fork is required. The source is hosted and updated automatically every six hours.

### One-tap install

Open the install page on your iPhone or iPad and select your app. The source opens prefilled:

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

GitHub strips `altstore://`-style links in this README, so the table links work only after being pasted into Safari. The button above routes through a landing page and works directly.

### Adding the URL manually

Paste the URL into the **Sources** or **Repositories** section of any signing app:

| Platform | Source URL |
|---|---|
| iOS / iPadOS | `https://gorlev.github.io/stremio-altstore/stremio-ios.json` |
| tvOS | `https://gorlev.github.io/stremio-altstore/stremio-tvos.json` |

Stremio then appears in the app's source list. Pick a version and select **Get** to download and sign it.

### Raw GitHub URLs

`sourceURL` also works with `raw.githubusercontent.com`:

```
https://raw.githubusercontent.com/gorlev/stremio-altstore/main/stremio-ios.json
https://raw.githubusercontent.com/gorlev/stremio-altstore/main/stremio-tvos.json
```

Some signing apps require a `Content-Type: application/json` header. GitHub Pages always sends it, raw URLs occasionally do not, so the `gorlev.github.io` URLs are preferred.

## Self-hosting

To run your own copy with its own URL and schedule:

1. Fork this repository.
2. Enable Pages under **Settings > Pages > Source: Deploy from a branch > Branch: `main` / `(root)`**. The sources become available at `https://<username>.github.io/stremio-altstore/stremio-{ios,tvos}.json`.
3. Point `sourceURL` at your fork:
   ```bash
   python3 stremio-updater.py \
     --source-url-ios  "https://<username>.github.io/stremio-altstore/stremio-ios.json" \
     --source-url-tvos "https://<username>.github.io/stremio-altstore/stremio-tvos.json"
   ```
4. Commit the change. The bundled GitHub Actions workflow keeps the fork updated every six hours.

## Available versions

<!-- BEGIN:AVAILABLE_VERSIONS -->

### iOS / iPadOS: `stremio-ios.json`

#### Stremio (PAL, full-featured): `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.1.3 | 28 | 2026-11-23 | 84.2 MB | [IPA](https://dl.strem.io/apple/2.1.3b28/ios/stremio_iOS.ipa) |
| 2.1.2 | 27 | 2026-11-17 | 84.2 MB | [IPA](https://dl.strem.io/apple/2.1.2b27/ios/stremio_iOS.ipa) |
| 2.1.1 | 25 | 2026-10-31 | 80.8 MB | [IPA](https://dl.strem.io/apple/2.1.1b25/ios/stremio_iOS.ipa) |
| 2.1.0 | 24 | 2026-10-21 | 80.8 MB | [IPA](https://dl.strem.io/apple/2.1.0b24/ios/stremio_iOS.ipa) |
| 2.0.8 | 23 | 2026-09-10 | 74.9 MB | [IPA](https://dl.strem.io/apple/2.0.8b23/ios/stremio_iOS.ipa) |
| 2.0.7 | 22 | 2026-08-24 | 75.1 MB | [IPA](https://dl.strem.io/apple/2.0.7b22/ios/stremio_iOS.ipa) |
| 2.0.6 | 21 | 2026-07-22 | 72.4 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 72.7 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/ios/stremio_iOS.ipa) |
| 2.0.4 | 19 | 2026-07-10 | 72.7 MB | [IPA](https://dl.strem.io/apple/2.0.4b19/ios/stremio_iOS.ipa) |
| 2.0.3 | 18 | 2026-07-09 | 72.7 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/ios/stremio_iOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 74.4 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/ios/stremio_iOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 74.1 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/ios/stremio_iOS.ipa) |

### tvOS: `stremio-tvos.json`

#### Stremio (PAL, full-featured): `com.stremio.pal`

| Version | Build | Date | Size | Download |
|---|---|---|---|---|
| 2.1.3 | 28 | 2026-11-23 | 74.5 MB | [IPA](https://dl.strem.io/apple/2.1.3b28/tvos/stremio_tvOS.ipa) |
| 2.1.2 | 27 | 2026-11-17 | 74.4 MB | [IPA](https://dl.strem.io/apple/2.1.2b27/tvos/stremio_tvOS.ipa) |
| 2.1.1 | 25 | 2026-10-31 | 71.3 MB | [IPA](https://dl.strem.io/apple/2.1.1b25/tvos/stremio_tvOS.ipa) |
| 2.1.0 | 24 | 2026-10-21 | 71.3 MB | [IPA](https://dl.strem.io/apple/2.1.0b24/tvos/stremio_tvOS.ipa) |
| 2.0.8 | 23 | 2026-09-10 | 70.6 MB | [IPA](https://dl.strem.io/apple/2.0.8b23/tvos/stremio_tvOS.ipa) |
| 2.0.7 | 22 | 2026-08-24 | 70.6 MB | [IPA](https://dl.strem.io/apple/2.0.7b22/tvos/stremio_tvOS.ipa) |
| 2.0.6 | 21 | 2026-07-22 | 70.6 MB | [IPA](https://dl.strem.io/apple/2.0.6b21/tvos/stremio_tvOS.ipa) |
| 2.0.5 | 20 | 2026-07-22 | 70.6 MB | [IPA](https://dl.strem.io/apple/2.0.5b20/tvos/stremio_tvOS.ipa) |
| 2.0.3 | 18 | 2026-07-09 | 70.6 MB | [IPA](https://dl.strem.io/apple/2.0.3b18/tvos/stremio_tvOS.ipa) |
| 2.0.2 | 17 | 2026-06-19 | 70.2 MB | [IPA](https://dl.strem.io/apple/2.0.2b17/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 16 | 2026-06-16 | 70.2 MB | [IPA](https://dl.strem.io/apple/2.0.1b16/tvos/stremio_tvOS.ipa) |
| 2.0.1 | 15 | 2026-06-15 | 70.2 MB | [IPA](https://dl.strem.io/apple/2.0.1b15/tvos/stremio_tvOS.ipa) |

<!-- END:AVAILABLE_VERSIONS -->

The tables above are generated from the JSON sources by `scripts/render_readme.py` on every update. Do not edit them by hand.

Every entry is verified against the IPA's `Info.plist`, fetched with HTTP Range requests (under 5 KB per IPA). Bundle identifiers, version strings and `MinimumOSVersion` values are read directly from the IPAs.

## Release mirror

Every build listed in the sources is also mirrored to this repository's [Releases](https://github.com/gorlev/stremio-altstore/releases), one release per version and build:

```
v2.1.3b28
├── stremio_iOS.ipa      unmodified upstream IPA
├── stremio_tvOS.ipa     unmodified upstream IPA
└── SHA256SUMS.txt       the same hashes the JSON sources publish
```

The IPAs are Stremio's own files, byte for byte. Nothing here is built, repackaged or re-signed, and the mirror exists with Stremio's go-ahead. The sources keep pointing at `dl.strem.io`, so ordinary installs still come from upstream and the traffic stays on their CDN.

The mirror addresses a different problem: a URL on someone else's CDN is the one part of this source that can disappear without warning. Builds do get pulled, and the previous answer was to drop the version and strand whoever was running it. The mirrored bytes survive the pull.

Verify any download against the manifest in its release:

```bash
shasum -a 256 -c SHA256SUMS.txt
```

These are the same `sha256` values the JSON sources carry, so a signing app that checks integrity accepts either copy.

Two rules keep the mirror trustworthy:

- A build is mirrored only after the source has recorded its `sha256`, so `add_hashes.py` always runs first. Publishing bytes the source cannot vouch for would make the mirror less trustworthy than the CDN it mirrors.
- The hash is recomputed from the bytes as they download, and a mismatch aborts that release instead of filling it. A mismatch means upstream replaced the file at the same URL, which is what the weekly audit's `add_hashes.py --reverify` repairs.

`.github/workflows/mirror.yml` runs after each successful updater run and mirrors a couple of releases at a time (roughly 170 MB each), so the backlog drains over a few runs and every new build is mirrored in the cycle it appears. A build that exists for only one platform gets one IPA, and its release says so. Trimming a version out of the JSON does not delete its release.

To mirror manually (requires an authenticated `gh` CLI):

```bash
make mirror                      # next couple of builds
make mirror DRY=1                # show the plan, download nothing
make mirror VERSION=2.1.3b28     # one specific build
python3 scripts/mirror_release.py --check   # coverage report
```

## Automation

`.github/workflows/update.yml` runs `stremio-updater.py` every six hours, discovers new Stremio versions, updates the JSON files and commits the result. With Pages enabled, new versions reach signing apps within minutes.

To enable the workflow: **Actions > Update Stremio source > Enable workflow**. To run it on demand: **Actions > Update Stremio source > Run workflow**.

### Publish gate

Each run starts with the test suite (`python3 -m unittest discover -s scripts -p 'test_*.py'`, under a second, no network). It covers the parts whose failure would be silent rather than loud: the ZIP/plist parser that reads `minOSVersion` from a remote IPA, the safety rails on the script that deletes versions, the version-discovery logic that once missed a release for five consecutive runs, and the publish gate itself.

Nothing is pushed before `scripts/validate_source.py` passes. Five scripts write to these JSON files and whatever lands here reaches users within minutes, so the gate checks more than well-formed JSON:

- every `downloadURL` must be HTTPS on Stremio's own CDN, because a sideloading source must never send people elsewhere for an unsigned IPA
- bundle identifiers must be unique within a source
- `sourceURL` must name its own file
- no app may be published with zero versions
- sizes, dates and `sha256` values must be plausible

A failure fails the job and publishes nothing. `scripts/test_validate_source.py` corrupts a known-good source one field at a time to prove the gate still fires.

### Per-run steps

- **Release notes.** `scripts/fetch_release_notes.py` copies each build's changelog from Stremio's own AltStore source. That source carries only the newest couple of builds, so this runs on the same cadence to catch each changelog before it rolls out of the window, and never drops one it has already captured. Builds released before this existed keep a generated placeholder unless an Internet Archive capture of the same upstream URL still holds the changelog; the weekly audit mines those to fill gaps and never overwrites a captured note.
- **Legacy field mirroring.** The AltStore format has two generations: modern clients read each app's `versions` array, while AltStore Classic and several forks read flat `version`, `versionDescription` and `downloadURL` fields on the app itself. `scripts/sync_legacy_fields.py` keeps both in step so older clients show the real changelog instead of a fallback string. The publish gate rejects a mirror that disagrees with the newest version, since old and new clients installing different builds from one entry is worse than shipping no legacy fields.
- **Liveness proof.** The install page asks GitHub when this workflow last succeeded and displays it, for example "Checked 2 hours ago". If the automation stalls, the indicator turns amber and then red instead of reassuring people about an unmaintained source.
- **News feed.** Signing apps render a source's `news` array in-app, so `scripts/build_news.py` turns each captured changelog into an item linking back to the app entry. Only the newest release may request a push notification, and only while it is genuinely fresh, so publishing or rebuilding the feed never fires a burst of notifications. Identifiers are derived from the release alone, so a client notifies at most once. The publish gate enforces both rules.
- **Integrity hashes.** `scripts/add_hashes.py` computes the `sha256` of a few IPAs per run, newest first and budget-limited so it never risks the job's time limit, until every version carries a hash that signing apps can verify against.
- **README tables.** Regenerated from the JSON.

### Weekly audit

The updater only looks for new builds, so `.github/workflows/audit.yml` runs weekly to catch the rest:

- **Dead downloads.** `scripts/prune_dead.py` sends a HEAD request to every listed IPA and removes entries whose build has been pulled, so nobody is left tapping a link that 404s. It is deliberately cautious: only 404 and 410 count, never a timeout or 5xx; each result is re-checked; and it prunes nothing if the newest version is missing or if many die at once, since that pattern indicates a CDN change rather than individual pulls. Dropping an app with no working versions left is a human decision.
- **Retention.** `scripts/trim_versions.py` keeps the version list from growing without bound. It retains the newest dozen builds and never drops a build that is the last option for a given `minOSVersion` or the last of a release line, so housekeeping cannot strand a device on an older OS. Nothing is trimmed on the current list; the policy matters as it grows.
- **Screenshots.** `scripts/fetch_screenshots.py` copies the App Store screenshots from Stremio's own source so entries show a gallery rather than a bare name and icon. Upstream publishes only iPhone and iPad shots, so the tvOS source is left without any instead of showing phone screenshots for a TV app.
- **Metadata drift.** `scripts/verify_bundle_ids.py` reads each IPA's real `Info.plist` and compares the bundle identifier, version, build and `MinimumOSVersion` against what the JSON claims. It corrects `minOSVersion` in place, since the IPA is the authority and the field only advertises compatibility. A mismatched bundle identifier, version or build defines the entry's identity, so those are reported for a human instead.

Anything requiring a decision opens a single deduplicated GitHub issue.

### CDN canary

`scripts/check_cdn.py` runs on the six-hour schedule. The updater exits successfully whether it finds new versions or none, so a changed URL scheme, an outage or a pulled build would otherwise be invisible. The canary sends a HEAD request to the newest known IPA for each platform and opens a deduplicated GitHub issue if the source may be serving dead downloads.

## Manual updates

```bash
git clone https://github.com/gorlev/stremio-altstore.git
cd stremio-altstore

# Optional virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Dry run: report what would change, write nothing
python3 stremio-updater.py --dry-run --verbose

# Real update
python3 stremio-updater.py

# Parse Info.plist for unknown IPAs to verify bundle identifiers (slower)
python3 stremio-updater.py --info-plist

# One platform only
python3 stremio-updater.py --platform ios
python3 stremio-updater.py --platform tvos

# Update sourceURL fields
python3 stremio-updater.py \
  --source-url-ios  "https://<username>.github.io/stremio-altstore/stremio-ios.json" \
  --source-url-tvos "https://<username>.github.io/stremio-altstore/stremio-tvos.json"

git add stremio-ios.json stremio-tvos.json
git commit -m "chore: update Stremio source"
git push
```

Shorter aliases:

```bash
make help         # list all targets
make dry-run      # dry run
make update       # real update
make verify       # update with Info.plist verification
make set-urls     # set sourceURL fields interactively
```

## Repository layout

```
stremio-altstore/
├── stremio-ios.json            iOS / iPadOS source
├── stremio-tvos.json           tvOS source
├── stremio-updater.py          CDN scanner and JSON updater
├── ipa_plist.py                shared HTTP-Range IPA Info.plist parser
├── install.html                one-tap install landing page (GitHub Pages)
├── Makefile                    shortcut commands
├── README.md, CHANGELOG.md, CONTRIBUTING.md, SECURITY.md, LICENSE
├── .github/
│   ├── dependabot.yml          keeps the workflow actions current
│   ├── workflows/
│   │   ├── update.yml          auto-update every 6 hours, plus CDN canary
│   │   ├── audit.yml           weekly dead-IPA prune and metadata verify
│   │   └── mirror.yml          mirrors each build into a GitHub Release
│   └── ISSUE_TEMPLATE/
└── scripts/
    ├── verify_bundle_ids.py    standalone IPA Info.plist verifier
    ├── render_readme.py        regenerates the version tables above
    ├── add_hashes.py           backfills sha256 integrity hashes (budgeted)
    ├── mirror_release.py       mirrors IPAs into GitHub Releases (budgeted)
    ├── check_cdn.py            CDN health canary
    ├── prune_dead.py           removes versions whose IPA returns 404
    ├── trim_versions.py        retention policy for the version list
    ├── fetch_release_notes.py  captures each release's changelog
    ├── fetch_screenshots.py    captures App Store screenshots (weekly)
    ├── build_news.py           turns changelogs into the in-app news feed
    ├── sync_legacy_fields.py   mirrors newest build for older AltStore clients
    ├── validate_source.py      publish gate
    ├── test_ipa_plist.py       ZIP/plist parser, against real archives
    ├── test_prune_dead.py      safety rails on the deleting script
    ├── test_updater_logic.py   version discovery and merge invariants
    ├── test_mirror_release.py  what gets mirrored, and what must not
    ├── test_derived_data.py    README render, legacy mirror, notes, hashes
    └── test_validate_source.py proves the publish gate fires
```

## Design notes

### Why two JSON files

Stremio ships the same bundle identifier, `com.stremio.pal`, on iOS and tvOS. Most signing apps reject two apps with the same `bundleIdentifier` inside one source, so the platforms are split:

- `stremio-ios.json` covers iPhone and iPad (`com.stremio.pal`, `com.stremio.ios`)
- `stremio-tvos.json` covers Apple TV (`com.stremio.pal`, `com.stremio.ios`)

Both can be added to the same signing app; the relevant one appears per device type.

### How the updater works

1. `scan_cdn` probes `dl.strem.io/apple/{semver}b{build}/{ios|tvos}/...` URLs in parallel with a 16-worker `ThreadPoolExecutor`, covering the last known build plus a buffer range.
2. `get_main_app_info_plist` fetches only the relevant chunks of the IPA with HTTP Range requests (ZIP EOCD, central directory, compressed `Info.plist`) and parses the binary or XML plist with `plistlib`. Typical transfer is under 5 KB per IPA. Framework and appex `Info.plist` entries are filtered out, keeping the main app.
3. `process_platform` adds discovered versions to the JSON or refreshes the metadata of existing ones, keeping versions sorted by version and build, descending.

## Limitations

- **Unofficial.** Stremio does not support this source and can change IPA URLs or shut down the CDN at any time.
- **Signature expiry.** Builds signed with a free Apple ID expire after 7 days; a paid developer account lasts 1 year. Re-signing happens through your signing app.
- **Missing features.** Per Stremio's blog, some features such as Apple Login and Handoff do not work in sideloaded builds: "these features cannot be available within sideloadable apps".
- **CDN dependency.** If Stremio changes its `dl.strem.io` infrastructure, this repository breaks. Run `stremio-updater.py --dry-run` periodically to check.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Particularly useful:

- reporting versions the updater missed, as an issue or a pull request
- bug fixes, especially parse errors and edge cases
- documentation: translations, clarifications, examples
- compatibility testing with other signing apps, including parse errors to fix

For security issues, see [SECURITY.md](SECURITY.md).

## License and attribution

Licensed under the [MIT License](LICENSE).

- Stremio is a trademark of SmartCode OOD. This repository is not affiliated with, endorsed by or sponsored by Stremio or SmartCode OOD.
- AltStore and the source format are defined by [AltStore](https://altstore.io).
- Feather is an open-source project by [@claration](https://github.com/claration/Feather).
- Original unofficial source inspiration: [@blksmr/altstore-stremio](https://github.com/blksmr/altstore-stremio).
