#!/usr/bin/env python3
"""
test_validate_source.py — proves the publish gate actually fires

A validator nobody tests is worse than no validator: it gives the pipeline
permission to publish. Each case here corrupts a known-good source in one
specific way and asserts that validation fails, so a future refactor cannot
quietly turn the gate off.

Run:
    python3 scripts/test_validate_source.py        # or: python3 -m unittest discover scripts
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from validate_source import Report, validate_source  # noqa: E402

GOOD = {
    "name": "Stremio iOS (Unofficial AltStore Source)",
    "identifier": "com.gorlev.stremio-ios",
    "sourceURL": "https://gorlev.github.io/stremio-altstore/stremio-ios.json",
    "iconURL": "https://gorlev.github.io/stremio-altstore/stremio-icon-512.png",
    "apps": [
        {
            "name": "Stremio",
            "bundleIdentifier": "com.stremio.pal",
            "screenshots": ["https://example.com/a.png"],
            "versions": [
                {
                    "version": "2.0.6",
                    "buildVersion": "21",
                    "date": "2026-07-22",
                    "downloadURL": "https://dl.strem.io/apple/2.0.6b21/ios/stremio_iOS.ipa",
                    "size": 75942223,
                    "sha256": "3ff786e83de059293d57378a742c4b70d069fa745133b5f909ea0e060dabf10d",
                    "minOSVersion": "13.0",
                },
                {
                    "version": "2.0.5",
                    "buildVersion": "20",
                    "date": "2026-07-22",
                    "downloadURL": "https://dl.strem.io/apple/2.0.5b20/ios/stremio_iOS.ipa",
                    "size": 76251082,
                    "sha256": "791f09fe5f" + "0" * 54,
                    "minOSVersion": "13.0",
                },
            ],
        }
    ],
    "news": [],
}


def run(doc: dict, filename: str = "stremio-ios.json") -> Report:
    """Validate an in-memory source document and return the report."""
    rep = Report()
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / filename
        p.write_text(json.dumps(doc), encoding="utf-8")
        validate_source(rep, p)
    return rep


class GoodSource(unittest.TestCase):
    def test_clean_source_passes(self):
        rep = run(copy.deepcopy(GOOD))
        self.assertEqual(rep.errors, [], f"clean source should pass, got {rep.errors}")


class Corruptions(unittest.TestCase):
    """Each case must produce at least one error."""

    def assert_rejected(self, doc: dict, needle: str, filename: str = "stremio-ios.json"):
        rep = run(doc, filename)
        self.assertTrue(rep.errors, "expected validation to fail, but it passed")
        joined = " | ".join(rep.errors).lower()
        self.assertIn(needle.lower(), joined,
                      f"expected an error mentioning {needle!r}, got: {rep.errors}")

    def test_corrupted_size(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["size"] = 1
        self.assert_rejected(d, "implausibly small")

    def test_download_url_off_cdn(self):
        # The one that matters most: never send people off-CDN for an unsigned IPA.
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["downloadURL"] = "https://evil.example.com/stremio.ipa"
        self.assert_rejected(d, "not allowed")

    def test_download_url_plain_http(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["downloadURL"] = "http://dl.strem.io/a.ipa"
        self.assert_rejected(d, "https")

    def test_duplicate_bundle_identifier(self):
        d = copy.deepcopy(GOOD)
        d["apps"].append(copy.deepcopy(d["apps"][0]))
        self.assert_rejected(d, "duplicates")

    def test_app_with_no_versions(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"] = []
        self.assert_rejected(d, "no versions")

    def test_build_version_as_number(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["buildVersion"] = 21
        self.assert_rejected(d, "buildversion must be a non-empty string")

    def test_swapped_source_url(self):
        d = copy.deepcopy(GOOD)
        d["sourceURL"] = "https://gorlev.github.io/stremio-altstore/stremio-tvos.json"
        self.assert_rejected(d, "expected 'stremio-ios.json'")

    def test_bad_sha256(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["sha256"] = "NOTAHASH"
        self.assert_rejected(d, "sha256")

    def test_duplicate_version_build(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"].append(copy.deepcopy(d["apps"][0]["versions"][0]))
        self.assert_rejected(d, "duplicate")

    def test_missing_apps(self):
        d = copy.deepcopy(GOOD)
        d["apps"] = []
        self.assert_rejected(d, "non-empty list")

    def test_bad_date(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["date"] = "22-07-2026"
        self.assert_rejected(d, "yyyy-mm-dd")

    def test_description_with_control_characters(self):
        # Release notes are harvested from upstream, so the gate must not
        # wave through raw bytes that a renderer could choke on.
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["localizedDescription"] = "feat: nice\x00\x07 thing"
        self.assert_rejected(d, "control characters")

    def test_description_absurdly_long(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["localizedDescription"] = "x" * 20000
        self.assert_rejected(d, "over the")

    def test_description_wrong_type(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"][0]["localizedDescription"] = {"text": "nope"}
        self.assert_rejected(d, "must be a string")

    def test_screenshot_over_plain_http_is_rejected(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["screenshots"] = ["http://cdn.example.com/a.jpg"]
        self.assert_rejected(d, "https")

    def test_screenshot_of_the_wrong_shape_is_rejected(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["screenshots"] = {"iphone": [{"nope": "https://cdn/a.jpg"}]}
        self.assert_rejected(d, "imageURL")

    def test_device_keyed_screenshots_are_accepted(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["screenshots"] = {
            "iphone": ["https://cdn.example.com/a.jpg"],
            "ipad": [{"imageURL": "https://cdn.example.com/b.jpg", "width": 2048, "height": 2732}],
        }
        rep = run(d)
        self.assertEqual(rep.errors, [], rep.errors)

    def test_two_notifying_news_items_are_rejected(self):
        # The spam failure mode: several pushes at once.
        d = copy.deepcopy(GOOD)
        d["news"] = [
            {"title": "A", "identifier": "a", "caption": "c", "date": "2026-07-22", "notify": True},
            {"title": "B", "identifier": "b", "caption": "c", "date": "2026-07-21", "notify": True},
        ]
        self.assert_rejected(d, "at most one")

    def test_duplicate_news_identifier_is_rejected(self):
        # A repeated identifier can make a client re-notify for a seen story.
        d = copy.deepcopy(GOOD)
        d["news"] = [
            {"title": "A", "identifier": "same", "caption": "c", "date": "2026-07-22", "notify": False},
            {"title": "B", "identifier": "same", "caption": "c", "date": "2026-07-21", "notify": False},
        ]
        self.assert_rejected(d, "already used")

    def test_news_appid_must_point_at_an_app_in_this_source(self):
        d = copy.deepcopy(GOOD)
        d["news"] = [{"title": "A", "identifier": "a", "caption": "c", "date": "2026-07-22",
                      "notify": False, "appID": "com.example.ghost"}]
        self.assert_rejected(d, "not an app in this source")

    def test_news_notify_must_be_boolean(self):
        d = copy.deepcopy(GOOD)
        d["news"] = [{"title": "A", "identifier": "a", "caption": "c", "date": "2026-07-22",
                      "notify": "yes"}]
        self.assert_rejected(d, "notify must be")

    def test_valid_news_item_passes(self):
        d = copy.deepcopy(GOOD)
        d["news"] = [{"title": "Stremio 2.0.6", "identifier": "stremio-2-0-6", "caption": "feat: x",
                      "tintColor": "7055D9", "date": "2026-07-22", "notify": True,
                      "appID": "com.stremio.pal",
                      "imageURL": "https://cdn.example.com/icon.png"}]
        rep = run(d)
        self.assertEqual(rep.errors, [], rep.errors)

    def test_malformed_json(self):
        rep = Report()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "stremio-ios.json"
            p.write_text("{ this is not json", encoding="utf-8")
            validate_source(rep, p)
        self.assertTrue(any("not valid json" in e.lower() for e in rep.errors), rep.errors)


def with_legacy(doc: dict) -> dict:
    """Add the legacy app-level mirror the way sync_legacy_fields.py would."""
    app = doc["apps"][0]
    newest = app["versions"][0]
    app.update({
        "version": newest["version"],
        "versionDate": newest["date"],
        "versionDescription": newest.get("localizedDescription", "notes"),
        "downloadURL": newest["downloadURL"],
        "size": newest["size"],
        "minOSVersion": newest["minOSVersion"],
    })
    return doc


class LegacyMirror(unittest.TestCase):
    """Old clients read flat app-level fields; they must agree with versions[0]."""

    def test_correct_mirror_passes(self):
        d = with_legacy(copy.deepcopy(GOOD))
        d["apps"][0]["versions"][0]["localizedDescription"] = "feat: something real"
        d["apps"][0]["versionDescription"] = "feat: something real"
        rep = run(d)
        self.assertEqual(rep.errors, [], rep.errors)

    def test_mirror_pointing_at_a_different_build_is_rejected(self):
        # The dangerous case: old clients would install a different IPA
        # than new ones from the same entry.
        d = with_legacy(copy.deepcopy(GOOD))
        d["apps"][0]["downloadURL"] = "https://dl.strem.io/apple/2.0.5b20/ios/stremio_iOS.ipa"
        rep = run(d)
        self.assertTrue(any("does not match the newest version" in e for e in rep.errors), rep.errors)

    def test_partial_mirror_is_rejected(self):
        d = with_legacy(copy.deepcopy(GOOD))
        del d["apps"][0]["versionDescription"]
        rep = run(d)
        self.assertTrue(any("versionDescription" in e for e in rep.errors), rep.errors)

    def test_absent_mirror_only_warns(self):
        # A source without legacy fields is still valid, just less compatible.
        rep = run(copy.deepcopy(GOOD))
        self.assertEqual(rep.errors, [], rep.errors)
        self.assertTrue(any("legacy app-level fields" in w for w in rep.warnings), rep.warnings)


class Warnings(unittest.TestCase):
    def test_missing_sha256_warns_but_passes(self):
        d = copy.deepcopy(GOOD)
        del d["apps"][0]["versions"][0]["sha256"]
        rep = run(d)
        self.assertEqual(rep.errors, [], "a missing hash must not block publishing")
        self.assertTrue(any("sha256" in w.lower() for w in rep.warnings), rep.warnings)

    def test_unsorted_versions_warn_but_pass(self):
        d = copy.deepcopy(GOOD)
        d["apps"][0]["versions"].reverse()
        rep = run(d)
        self.assertEqual(rep.errors, [])
        self.assertTrue(any("newest-first" in w for w in rep.warnings), rep.warnings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
