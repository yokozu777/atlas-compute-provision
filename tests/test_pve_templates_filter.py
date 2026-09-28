"""Unit tests for filter_plugins.pve_templates."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "filter_plugins" / "pve_templates.py"


def _load():
    spec = importlib.util.spec_from_file_location("pve_templates", PLUGIN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class PveTemplatesFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load()

    def test_basename_from_url(self) -> None:
        url = "https://upload.example.com/images/ubuntu-26.04-minimal-cloudimg-amd64.img"
        self.assertEqual(
            self.mod._image_basename(url),
            "ubuntu-26.04-minimal-cloudimg-amd64.img",
        )

    def test_basename_strips_query(self) -> None:
        url = "https://example.com/path/OL9.qcow2?token=abc"
        self.assertEqual(self.mod._image_basename(url), "OL9.qcow2")

    def test_resolve_entry_uses_key_as_name(self) -> None:
        entry = {
            "id": 444124,
            "name": "legacy-ignored",
            "image_url": "https://upload.example.com/images/ubuntu-26.04-minimal-cloudimg-amd64.img",
            "download_glob": "ubuntu*",
            "image_file": "ubuntu.img",
        }
        resolved = self.mod.resolve_pve_template_entry(entry, "ubuntu-k8s")
        self.assertEqual(resolved["name"], "ubuntu-k8s")
        self.assertEqual(resolved["template_key"], "ubuntu-k8s")
        self.assertEqual(resolved["image_file"], "ubuntu-26.04-minimal-cloudimg-amd64.img")
        self.assertEqual(resolved["id"], 444124)
        self.assertNotIn("download_glob", resolved)

    def test_resolve_catalog(self) -> None:
        catalog = {
            "ubuntu-noble": {
                "id": 9001,
                "image_url": "https://cloud-images.ubuntu.com/x/ubuntu-24.04-minimal-cloudimg-amd64.img",
            }
        }
        resolved = self.mod.resolve_pve_templates(catalog)
        self.assertEqual(resolved["ubuntu-noble"]["name"], "ubuntu-noble")
        self.assertEqual(
            resolved["ubuntu-noble"]["image_file"],
            "ubuntu-24.04-minimal-cloudimg-amd64.img",
        )

    def test_resolve_entry_without_image_url(self) -> None:
        """Resolver accepts id-only or empty entries (provision allowlist / transitional)."""
        resolved = self.mod.resolve_pve_template_entry({"id": 400100}, "ubuntu-base")
        self.assertEqual(resolved["name"], "ubuntu-base")
        self.assertEqual(resolved["template_key"], "ubuntu-base")
        self.assertEqual(resolved["id"], 400100)
        self.assertEqual(resolved["image_file"], "")
        self.assertNotIn("image_url", resolved)
        empty = self.mod.resolve_pve_template_entry({}, "oracle-base")
        self.assertEqual(empty["name"], "oracle-base")
        self.assertEqual(empty["image_file"], "")
        self.assertNotIn("id", empty)

    def test_resolve_catalog_mixed_build_and_clone(self) -> None:
        catalog = {
            "ubuntu-base": {"id": 400100},
            "oracle-base": {
                "id": 400101,
                "image_url": "https://example.com/OL9.qcow2",
            },
        }
        resolved = self.mod.resolve_pve_templates(catalog)
        self.assertEqual(resolved["ubuntu-base"]["image_file"], "")
        self.assertEqual(resolved["oracle-base"]["image_file"], "OL9.qcow2")

    def test_empty_backup_is_dropped(self) -> None:
        resolved = self.mod.resolve_pve_template_entry(
            {"id": 400100, "image_url": "https://example.com/u.img", "image_url_backup": "  "},
            "ubuntu-base",
        )
        self.assertNotIn("image_url_backup", resolved)
        self.assertEqual(resolved["image_file"], "u.img")

    def test_backup_is_kept_and_download_result_replaces_file(self) -> None:
        resolved = self.mod.resolve_pve_template_entry(
            {
                "id": 400100,
                "image_url": "https://example.com/u.img",
                "image_url_backup": "https://mirror.example/u.img",
            },
            "ubuntu-base",
        )
        self.assertEqual(resolved["image_url_backup"], "https://mirror.example/u.img")
        updated = self.mod.apply_pve_download_results(
            [resolved],
            [{"name": "ubuntu-base", "image_url": "https://mirror.example/u.img", "image_file": "u.img"}],
        )
        self.assertEqual(updated[0]["image_url"], "https://mirror.example/u.img")
        self.assertEqual(updated[0]["image_file"], "u.img")
        self.assertEqual(updated[0]["image_url_backup"], "https://mirror.example/u.img")


if __name__ == "__main__":
    unittest.main()
