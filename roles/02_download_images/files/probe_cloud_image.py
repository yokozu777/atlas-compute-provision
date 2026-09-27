#!/usr/bin/env python3
"""Fail unless a Golden PVE cloud image URL starts serving bytes.

Reads at most a small prefix so a multi-gigabyte object is not downloaded twice.
SSL verification is off, matching get_url validate_certs: false on the download.
"""
from __future__ import annotations

import ssl
import sys
import urllib.error
import urllib.request

_RANGE = "bytes=0-1023"
_READ = 64


def _fetch(url: str, timeout: int, ranged: bool) -> tuple[int, bytes]:
    headers = {"User-Agent": "atlas-compute-provision"}
    if ranged:
        headers["Range"] = _RANGE
    req = urllib.request.Request(url, method="GET", headers=headers)
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        code = int(getattr(resp, "status", None) or resp.getcode())
        return code, resp.read(_READ)


def probe(url: str, timeout: int) -> str:
    try:
        code, chunk = _fetch(url, timeout, ranged=True)
    except urllib.error.HTTPError as exc:
        exc.close()
        if exc.code not in (400, 416):
            raise SystemExit(
                f"Cloud image is not downloadable: {url}: HTTP {exc.code}"
            ) from exc
        try:
            code, chunk = _fetch(url, timeout, ranged=False)
        except urllib.error.HTTPError as retry_exc:
            raise SystemExit(
                f"Cloud image is not downloadable: {url}: HTTP {retry_exc.code}"
            ) from retry_exc
        except Exception as retry_exc:
            raise SystemExit(
                f"Cloud image is not downloadable: {url}: {retry_exc}"
            ) from retry_exc
    except Exception as exc:
        raise SystemExit(f"Cloud image is not downloadable: {url}: {exc}") from exc
    if code not in (200, 206):
        raise SystemExit(f"Cloud image is not downloadable: {url}: HTTP {code}")
    if not chunk:
        raise SystemExit(f"Cloud image is not downloadable: {url}: empty response")
    return f"reachable HTTP {code} {url}"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: probe_cloud_image.py URL TIMEOUT")
    url = sys.argv[1].strip()
    if not url:
        raise SystemExit("Cloud image URL is empty")
    try:
        timeout = int(sys.argv[2])
    except ValueError as exc:
        raise SystemExit("timeout must be an integer") from exc
    if timeout < 1:
        raise SystemExit("timeout must be >= 1")
    print(probe(url, timeout))


if __name__ == "__main__":
    main()
