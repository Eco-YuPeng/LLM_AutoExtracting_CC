#!/usr/bin/env python3
"""Validate dataset URLs before writing a workflow script.

Performs a lightweight HEAD request (falls back to a partial GET) on each URL
to check that it is reachable and returns actual data — not an HTML portal
page or login screen.

Usage:
    python scripts/check_urls.py <url1> <url2> ...

Exit code 0 if ALL urls are valid, 1 if ANY failed.

Example:
    python scripts/check_urls.py \
        https://minedbuildings.z5.web.core.windows.net/legacy/usbuildings-v2/Colorado.geojson.zip \
        https://prod-explorer.coloradoforestatlas.org/ShareFileManager?id=3125bd23

Output:
    OK   https://minedbuildings...Colorado.geojson.zip (application/zip, 82.3 MB)
    FAIL https://prod-explorer...?id=3125bd23
         HTML page returned — this is a portal link, not a direct download URL.
         Ask the user for a direct download URL.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request


def check_url(url: str) -> tuple[bool, str]:
    """Check a single URL. Returns (ok, message)."""
    headers = {"User-Agent": "Mozilla/5.0"}

    # OPeNDAP URLs (THREDDS dodsC) don't respond to normal GET/HEAD.
    # Request the .dds suffix (dataset descriptor — lightweight metadata).
    if "dodsC" in url:
        dds_url = url.split("?")[0].rstrip("/") + ".dds"
        request = urllib.request.Request(dds_url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return True, "OPeNDAP endpoint (verified via .dds)"
        except urllib.error.HTTPError as e:
            return False, f"OPeNDAP endpoint not reachable: HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"OPeNDAP endpoint not reachable: {e.reason}"
        except Exception as e:
            return False, f"OPeNDAP endpoint not reachable: {e}"

    # Try HEAD first (fast, no body download)
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                content_length = response.headers.get("Content-Length")

                if "text/html" in content_type:
                    return False, (
                        "HTML page returned — this is a portal link, not a direct download URL.\n"
                        "         Ask the user for a direct download URL."
                    )

                # Build size string
                if content_length:
                    size_mb = int(content_length) / 1_048_576
                    if size_mb >= 1:
                        size_str = f"{size_mb:.1f} MB"
                    else:
                        size_str = f"{int(content_length)} bytes"
                else:
                    size_str = "unknown size"

                ct_short = content_type.split(";")[0].strip() or "unknown type"
                return True, f"{ct_short}, {size_str}"

        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405):
                # Some servers reject HEAD — retry with GET
                continue
            return False, f"HTTP Error {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"Connection error: {e.reason}"
        except Exception as e:
            return False, f"Error: {e}"

    return False, "Could not reach URL"


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2

    any_failed = False
    for url in argv:
        ok, msg = check_url(url)
        if ok:
            print(f"OK   {url} ({msg})")
        else:
            any_failed = True
            print(f"FAIL {url}")
            print(f"         {msg}")

    if any_failed:
        print("\nSome URLs failed. Do NOT use broken URLs in the workflow script.")
        print("Ask the user for working direct download URLs before proceeding.")

    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
