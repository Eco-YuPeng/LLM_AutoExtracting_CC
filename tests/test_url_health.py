"""
API endpoint health checks for data_catalog.yml's external_apis list.

Sends a lightweight request to each base_url to verify reachability.
NEVER fails the test suite — collects and reports dead endpoints as
warnings only.

Run separately with: pytest tests/test_url_health.py -v -s
"""

import sys
from pathlib import Path

import pytest
import requests
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

CATALOG = Path(__file__).parent.parent / "data_catalog.yml"
REQUEST_TIMEOUT = 20  # seconds


def load_api_base_urls():
    """Return list of (name, base_url) tuples from data_catalog.yml's
    external_apis list. Entries without a base_url (endpoint not yet
    confirmed) are skipped, not failed."""
    with open(CATALOG) as f:
        catalog = yaml.safe_load(f)
    return [
        (entry["name"], entry["base_url"])
        for entry in catalog.get("external_apis", [])
        if entry.get("base_url")
    ]


def check_url(url: str) -> tuple[bool, str]:
    try:
        r = requests.head(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"},
                           allow_redirects=True)
        if r.status_code in (405, 501):
            r = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"},
                              allow_redirects=True, stream=True)
        return r.status_code < 400, f"HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.ConnectionError as e:
        return False, f"Connection error: {e}"
    except Exception as e:
        return False, str(e)


@pytest.mark.url_health
def test_all_catalog_apis_reachable():
    """Check every base_url in data_catalog.yml. Report failures but always pass.
    NOTE: this test requires open network access — it will report all
    endpoints as unreachable inside a sandboxed chat container. That is
    expected there, not a real failure; see AGENTS.md step 10."""
    apis = load_api_base_urls()
    failures = []
    for name, url in apis:
        ok, message = check_url(url)
        status = "OK" if ok else "DEAD"
        print(f"  [{status}] {name}: {url}  ({message})")
        if not ok:
            failures.append(f"  {name}: {url}  ({message})")

    if failures:
        print(f"\n⚠  {len(failures)} unreachable endpoint(s) — "
              f"expected inside a sandboxed container, investigate otherwise:\n")
        for f in failures:
            print(f)

    assert True  # report-only, never fail the suite
