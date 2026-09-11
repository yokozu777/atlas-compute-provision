"""Unit tests for 00_check_pve_templates linked-clone conf scanner."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    REPO_ROOT
    / "roles"
    / "00_check_pve_templates"
    / "files"
    / "detect_linked_clones.sh"
)
CHECK_TEMPLATE = (
    REPO_ROOT / "roles" / "00_check_pve_templates" / "tasks" / "check_template.yaml"
)


def _write_conf(root: Path, node: str, vmid: str, body: str) -> Path:
    conf_dir = root / node / "qemu-server"
    conf_dir.mkdir(parents=True, exist_ok=True)
    path = conf_dir / f"{vmid}.conf"
    path.write_text(body, encoding="utf-8")
    return path


def _run(tid: str, conf_root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PVE_QEMU_CONF_ROOT"] = str(conf_root)
    return subprocess.run(
        ["bash", str(SCRIPT), tid],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


class DetectLinkedClonesScriptTest(unittest.TestCase):
    def test_script_is_executable_bits_ok(self) -> None:
        self.assertTrue(SCRIPT.is_file(), str(SCRIPT))
        # Must be runnable via bash even if +x missing in checkout.
        self.assertIn("PVE_QEMU_CONF_ROOT", SCRIPT.read_text(encoding="utf-8"))

    def test_invalid_vmid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_conf(root, "pve1", "100", "name: x\n")
            r = _run("abc", root)
            self.assertEqual(r.returncode, 2)

    def test_missing_conf_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-nodes"
            r = _run("444124", missing)
            self.assertEqual(r.returncode, 3)

    def test_empty_greenfield_no_confs(self) -> None:
        # Wiped / fresh PVE: nodes root exists, qemu-server has no *.conf yet.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "proxmox2" / "qemu-server").mkdir(parents=True)
            r = _run("400100", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")

    def test_no_clones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_conf(
                root,
                "pve1",
                "444124",
                "name: ubuntu-k8s\ntemplate: 1\nscsi0: local-zfs:base-444124-disk-0\n",
            )
            _write_conf(
                root,
                "pve1",
                "219",
                "name: infra2\nscsi0: local-zfs:vm-219-disk-0,size=32G\n",
            )
            r = _run("444124", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")

    def test_parent_and_base_disk_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_conf(root, "pve1", "444124", "name: tpl\ntemplate: 1\n")
            _write_conf(
                root,
                "pve1",
                "301",
                "name: linked-a\nparent: 444124\nscsi0: local-zfs:base-444124-disk-0\n",
            )
            _write_conf(
                root,
                "pve2",
                "302",
                "name: linked-b\nscsi0: local-lvm:base-444124-disk-0,size=20G\n",
            )
            _write_conf(
                root,
                "pve1",
                "303",
                # full clone — must NOT match
                "name: full\nscsi0: local-zfs:vm-303-disk-0,size=20G\n",
            )
            r = _run("444124", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "301 302")

    def test_does_not_match_bare_path_slash_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_conf(root, "pve1", "444124", "name: tpl\ntemplate: 1\n")
            _write_conf(
                root,
                "pve1",
                "400",
                # noisy path that old qm-config regex could trip on
                "name: noise\ndescription: path /444124/not-a-clone\n",
            )
            r = _run("444124", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")

    def test_excludes_template_self(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_conf(
                root,
                "pve1",
                "444124",
                "name: tpl\ntemplate: 1\nscsi0: local-zfs:base-444124-disk-0\n",
            )
            r = _run("444124", root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), "")


class CheckTemplateTaskContractTest(unittest.TestCase):
    def test_uses_conf_scan_script_and_conditional_gate(self) -> None:
        text = CHECK_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("detect_linked_clones.sh", text)
        self.assertIn("build_template_need_linked_scan", text)
        self.assertIn("resolve_pve_template_entry", text)
        self.assertIn("ansible.builtin.script", text)
        self.assertNotIn("qm list", text)
        self.assertNotIn("while IFS= read -r vmid", text)
        # Rename still gated on empty linked list.
        self.assertIn("build_template_linked_clone_vmids | length == 0", text)
        # Scan runs only when gate is true.
        self.assertIn("when: build_template_need_linked_scan | bool", text)


if __name__ == "__main__":
    unittest.main()
