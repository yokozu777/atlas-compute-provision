"""Cloud image download falls back when the primary is down or stalls."""

from __future__ import annotations

import importlib.util
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "roles" / "02_download_images" / "files" / "download_cloud_image.py"


def _load():
    spec = importlib.util.spec_from_file_location("download_cloud_image", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/missing"):
            self.send_error(404, "missing")
            return
        if self.path.startswith("/stall"):
            self.send_response(200)
            self.send_header("Content-Length", "1000000")
            self.end_headers()
            try:
                self.wfile.write(b"x" * 100)
                time.sleep(30)
            except Exception:
                return
            return
        body = b"full-image-bytes"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


class DownloadCloudImageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load()
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.thread.join(timeout=5)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}/{path}"

    def test_primary_download(self) -> None:
        with TemporaryDirectory() as tmp:
            chosen = self.mod.fetch(
                Path(tmp),
                self._url("ubuntu.img"),
                probe_timeout=2,
                stall=5,
                overall=10,
            )
            self.assertEqual(chosen["image_file"], "ubuntu.img")
            self.assertEqual((Path(tmp) / "ubuntu.img").read_bytes(), b"full-image-bytes")

    def test_primary_404_uses_backup(self) -> None:
        with TemporaryDirectory() as tmp:
            chosen = self.mod.fetch(
                Path(tmp),
                self._url("missing.img"),
                probe_timeout=2,
                stall=5,
                overall=10,
                backup=self._url("debian.qcow2"),
            )
            self.assertEqual(chosen["image_file"], "debian.qcow2")
            self.assertTrue(chosen["image_url"].endswith("/debian.qcow2"))
            self.assertFalse((Path(tmp) / "missing.img").exists())

    def test_primary_stall_uses_backup(self) -> None:
        with TemporaryDirectory() as tmp:
            chosen = self.mod.fetch(
                Path(tmp),
                self._url("stall.img"),
                probe_timeout=2,
                stall=1,
                overall=10,
                backup=self._url("mirror.img"),
            )
            self.assertEqual(chosen["image_file"], "mirror.img")
            self.assertEqual((Path(tmp) / "mirror.img").read_bytes(), b"full-image-bytes")
            self.assertFalse((Path(tmp) / "stall.img").exists())
            self.assertFalse((Path(tmp) / "stall.img.partial").exists())

    def test_empty_backup_fails_when_primary_is_down(self) -> None:
        with TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit) as raised:
                self.mod.fetch(
                    Path(tmp),
                    self._url("missing.img"),
                    probe_timeout=2,
                    stall=2,
                    overall=5,
                    backup="",
                )
            self.assertIn("not downloadable", str(raised.exception))
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
