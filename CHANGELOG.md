# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Routine `chore: update Stremio source` commits — new builds discovered by the
updater — are not listed individually; the [version tables](README.md#available-versions)
are the record for those.

## [Unreleased]

Everything here is live on the published sources. The theme of this stretch was
turning a scanner that found new builds into something that also keeps the
source honest: verifying what it publishes, noticing when it breaks, and saying
enough about each build for someone to choose one.

### Added

- **Release mirror** — every listed build is also published as a GitHub Release
  (`v2.1.3b28`: both IPAs plus a `shasum -c`-compatible `SHA256SUMS.txt`), with
  Stremio's go-ahead and byte-identical to their CDN copy. The sources still
  point at `dl.strem.io`, so installs and traffic stay upstream; the mirror is
  there for the day a build is pulled, which until now could only be answered by
  dropping the version and stranding whoever ran it. A build is mirrored only
  after the source records its `sha256`, and the hash is recomputed while
  downloading — a mismatch aborts that release rather than filling it with bytes
  no client would accept.
- **One-tap install page** (`install.html`, served from GitHub Pages) — no fork
  needed. Loads its data live from the JSON, so it is never out of date: latest
  build per platform, full version history, `altstore://` / `sidestore://` deep
  links, and copyable source URLs.
- **SHA-256 integrity hashes** on every version, computed by downloading each
  IPA in full, a few per run. `SECURITY.md` documents how to verify a download.
- **Real release notes per version**, captured from Stremio's own source while
  it still publishes them (it only shows the newest couple of builds), with
  older ones recovered from Internet Archive captures where they exist.
- **In-app news feed** (`news`), which signing apps render inside the app. At
  most one item may raise a push notification, and only while the release is
  genuinely fresh, so rebuilding the feed never produces a burst of pushes.
- **App Store screenshots**, copied from upstream. tvOS is deliberately left
  without any: upstream publishes only iPhone and iPad shots, and phone
  screenshots would misrepresent a TV app.
- **Legacy app-level fields** (`version`, `versionDescription`, `downloadURL`, …)
  so AltStore Classic and forks that read the older schema show release notes
  instead of falling back to the app name and build number.
- **Publish gate** (`scripts/validate_source.py`), run before every commit in
  CI. If the result is not a valid, safe source, nothing is published.
- **Test suite** — 134 tests, no network, under a second, run by both workflows.
  It concentrates on logic whose failure would be silent: the byte-level
  IPA/ZIP parser, the rails on the scripts that delete data, and version
  discovery.
- **Weekly source audit** (`.github/workflows/audit.yml`) — prunes builds whose
  IPA now 404s, verifies JSON metadata against each IPA's own `Info.plist`, and
  opens a single deduplicated issue when something needs a human decision.
- **CDN health canary**, because the updater exits successfully whether it finds
  new builds or finds nothing; a changed URL scheme would otherwise be invisible.
- **Retention policy** for the version list, which never drops a build that is
  the last option for a given `minOSVersion` or release line.
- **Auto-generated README version tables** and count badges, rebuilt from the
  JSON on every update.
- **Dependabot** for the workflow actions.

### Changed

- The updater now always reads each IPA's `Info.plist`, so `minOSVersion` is the
  real value rather than a hardcoded default.
- Version discovery derives candidates from the versions already listed and also
  seeds from Stremio's own source, replacing a hand-written candidate list.
- Sizes are shown to one decimal place everywhere (`72.4 MB`); flooring made
  72.7 MB and 72.4 MB read identically.
- Workflow actions updated to their Node 24-native releases.
- Comments and log output are English throughout.

### Fixed

- **Releases were being missed.** Candidate versions came from a list written
  when 2.0.2 was current, so 2.0.6b21 shipped and five scheduled runs never even
  requested its URL. Reported via an issue.
- The same blind spot on the build axis: a build far enough ahead of the local
  window could never be probed, leaving discovery stuck on an old maximum.
- **`minOSVersion` drift** — three tvOS builds advertised 13.0 while their IPAs
  require 15.0, telling tvOS 13/14 users an incompatible build would run.
- **Release notes were invisible in AltStore Classic**, which reads flat
  app-level fields this source never emitted.
- Two overlapping workflow runs could race to push; runs are now serialized and
  the push rebases and retries.
- The install page overflowed on iPhone — a grid item cannot shrink below its
  min-content width, which Chromium clips and iOS Safari does not.

### Removed

- **Stremio Lite** (`com.stremio.ios`). Stremio pulled its only build from the
  CDN, so both sources advertised an app that could not be installed.

### Security

- Every `downloadURL` must be **https on `dl.strem.io`**, enforced by the publish
  gate as an allowlist rather than a convention: a sideloading source that sends
  people elsewhere for an unsigned IPA is the worst thing this repo could ship.
- Release notes and screenshots are copied from a third party, so they are
  sanitised on the way in, length-capped, and rendered without HTML
  interpretation.

## [1.0.0] — 2026-06-23

### Added
- `stremio-ios.json` — AltStore-format source for iOS / iPadOS
  - Stremio PAL (full-featured) — `com.stremio.pal`, 6 versions (2.0.0b11 → 2.0.2b17)
  - Stremio Lite (legacy) — `com.stremio.ios`, 1 version (1.3.6b7)
- `stremio-tvos.json` — Separate AltStore-format source for Apple TV
  - Stremio PAL — `com.stremio.pal`, 3 versions (2.0.1b15 → 2.0.2b17)
  - Stremio Lite — `com.stremio.ios`, 1 version (1.3.6b7)
- `stremio-updater.py` — `dl.strem.io` CDN scanner
  - Parallel HEAD requests (ThreadPoolExecutor, 16 workers)
  - HTTP Range-based IPA Info.plist extraction (XML + binary plist, via `plistlib`)
  - Main-app Info.plist filtering (excludes framework and appex entries)
  - Scans known + plausible upcoming semver/build combinations
- `.github/workflows/update.yml` — Auto-update every 6 hours
- `.github/ISSUE_TEMPLATE/` — Bug, feature, source-broken, and question templates
- `Makefile` — Shortcut commands (`make update`, `make dry-run`, etc.)
- `scripts/verify_bundle_ids.py` — Standalone IPA Info.plist verifier
- Bundle identifier, version, build, and `MinimumOSVersion` values verified against IPA Info.plist
- Compatibility with all signing apps that consume the standard AltStore source format (Feather, AltStore Classic, AltStore PAL, ESign, Scarlet, Sideloadly, and others)

### Notes
- Stremio's official `dl.strem.io/apple/altstore/source.json` source cannot be parsed by most third-party signing apps because it uses Apple's encrypted App Store Connect manifest format. This repo is an unofficial port that points to the plain IPAs available on the same CDN.
- Two separate JSON files are used because Stremio uses the same bundle identifier (`com.stremio.pal`) on both iOS and tvOS, and most signing apps do not allow two apps with the same `bundleIdentifier` inside one source.

<!-- No git tags or GitHub releases exist yet, so these point at commits. -->
[Unreleased]: https://github.com/gorlev/stremio-altstore/compare/8099dad...main
[1.0.0]: https://github.com/gorlev/stremio-altstore/commit/8099dad
