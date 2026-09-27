"""Golden PVE image URL probe fails closed when the origin is unreachable."""

from __future__ import annotations

import importlib.util
import socket
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROBE = REPO_ROOT / "roles" / "02_download_images" / "files" / "probe_cloud_image.py"


def _load():
    spec = importlib.util.spec_from_file_location("probe_cloud_image", PROBE)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/range-rejected"):
            if "Range" in self.headers:
                self.send_error(416, "Range Not Satisfiable")
                return
            body = b"qcow-bytes"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/missing"):
            self.send_error(404, "missing")
            return
        body = b"img-bytes-ok"
        self.send_response(206 if "Range" in self.headers else 200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:
        return


class ProbeCloudImageTest(unittest.TestCase):
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

    def test_range_response_is_reachable(self) -> None:
        url = f"http://127.0.0.1:{self.port}/ubuntu.img"
        self.assertIn("reachable HTTP 206", self.mod.probe(url, 5))

    def test_retries_without_range(self) -> None:
        url = f"http://127.0.0.1:{self.port}/range-rejected/debian.qcow2"
        self.assertIn("reachable HTTP 200", self.mod.probe(url, 5))

    def test_http_404_fails(self) -> None:
        url = f"http://127.0.0.1:{self.port}/missing.img"
        with self.assertRaises(SystemExit) as raised:
            self.mod.probe(url, 5)
        self.assertIn("HTTP 404", str(raised.exception))

    def test_connection_refused_fails(self) -> None:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            closed = sock.getsockname()[1]
        url = f"http://127.0.0.1:{closed}/ubuntu.img"
        with self.assertRaises(SystemExit) as raised:
            self.mod.probe(url, 2)
        self.assertIn("not downloadable", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
