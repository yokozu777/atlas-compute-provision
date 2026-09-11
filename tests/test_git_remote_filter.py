"""Unit tests for filter_plugins.git_remote."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "filter_plugins" / "git_remote.py"


def _load():
    spec = importlib.util.spec_from_file_location("git_remote", PLUGIN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class GitRemoteFilterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _load()

    def test_ssh_url_matches_scp_like(self) -> None:
        ssh = "ssh://git@gitea.mxhash.com/root/atlas-inventory.git"
        scp = "git@gitea.mxhash.com:root/atlas-inventory.git"
        self.assertEqual(
            self.mod.canonicalize_git_remote(ssh),
            "git@gitea.mxhash.com:root/atlas-inventory",
        )
        self.assertEqual(
            self.mod.canonicalize_git_remote(scp),
            "git@gitea.mxhash.com:root/atlas-inventory",
        )
        self.assertTrue(self.mod.git_remotes_match(ssh, scp))

    def test_ssh_url_with_port(self) -> None:
        ssh = "ssh://git@gitea.mxhash.com:22/root/atlas-inventory.git"
        scp = "git@gitea.mxhash.com:root/atlas-inventory"
        self.assertTrue(self.mod.git_remotes_match(ssh, scp))

    def test_git_plus_ssh(self) -> None:
        left = "git+ssh://git@gitea.mxhash.com/root/atlas-inventory.git"
        right = "git@gitea.mxhash.com:root/atlas-inventory"
        self.assertTrue(self.mod.git_remotes_match(left, right))

    def test_different_repos_do_not_match(self) -> None:
        left = "ssh://git@gitea.mxhash.com/root/atlas-inventory.git"
        right = "git@gitea.mxhash.com:root/vms_state.git"
        self.assertFalse(self.mod.git_remotes_match(left, right))

    def test_https_canonical(self) -> None:
        self.assertEqual(
            self.mod.canonicalize_git_remote(
                "https://gitea.mxhash.com/root/atlas-inventory.git"
            ),
            "https://gitea.mxhash.com/root/atlas-inventory",
        )

    def test_empty(self) -> None:
        self.assertEqual(self.mod.canonicalize_git_remote(""), "")
        self.assertFalse(self.mod.git_remotes_match("", "git@h:p"))

    def test_filter_module_exports(self) -> None:
        filters = self.mod.FilterModule().filters()
        self.assertIn("canonicalize_git_remote", filters)
        self.assertIn("git_remotes_match", filters)


if __name__ == "__main__":
    unittest.main()
