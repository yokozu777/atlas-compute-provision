"""Compute-provision repo layout / hygiene / fingerprint tests (publish step 2)."""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

_PRODUCT_SCAN_ROOTS = (
    REPO_ROOT / "roles",
    REPO_ROOT / "playbooks",
    REPO_ROOT / "group_vars",
    REPO_ROOT / "stacks",
    REPO_ROOT / "modules",
    REPO_ROOT / "filter_plugins",
    REPO_ROOT / "examples",
    REPO_ROOT / "host_vars",
    REPO_ROOT / "inventory-example.yml",
    REPO_ROOT / "run.sh",
    REPO_ROOT / "ansible.cfg",
    REPO_ROOT / "vars-build.yml",
    REPO_ROOT / "README.md",
)
_PRODUCT_SCAN_SUFFIXES = {".yml", ".yaml", ".j2", ".sh", ".cfg", ".md", ".py", ".tf", ".toml"}
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_SKIP_PATH_PARTS = ("examples/internal",)

_EXPECTED_ROLES = (
    "00_ensure_workspace",
    "00_validate_provision",
    "00_check_pve_templates",
    "01_prepare_system",
    "02_download_images",
    "03_customize_images",
    "04_upload_images",
    "05_create_pve_templates",
    "06_configure_git",
    "07_tf_state_pull",
    "08_generate_tf_vars",
    "09_hypervisor_cleaner",
    "09a_tf_destroy_dns",
    "10_tf_apply",
    "11_tf_state_push",
)

_EXPECTED_STACKS = (
    "k8s",
    "jenkins",
    "gitlab_runner",
    "postgresql",
    "mysql",
    "redis",
    "kafka",
    "_shared",
)


def _is_skipped(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return any(part in rel for part in _SKIP_PATH_PARTS)


def _iter_product_files():
    for root in _PRODUCT_SCAN_ROOTS:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or _is_skipped(path):
                continue
            if path.suffix.lower() not in _PRODUCT_SCAN_SUFFIXES and path.name != "run.sh":
                continue
            yield path


def _scan_product_sources_for(
    needles: tuple[str, ...],
    *,
    case_sensitive: bool = False,
) -> list[str]:
    hits: list[str] = []
    for path in _iter_product_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        haystack = text if case_sensitive else text.lower()
        for needle in needles:
            probe = needle if case_sensitive else needle.lower()
            if probe in haystack:
                hits.append(f"{path.relative_to(REPO_ROOT)}:{needle}")
    return hits


class ComputeProvisionLayoutTest(unittest.TestCase):
    def test_license_and_security_exist(self) -> None:
        self.assertTrue((REPO_ROOT / "LICENSE").is_file())
        self.assertTrue((REPO_ROOT / "SECURITY.md").is_file())
        self.assertTrue((REPO_ROOT / ".gitignore").is_file())
        self.assertTrue((REPO_ROOT / ".dockerignore").is_file())

    def test_adr_001_tfstate_phase5_docs(self) -> None:
        """Phase 5: publish + multi-leaf 07 pull + plan smoke recorded in ADR."""
        adr = REPO_ROOT / "docs" / "adr" / "001-tfstate-repo-prefix.md"
        guide = REPO_ROOT / "docs" / "tfstate.md"
        index = REPO_ROOT / "docs" / "adr" / "README.md"
        text = adr.read_text(encoding="utf-8")
        guide_text = guide.read_text(encoding="utf-8")
        self.assertIn("Status:** Accepted (Phase 5", text)
        self.assertIn("Phase 5 complete", text)
        self.assertIn("07_tf_state_pull", text)
        self.assertIn("tfstate/ci/infra", text)
        self.assertIn("dev/mxhash", text)
        self.assertIn("0 to add", text)
        self.assertIn("0 to destroy", text)
        self.assertIn("Accepted (Phase 5", index.read_text(encoding="utf-8"))
        self.assertIn("Phase 5", guide_text)
        self.assertIn("tfstate-repo", guide_text)
        self.assertIn("multi-leaf", guide_text)
        defaults = (REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_defaults.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("/tfstate-repo", defaults)
        self.assertIn("provision_tf_state_repo_prefix: tfstate", defaults)

    def test_adr_001_tfstate_phase6_contract_docs(self) -> None:
        """Phase 6: unified inventory local_dir contract (docs only)."""
        adr = REPO_ROOT / "docs" / "adr" / "001-tfstate-repo-prefix.md"
        guide = REPO_ROOT / "docs" / "tfstate.md"
        text = adr.read_text(encoding="utf-8")
        guide_text = guide.read_text(encoding="utf-8")
        self.assertIn("Phase 6", text)
        self.assertIn("Unified inventory", text)
        self.assertIn("Stage 1", text)
        self.assertIn("an existing git checkout", text)
        self.assertIn("MUST NOT clone a", text)
        self.assertIn("provision_tf_state_cluster_path", text)
        self.assertIn("Phase 6", guide_text)
        self.assertIn("Unified inventory checkout", guide_text)
        self.assertIn("Controller modes", guide_text)
        self.assertIn("provision_tf_state_git_discard_local", guide_text)
        self.assertIn("Stages 2–3", guide_text)
        self.assertIn("atlas_inventory_root", guide_text)
        index = (REPO_ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Phase 6", index)
        self.assertIn("Stages 1–5", text)
        self.assertIn("Stage 5 — CI", text)
        self.assertIn("prepare_inventory_checkout.sh", text)
        self.assertIn("tfstate-repo.legacy.bak", text)
        # P2: ADR header no longer reads as “Phase 6 still open”
        self.assertIn("Phase 6** Stages 1–5", text.replace("\n", " "))
        self.assertIn("**landed**", text)
        self.assertNotIn("→ **6 (unified inventory local_dir — contract)**", text)
        self.assertIn("Stages 1–5 landed", text)

    def test_adr_001_tfstate_phase6_stage1_roles(self) -> None:
        """Phase 6 Stage 1: 07 reuse / 11 scoped add / discard-local default."""
        pull = (REPO_ROOT / "roles" / "07_tf_state_pull" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        push = (REPO_ROOT / "roles" / "11_tf_state_push" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        validate = (REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        defaults = (REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_defaults.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Fetch and fast-forward existing matching checkout", pull)
        self.assertIn("git merge --ff-only", pull)
        self.assertIn("force: false", pull)
        self.assertIn(":(exclude){{ provision_tf_state_git_prefix }}", pull)
        self.assertIn("provision_tf_state_git_discard_local", pull)
        self.assertIn("Clone terraform state repository into local_dir", pull)
        self.assertNotIn("force: true", pull)
        self.assertNotIn("reset --hard", pull)
        self.assertIn(":(exclude){{ provision_tf_state_git_prefix }}", push)
        self.assertIn('git add -- "{{ provision_tf_state_cluster_path }}"', push)
        self.assertIn("Refusing to commit path outside", push)
        self.assertIn("provision_tf_state_git_discard_local", push)
        self.assertNotIn("reset --hard", push)
        self.assertNotIn("\ngit add .\n", push)
        self.assertNotIn("git add .", push)
        # Ensure leaf dir after discard/pull (not before): clean must not wipe mkdir.
        ensure_idx = push.index("Ensure cluster state directory exists in repository")
        pull_idx = push.index("Pull latest terraform state from remote before syncing local copy")
        clean_idx = push.index("git clean -fd --")
        self.assertGreater(ensure_idx, pull_idx)
        self.assertGreater(ensure_idx, clean_idx)
        self.assertIn("does not match provision_tf_state_repo", validate)
        self.assertIn("provision_tf_state_git_discard_local: false", defaults)

    def test_gitignore_covers_inventory_workspace_and_tf_state(self) -> None:
        text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        for needle in (
            "inventory.yml",
            "workspace/",
            "secrets.yml",
            "!roles/**/tasks/secrets.yml",
            "*.vault",
            "__pycache__/",
            "*.tfstate",
            ".terraform/",
        ):
            self.assertIn(needle, text)
        dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
        self.assertIn("!roles/**/tasks/secrets.yml", dockerignore)

    def test_standalone_entrypoints(self) -> None:
        run_sh = REPO_ROOT / "run.sh"
        self.assertTrue(run_sh.is_file())
        self.assertTrue(run_sh.stat().st_mode & 0o111, "run.sh must be executable")
        self.assertTrue((REPO_ROOT / "inventory-example.yml").is_file())
        self.assertTrue((REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.yml").is_file())
        self.assertTrue((REPO_ROOT / "group_vars" / "all").is_dir())
        self.assertFalse((REPO_ROOT / "group_vars" / "all.yml").exists())
        self.assertFalse((REPO_ROOT / "group_vars" / "all" / "standalone.example.yml").exists())
        self.assertTrue((REPO_ROOT / "requirements.yml").is_file())
        self.assertTrue((REPO_ROOT / "examples" / "secrets.example.yml").is_file())
        self.assertTrue((REPO_ROOT / "examples" / "ssh" / "localuser.pub").is_file())
        self.assertTrue((REPO_ROOT / "host_vars" / "example.yml").is_file())
        self.assertTrue((REPO_ROOT / "vars-build.yml").is_file())

        catalog = (REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.yml").read_text(encoding="utf-8")
        secrets_overlay = (
            REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.secrets.yml"
        ).read_text(encoding="utf-8")
        defaults = (REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_defaults.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("operator surface", catalog.lower())
        self.assertIn("provision_defaults.yml", catalog)
        self.assertIn("provision_stack: jenkins", catalog)
        self.assertIn("CHANGEME", secrets_overlay)
        self.assertTrue((REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.secrets.yml").is_file())
        self.assertIn("example.com", catalog)
        self.assertIn("cluster_workspace_root:", catalog)
        self.assertIn("CLUSTER_WORKSPACE_ID", catalog)
        self.assertIn("CLUSTER_WORKSPACE_PARENT", catalog)
        self.assertIn("CLUSTER_WORKSPACE_ROOT", catalog)
        self.assertIn("provision_inventory_group_map_jenkins:", catalog)
        self.assertIn("provision_inventory_group_map_gitlab_runner:", catalog)
        self.assertIn("provision_pve_templates:", catalog)
        self.assertIn("ubuntu-noble:", catalog)
        self.assertNotIn("download_glob:", catalog)
        self.assertNotIn("image_file:", catalog)
        self.assertNotIn("name: ubuntu-noble", catalog)
        self.assertTrue((REPO_ROOT / "filter_plugins" / "pve_templates.py").is_file())
        self.assertTrue((REPO_ROOT / "filter_plugins" / "git_remote.py").is_file())
        ansible_cfg = (REPO_ROOT / "ansible.cfg").read_text(encoding="utf-8")
        self.assertIn("filter_plugins = ./filter_plugins", ansible_cfg)
        self.assertNotIn("mxhash", catalog.lower())
        self.assertNotIn("Welcomeback", catalog)
        self.assertNotIn("clusterctl", catalog.lower())
        self.assertNotIn("gitea.", catalog.lower())
        # Stable knobs live in playbooks/group_vars/all/provision_defaults.yml
        self.assertIn("provision_tf_state_git_push: false", defaults)
        self.assertIn("tfstate", defaults)
        self.assertIn("provision_tf_state_cluster_path:", defaults)
        self.assertNotIn('provision_tf_state_cluster_path: "clusters/', defaults)
        self.assertIn("provision_enforce_live_secrets: false", defaults)
        self.assertIn("provision_dns_tf_manage_a_records: false", defaults)
        self.assertIn("provision_dns_a_ttl: 300", defaults)

        inventory = (REPO_ROOT / "inventory-example.yml").read_text(encoding="utf-8")
        self.assertIn("jslave:", inventory)
        self.assertIn("hostname:", inventory)
        self.assertIn("example.com", inventory)
        self.assertIn("ubuntu-noble", inventory)
        self.assertNotIn("mxhash", inventory.lower())

        run_text = run_sh.read_text(encoding="utf-8")
        self.assertIn("playbooks/provision_nodes.yaml", run_text)
        self.assertIn("playbooks/build_templates.yaml", run_text)
        self.assertIn("CLUSTER_WORKSPACE_ROOT", run_text)
        self.assertIn("CLUSTER_WORKSPACE_PARENT", run_text)
        self.assertIn("EXTRA_VARS_FILE", run_text)
        self.assertIn("inventory-example.yml", run_text)
        self.assertIn('MODE="provision"', run_text)
        self.assertIn("templates|provision", run_text)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", run_text)
        self.assertIn("provision_hosts_file=", run_text)

        secrets = (REPO_ROOT / "examples" / "secrets.example.yml").read_text(encoding="utf-8")
        self.assertIn("CHANGEME", secrets)
        self.assertIn("provision_enforce_live_secrets: true", secrets)
        self.assertIn("provision_proxmox_token_secret", secrets)
        destroy_dns = (
            REPO_ROOT / "roles" / "09a_tf_destroy_dns" / "tasks" / "main.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("provision_dns_tf_manage_a_records", destroy_dns)
        self.assertIn("Destroy Terraform-managed DNS A records on destroy mode", destroy_dns)

        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("./run.sh", readme)
        self.assertIn("## Quickstart", readme)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", readme)
        self.assertIn("inventory-example.yml", readme)
        self.assertIn("## Compatibility", readme)
        self.assertIn("## Architecture (role order)", readme)
        self.assertIn("## Stacks and provision modes", readme)
        self.assertIn("## Greenfield checklist", readme)
        self.assertIn("## Troubleshooting", readme)
        self.assertIn("## Testing / CI", readme)
        self.assertIn("## Project structure", readme)
        self.assertIn("## Integrations", readme)
        self.assertIn("## Security", readme)
        self.assertIn("## Contributing", readme)
        self.assertIn("00_validate_provision", readme)
        self.assertIn("playbooks/build_templates.yaml", readme)
        self.assertIn("playbooks/provision_nodes.yaml", readme)
        self.assertIn("provision_stack", readme)
        self.assertIn("provision_tf_state_git_push", readme)
        self.assertIn("provision_enforce_live_secrets", readme)
        self.assertIn("provision_wait_ssh", readme)
        self.assertIn("my_build_agents", readme)
        self.assertIn("examples/rename_smoke", readme)
        self.assertIn("examples/k8s", readme)
        self.assertIn("Renaming inventory groups", readme)
        self.assertIn("test_compute_provision_layout", readme)
        self.assertIn("test_provision_stacks", readme)
        self.assertIn("check-no-hardcoded-domains.sh", readme)
        self.assertIn("./tests/run_ci.sh", readme)
        self.assertIn(".github/workflows/ci.yml", readme)
        self.assertIn("ansible-lint", readme)
        self.assertIn("requirements.yml", readme)
        self.assertIn("01_validate_vars", readme)  # documented absence / contrast
        self.assertIn("SECURITY.md", readme)
        self.assertIn("LICENSE", readme)
        self.assertIn("CLUSTER_WORKSPACE_PARENT", readme)
        self.assertIn("EXTRA_VARS_FILE", readme)
        self.assertNotIn("standalone.example.yml", readme)
        self.assertNotIn("mxhash", readme.lower())
        self.assertNotIn("gitea.", readme.lower())
        self.assertNotIn("Welcomeback", readme)
        self.assertNotIn("clusterctl", readme)
        self.assertNotIn("./cluster ", readme)
        self.assertNotIn("./cluster\n", readme)
        quick = readme.index("## Quickstart")
        integ = readme.index("## Integrations")
        self.assertLess(quick, integ)
        for earlier, later in (
            ("## Compatibility", "## Quickstart"),
            ("## Quickstart", "## Architecture (role order)"),
            ("## Architecture (role order)", "## Stacks and provision modes"),
            ("## Stacks and provision modes", "## Greenfield checklist"),
            ("## Greenfield checklist", "## Troubleshooting"),
            ("## Troubleshooting", "## Testing / CI"),
            ("## Testing / CI", "## Project structure"),
            ("## Project structure", "## Integrations"),
            ("## Integrations", "## Security"),
            ("## Security", "## Contributing"),
        ):
            self.assertLess(readme.index(earlier), readme.index(later), f"{earlier} before {later}")

    def test_readme_has_no_org_urls(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("mxhash", readme.lower())
        self.assertNotIn("gitea.", readme.lower())
        self.assertNotIn("harbor.", readme.lower())
        self.assertNotIn("Welcomeback", readme)
        self.assertIn("SECURITY.md", readme)
        self.assertIn("LICENSE", readme)

    def test_readme_quickstart_uses_run_sh(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Quickstart", readme)
        self.assertIn("./run.sh", readme)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", readme)
        self.assertIn("inventory-example.yml", readme)
        self.assertIn("playbooks/provision_nodes.yaml", readme)
        self.assertIn("playbooks/build_templates.yaml", readme)
        self.assertIn("--tags 00_validate_provision", readme)
        self.assertIn("./run.sh templates", readme)
        self.assertIn("./run.sh provision", readme)
        self.assertIn("ansible-galaxy collection install -r requirements.yml", readme)
        self.assertNotIn("standalone.example.yml", readme)
        self.assertNotIn("gitea.", readme.lower())
        self.assertNotIn("mxhash", readme.lower())
        self.assertNotIn("clusterctl", readme)
        self.assertNotIn("./cluster ", readme)

    def test_ci_entrypoint_artifacts(self) -> None:
        self.assertTrue((REPO_ROOT / ".ansible-lint").is_file())
        self.assertTrue((REPO_ROOT / ".github" / "workflows" / "ci.yml").is_file())
        self.assertTrue((REPO_ROOT / "requirements.yml").is_file())
        self.assertTrue((REPO_ROOT / "requirements-dev.txt").is_file())
        run_ci = REPO_ROOT / "tests" / "run_ci.sh"
        self.assertTrue(run_ci.is_file())
        self.assertTrue(run_ci.stat().st_mode & 0o111, "tests/run_ci.sh must be executable")
        run_ci_text = run_ci.read_text(encoding="utf-8")
        for needle in (
            "unittest",
            "syntax-check",
            "ansible-lint",
            "check-no-hardcoded-domains.sh",
            "playbooks/provision_nodes.yaml",
            "playbooks/build_templates.yaml",
        ):
            self.assertIn(needle, run_ci_text, needle)
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("ansible-lint --profile min", workflow)
        self.assertIn("check-no-hardcoded-domains.sh", workflow)
        self.assertIn("playbooks/provision_nodes.yaml", workflow)
        self.assertIn("playbooks/build_templates.yaml", workflow)
        self.assertIn("requirements.yml", workflow)
        lint_cfg = (REPO_ROOT / ".ansible-lint").read_text(encoding="utf-8")
        self.assertIn("profile: min", lint_cfg)
        self.assertIn("examples/internal/", lint_cfg)
        self.assertIn("stacks/", lint_cfg)
        self.assertIn("modules/", lint_cfg)
        reqs = (REPO_ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
        self.assertIn("ansible-lint", reqs)
        galaxy = (REPO_ROOT / "requirements.yml").read_text(encoding="utf-8")
        self.assertIn("community.general", galaxy)
        self.assertIn("ansible.posix", galaxy)

    def test_playbook_headers_are_orchestrator_neutral(self) -> None:
        for rel in (
            "playbooks/build_templates.yaml",
            "playbooks/provision_nodes.yaml",
            "playbooks/group_vars/all/provision_stack_maps.yml",
        ):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("clusterctl", text, rel)
            self.assertNotIn("clusters/<id>", text, rel)
            self.assertNotIn("vars-file.yml", text, rel)
            self.assertNotIn("mxhash", text.lower(), rel)
            self.assertNotIn("atlas-clusterctl", text, rel)

        provision = (REPO_ROOT / "playbooks" / "provision_nodes.yaml").read_text(encoding="utf-8")
        self.assertIn("tags: [00_ensure_workspace]", provision)
        self.assertIn("tags: 00_validate_provision", provision)
        self.assertIn("provision_wait_ssh", provision)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", provision)

        templates = (REPO_ROOT / "playbooks" / "build_templates.yaml").read_text(encoding="utf-8")
        self.assertIn("./run.sh templates", templates)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", templates)
        self.assertIn("provision_pve_inventory_group | default('proxmox')", templates)
        # After successful 05, drop local build artifacts (images live on PVE as templates).
        self.assertIn("Clean build workspace after template build completed", templates)
        self.assertIn("Remove build state file after template build completed", templates)
        # Build path requires id + image_url; provision validate does not require catalog.
        self.assertIn("Assert each template has id + image_url", templates)
        self.assertIn("needs id + image_url", templates)

        validate = (REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Normalize optional provision_pve_templates allowlist", validate)
        self.assertIn("Assert unique ids when optional catalog entries declare id", validate)
        self.assertNotIn("Assert each provision_pve_templates entry has id", validate)
        self.assertNotIn("needs id + image_url", validate)
        inv = (
            REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "validate_inventory_group.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("optional allowlist", inv.lower())
        self.assertIn(
            "(provision_pve_templates | default({}) | length == 0)",
            inv,
        )
        self.assertTrue(
            (REPO_ROOT / "examples" / "provision_catalog_clone_only.example.yml").is_file()
        )
        clone_only = (
            REPO_ROOT / "examples" / "provision_catalog_clone_only.example.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("optional", clone_only.lower())
        self.assertIn("omit", clone_only.lower())
        self.assertNotIn("id: 400100", clone_only)
        self.assertNotIn("image_url:", clone_only)

        customize = (
            REPO_ROOT / "roles" / "03_customize_images" / "tasks" / "main.yaml"
        ).read_text(encoding="utf-8")
        # Do not delete the just-downloaded file when image_file == basename(image_url).
        self.assertIn(
            "when: item.image_file != (item.image_url | basename)",
            customize,
        )

        create_tpl = (
            REPO_ROOT / "roles" / "05_create_pve_templates" / "tasks" / "main.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "Remove uploaded template images from Proxmox upload directory",
            create_tpl,
        )

    def test_no_org_fingerprint_in_product_sources(self) -> None:
        needles = (
            "mxhash",
            "gitea.",
            "harbor.",
            "welcomeback",
            "upload.mxhash",
            "nexus.mxhash",
            "/var/lib/mxhash",
        )
        hits = _scan_product_sources_for(needles)
        self.assertEqual(hits, [], f"org fingerprint in product sources: {hits}")

        for needle in (
            "vars-file.yml",
            "atlas-clusterctl",
            "./cluster ",
            "clusters/<id>",
        ):
            overlay_hits = _scan_product_sources_for((needle,), case_sensitive=True)
            self.assertEqual(
                overlay_hits,
                [],
                f"orchestrator path in product sources ({needle}): {overlay_hits}",
            )

    def test_no_lab_password_fingerprint_in_product_sources(self) -> None:
        hits = _scan_product_sources_for(("Welcomeback",), case_sensitive=True)
        self.assertEqual(hits, [], f"lab password fingerprint in product sources: {hits}")

    def test_no_obvious_secret_material_in_product_sources(self) -> None:
        needles = ("Welcomeback", "BEGIN OPENSSH PRIVATE", "BEGIN RSA PRIVATE", "AKIA")
        hits = _scan_product_sources_for(needles, case_sensitive=True)
        self.assertEqual(hits, [], f"secret-like material found: {hits}")

    def test_no_cyrillic_in_product_sources(self) -> None:
        hits: list[str] = []
        for path in _iter_product_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if _CYRILLIC_RE.search(text):
                hits.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(hits, [], f"Cyrillic residue in product sources: {hits[:20]}")

    def test_catalog_and_examples_are_inert(self) -> None:
        catalog = (REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.yml").read_text(encoding="utf-8")
        secrets_overlay = (
            REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.secrets.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("CHANGEME", secrets_overlay)
        self.assertIn("example.com", catalog)
        self.assertIn("gitea_host: git.example.com", catalog)
        self.assertIn("provision_dns_tf_manage_a_records: false", catalog)
        self.assertIn("provision_inventory_group_map_redis:", catalog)
        self.assertIn("provision_tf_module_map_k8s:", catalog)
        self.assertNotIn('provision_pve_ssh_password: "CHANGEME"', catalog)
        self.assertIn('provision_pve_ssh_password: "CHANGEME"', secrets_overlay)
        self.assertIn('provision_proxmox_token_secret: "CHANGEME"', secrets_overlay)
        self.assertNotIn("mxhash", catalog.lower())
        self.assertNotIn("Welcomeback", catalog)

        for rel in (
            "examples/jenkins/provision.example.yml",
            "examples/postgresql/provision.example.yml",
            "examples/kafka/provision.example.yml",
            "examples/jenkins/hosts.example.yml",
            "examples/postgresql/hosts.example.yml",
            "examples/kafka/hosts.example.yml",
            "vars-build.yml",
        ):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("mxhash", text.lower(), rel)
            self.assertNotIn("Welcomeback", text, rel)
            self.assertNotIn("gitea.", text.lower(), rel)
            self.assertNotIn("atlas-clusterctl", text, rel)

    def test_domain_check_script_exists_and_passes(self) -> None:
        path = REPO_ROOT / "scripts" / "check-no-hardcoded-domains.sh"
        self.assertTrue(path.is_file())
        self.assertTrue(path.stat().st_mode & 0o111, "check-no-hardcoded-domains.sh must be executable")
        text = path.read_text(encoding="utf-8")
        self.assertIn("mxhash", text)
        self.assertIn(r"upload\.mxhash", text)
        self.assertIn(r"nexus\.mxhash", text)
        self.assertIn("/var/lib/mxhash", text)
        self.assertIn("[Ww]elcomeback", text)
        self.assertIn("examples/internal", text)
        result = subprocess.run(
            [str(path)],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_security_md_documents_history_fingerprint(self) -> None:
        text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("mxhash.com", text)
        self.assertIn("gitea.mxhash.com", text)
        self.assertIn("3738c82", text)
        self.assertIn("4694296", text)
        self.assertIn("check-no-hardcoded-domains.sh", text)
        self.assertIn("test_compute_provision_layout", text)
        self.assertIn("./tests/run_ci.sh", text)
        self.assertIn(".github/workflows/ci.yml", text)
        self.assertIn("examples/internal", text)

    def test_roles_and_stacks_layout(self) -> None:
        for role in _EXPECTED_ROLES:
            tasks = REPO_ROOT / "roles" / role / "tasks"
            self.assertTrue(
                (tasks / "main.yaml").is_file() or any(tasks.glob("*.yaml")),
                role,
            )
        for stack in _EXPECTED_STACKS:
            path = REPO_ROOT / "stacks" / stack
            self.assertTrue(path.is_dir(), stack)
        self.assertTrue((REPO_ROOT / "modules" / "proxmox_vm").is_dir())
        self.assertTrue((REPO_ROOT / "stacks" / "_shared" / "providers.tf.j2").is_file())

    def test_validate_defaults_git_push_opt_in(self) -> None:
        defaults = (REPO_ROOT / "roles" / "00_validate_provision" / "defaults" / "main.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_tf_state_git_push: false", defaults)
        validate = (REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_tf_state_git_push | default(false)", validate)
        self.assertIn("not (provision_tf_state_cluster_path is match('^clusters/')", validate)
        self.assertIn("not (provision_tf_state_cluster_path is match('^workspace/')", validate)
        self.assertIn(
            "provision_tf_state_cluster_path == (provision_tf_state_repo_prefix ~ '/' ~ cluster_id)",
            validate,
        )
        self.assertNotIn("provision_tf_state_cluster_path == cluster_id\n", validate)
        self.assertNotIn("vars-file.yml", validate)
        git_role = (REPO_ROOT / "roles" / "06_configure_git" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_tf_state_git_push | default(false)", git_role)
        self.assertIn("git_config", git_role)
        self.assertIn("user.name", git_role)
        self.assertIn("user.email", git_role)
        self.assertNotIn("provision_known_hosts", git_role)
        self.assertNotIn("ssh-keyscan", git_role)
        self.assertNotIn("Ensure SSH directory", git_role)
        self.assertNotIn("Add git host to known_hosts", git_role)
        self.assertNotIn("lookup('env', 'SSH_KEY')", git_role)
        self.assertNotIn("provision_ssh_dir", git_role)
        self.assertNotIn("provision_ssh_key", git_role)
        self.assertNotIn("~/.ssh", git_role)
        self.assertNotIn("/root/.ssh", git_role)
        self.assertNotIn("/etc/hosts", git_role)

    def test_workspace_role_is_standalone_safe(self) -> None:
        defaults = (REPO_ROOT / "roles" / "00_ensure_workspace" / "defaults" / "main.yml").read_text(
            encoding="utf-8"
        )
        validate = (REPO_ROOT / "roles" / "00_ensure_workspace" / "tasks" / "validate.yaml").read_text(
            encoding="utf-8"
        )
        create_dirs = (REPO_ROOT / "roles" / "00_ensure_workspace" / "tasks" / "create_dirs.yaml").read_text(
            encoding="utf-8"
        )
        catalog = (REPO_ROOT / "group_vars" / "all" / "atlas-compute-provision.yml").read_text(encoding="utf-8")
        product_defaults = (
            REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_defaults.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("clusterctl", defaults.lower())
        self.assertNotIn("mxhash", defaults.lower())
        for needle in (
            "CLUSTER_WORKSPACE_ID",
            "CLUSTER_WORKSPACE_PARENT",
            "CLUSTER_WORKSPACE_ROOT",
            "cluster_workspace_id:",
            "cluster_workspace_parent:",
            "cluster_workspace_root:",
            "cluster_domain:",
        ):
            self.assertIn(needle, defaults, needle)
        self.assertIn("Resolve cluster workspace id", validate)
        self.assertIn("Resolve cluster workspace parent", validate)
        self.assertIn("Resolve cluster workspace root", validate)
        self.assertIn("Align controller / provision paths under resolved workspace root", validate)
        self.assertIn("CLUSTER_WORKSPACE_PARENT", validate)
        self.assertIn("cluster_domain", validate)
        self.assertIn("k8s_cluster_domain", validate)
        self.assertIn("provision_tf_workspace_dir", validate)
        self.assertIn("build_workdir", validate)
        self.assertIn("group_vars/all/atlas-compute-provision.yml", validate)
        self.assertNotIn("vars-file.yml", validate)
        self.assertIn("/tfstate-repo", defaults)
        self.assertIn("provision_tf_state_repo_prefix: tfstate", defaults)
        self.assertIn("provision_tf_state_cluster_path:", defaults)
        self.assertNotIn('clusters/{{ cluster_workspace_id }}', defaults)
        self.assertIn(".ansible_facts_cache", create_dirs)
        self.assertIn("logs", create_dirs)
        # Must not mkdir absolute /kubeconfig when controller_* unset
        self.assertNotIn('"/kubeconfig"', create_dirs)
        self.assertNotIn(" /kubeconfig", create_dirs)
        self.assertIn("provision_enforce_live_secrets: false", product_defaults)
        self.assertIn("example.com", catalog)

    def test_root_jenkinsfile_removed_from_product_path(self) -> None:
        self.assertFalse((REPO_ROOT / "Jenkinsfile").exists())
        self.assertTrue((REPO_ROOT / "examples" / "internal" / "Jenkinsfile").is_file())
        self.assertTrue((REPO_ROOT / "examples" / "internal" / "README.md").is_file())
        internal_readme = (REPO_ROOT / "examples" / "internal" / "README.md").read_text(encoding="utf-8")
        self.assertIn("not part of the standalone product path", internal_readme.lower())

    def test_rename_smoke_and_k8s_fixtures(self) -> None:
        rename_hosts = yaml.safe_load(
            (REPO_ROOT / "examples" / "rename_smoke" / "hosts.example.yml").read_text(encoding="utf-8")
        )
        rename_maps = yaml.safe_load(
            (REPO_ROOT / "examples" / "rename_smoke" / "maps.example.yml").read_text(encoding="utf-8")
        )
        self.assertIn("my_build_agents", rename_hosts["all"]["children"])
        self.assertNotIn("jslave", rename_hosts["all"]["children"])
        self.assertEqual(rename_maps["provision_stack"], "jenkins")
        self.assertIn("my_build_agents", rename_maps["provision_inventory_group_map_jenkins"])
        self.assertEqual(
            rename_maps["provision_inventory_group_map_jenkins"]["my_build_agents"],
            "jslave_vms",
        )
        self.assertEqual(rename_maps["provision_wait_hosts"], "my_build_agents")
        self.assertNotIn("mxhash", str(rename_hosts).lower())
        self.assertNotIn("mxhash", str(rename_maps).lower())

        k8s_hosts = yaml.safe_load(
            (REPO_ROOT / "examples" / "k8s" / "hosts.example.yml").read_text(encoding="utf-8")
        )
        k8s_maps = yaml.safe_load(
            (REPO_ROOT / "examples" / "k8s" / "maps.example.yml").read_text(encoding="utf-8")
        )
        for group in ("k8s_lbs", "k8s_masters", "k8s_workers"):
            self.assertIn(group, k8s_hosts["all"]["children"])
            self.assertIn(group, k8s_maps["provision_inventory_group_map_k8s"])
        self.assertEqual(k8s_maps["provision_stack"], "k8s")
        self.assertEqual(
            set(k8s_maps["provision_inventory_group_map_k8s"].values()),
            set(k8s_maps["provision_tf_module_map_k8s"].keys()),
        )

    def test_validate_documents_infra_wait_hosts_and_secrets(self) -> None:
        main = (REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "main.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("Assert infra maps when provision_stack is infra", main)
        self.assertIn("provision_inventory_group_map_infra", main)
        self.assertIn("Validate optional provision_wait_hosts groups exist", main)
        self.assertIn("provision_wait_hosts", main)
        self.assertIn("include_tasks: secrets.yml", main)
        self.assertIn("gitea_host | default('') | trim | upper != 'CHANGEME'", main)
        inv = (
            REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "validate_inventory_group.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("examples/rename_smoke", inv)
        secrets = (REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "secrets.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_enforce_live_secrets", secrets)
        self.assertIn("CHANGEME", secrets)
        self.assertIn("provision_pve_ssh_password", secrets)
        self.assertIn("provision_proxmox_token_secret", secrets)
        self.assertIn("provision_dns_key_secret", secrets)
        self.assertIn("provision_vm_cipassword", secrets)
        defaults = (REPO_ROOT / "roles" / "00_validate_provision" / "defaults" / "main.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_enforce_live_secrets: false", defaults)
        self.assertIn("provision_tf_state_git_push: false", defaults)
        fail_overlay = yaml.safe_load(
            (REPO_ROOT / "examples" / "enforce_secrets_fail.example.yml").read_text(encoding="utf-8")
        )
        ok_overlay = yaml.safe_load(
            (REPO_ROOT / "examples" / "enforce_secrets_ok.example.yml").read_text(encoding="utf-8")
        )
        self.assertTrue(fail_overlay["provision_enforce_live_secrets"])
        self.assertTrue(ok_overlay["provision_enforce_live_secrets"])
        for key in (
            "provision_pve_ssh_password",
            "provision_proxmox_token_secret",
            "provision_dns_key_secret",
            "provision_vm_cipassword",
        ):
            self.assertNotEqual(str(ok_overlay[key]).upper(), "CHANGEME", key)


if __name__ == "__main__":
    unittest.main()
