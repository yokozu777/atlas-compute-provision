#!/usr/bin/env python3
"""Download one Golden PVE cloud image, falling back when the primary stalls.

Primary is probed, then streamed. If it is unreachable, the connection drops,
or no new bytes arrive for the stall window, an optional backup URL is used.
An empty backup keeps the primary failure. SSL verification is off, matching
get_url validate_certs: false.
"""
from __future__ import annotations

import json
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_cloud_image import probe  # noqa: E402


class DownloadError(Exception):
    pass


class Stalled(DownloadError):
    pass


def _basename(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(path.rsplit("/", 1)[-1] if path else "")
    if not name or name in (".", ".."):
        raise DownloadError(f"cloud image URL has no filename: {url}")
    return name


def download(url: str, dest: Path, overall: int, stall: int) -> None:
    """Stream url to dest. Remove a partial file if the transfer stalls or fails."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    if dest.exists():
        dest.unlink()
    if partial.exists():
        partial.unlink()
    started = time.monotonic()
    last = started
    written = 0
    read_timeout = min(30, max(1, stall))
    headers = {"User-Agent": "atlas-compute-provision"}
    req = urllib.request.Request(url, method="GET", headers=headers)
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=read_timeout, context=ctx) as resp:
            code = int(getattr(resp, "status", None) or resp.getcode())
            if code not in (200, 206):
                raise DownloadError(f"HTTP {code}")
            with partial.open("wb") as out:
                while True:
                    now = time.monotonic()
                    if now - started > overall:
                        raise DownloadError(f"exceeded {overall}s")
                    try:
                        chunk = resp.read(64 * 1024)
                    except (TimeoutError, socket.timeout):
                        if time.monotonic() - last >= stall:
                            raise Stalled(f"no bytes for {stall}s")
                        continue
                    if not chunk:
                        break
                    out.write(chunk)
                    written += len(chunk)
                    last = time.monotonic()
        if written <= 0:
            raise DownloadError("empty response")
        partial.replace(dest)
    except urllib.error.HTTPError as exc:
        exc.close()
        raise DownloadError(f"HTTP {exc.code}") from exc
    except Stalled:
        raise
    except DownloadError:
        raise
    except Exception as exc:
        raise DownloadError(str(exc)) from exc
    finally:
        if partial.exists():
            partial.unlink()


def fetch(
    dest_dir: Path,
    primary: str,
    probe_timeout: int,
    stall: int,
    overall: int,
    backup: str = "",
) -> dict[str, str]:
    """Save primary, or backup when primary is down or stalls. Return the chosen URL."""
    primary = (primary or "").strip()
    backup = (backup or "").strip()
    if not primary:
        raise SystemExit("Cloud image URL is empty")
    if probe_timeout < 1 or stall < 1 or overall < 1:
        raise SystemExit("timeouts must be >= 1")
    urls = [primary]
    if backup and backup != primary:
        urls.append(backup)
    errors: list[str] = []
    for index, url in enumerate(urls):
        try:
            probe(url, probe_timeout)
        except SystemExit as exc:
            errors.append(str(exc))
            continue
        dest = dest_dir / _basename(url)
        try:
            download(url, dest, overall, stall)
        except Exception as exc:
            if dest.exists():
                dest.unlink()
            errors.append(f"Cloud image download failed: {url}: {exc}")
            if index == 0 and len(urls) > 1:
                continue
            break
        return {"image_url": url, "image_file": dest.name}
    raise SystemExit("; ".join(errors) or f"Cloud image is not downloadable: {primary}")


def main() -> None:
    if len(sys.argv) not in (6, 7):
        raise SystemExit(
            "usage: download_cloud_image.py DEST_DIR PRIMARY PROBE_TIMEOUT STALL OVERALL [BACKUP]"
        )
    dest_dir = Path(sys.argv[1])
    primary = sys.argv[2]
    try:
        probe_timeout = int(sys.argv[3])
        stall = int(sys.argv[4])
        overall = int(sys.argv[5])
    except ValueError as exc:
        raise SystemExit("timeouts must be integers") from exc
    backup = sys.argv[6] if len(sys.argv) == 7 else ""
    chosen = fetch(dest_dir, primary, probe_timeout, stall, overall, backup)
    print(json.dumps(chosen))


if __name__ == "__main__":
    main()
