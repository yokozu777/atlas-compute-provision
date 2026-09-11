"""Provision stack layout tests."""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
STACKS = REPO_ROOT / "stacks"
EXAMPLES = REPO_ROOT / "examples"

KNOWN_STACKS = ("k8s", "infra", "mysql", "postgresql", "jenkins", "gitlab_runner", "redis", "kafka")


class ProvisionStacksLayoutTest(unittest.TestCase):
    def test_known_stacks_have_tf_templates(self) -> None:
        for name in KNOWN_STACKS:
            stack = STACKS / name
            self.assertTrue(stack.is_dir(), name)
            self.assertTrue((stack / "main.tf.j2").is_file(), f"{name}/main.tf.j2")
            self.assertTrue(
                (stack / "templates" / "variables.tf.j2").is_file(),
                f"{name}/templates/variables.tf.j2",
            )

    def test_jenkins_main_matches_k8s_module_loop(self) -> None:
        k8s_main = (STACKS / "k8s" / "main.tf.j2").read_text(encoding="utf-8")
        jenkins_main = (STACKS / "jenkins" / "main.tf.j2").read_text(encoding="utf-8")
        self.assertEqual(k8s_main, jenkins_main)

    def test_infra_main_matches_k8s_module_loop(self) -> None:
        k8s_main = (STACKS / "k8s" / "main.tf.j2").read_text(encoding="utf-8")
        infra_main = (STACKS / "infra" / "main.tf.j2").read_text(encoding="utf-8")
        self.assertEqual(k8s_main, infra_main)

    def test_infra_example_files_exist(self) -> None:
        example_dir = EXAMPLES / "infra"
        self.assertTrue((example_dir / "hosts.example.yml").is_file())
        self.assertTrue((example_dir / "provision.example.yml").is_file())
        self.assertTrue((example_dir / "README.md").is_file())
        provision = yaml.safe_load(
            (example_dir / "provision.example.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(provision["provision_stack"], "infra")
        inv_map = provision["provision_inventory_group_map_infra"]
        tf_map = provision["provision_tf_module_map_infra"]
        self.assertEqual(inv_map, {"infra_platform": "infra_node"})
        self.assertEqual(tf_map, {"infra_node": "proxmox_infra_node"})
        self.assertEqual(set(inv_map.values()), set(tf_map.keys()))
        hosts = yaml.safe_load(
            (example_dir / "hosts.example.yml").read_text(encoding="utf-8")
        )
        self.assertIn("infra_platform", hosts["all"]["children"])

    def test_postgresql_main_matches_k8s_module_loop(self) -> None:
        k8s_main = (STACKS / "k8s" / "main.tf.j2").read_text(encoding="utf-8")
        postgresql_main = (STACKS / "postgresql" / "main.tf.j2").read_text(encoding="utf-8")
        self.assertEqual(k8s_main, postgresql_main)

    def test_stack_variables_templates_use_provision_inventory_index(self) -> None:
        for name in KNOWN_STACKS:
            template = (STACKS / name / "templates" / "variables.tf.j2").read_text(encoding="utf-8")
            self.assertIn("provision_inventory_groups_index", template, name)
            self.assertIn("provision_dns_tf_manage_a_records", template, name)
            self.assertIn('clone   = "{{ host.provision.clone }}"', template, name)
            self.assertIn('cluster_id      = "{{ cluster_id | default(cluster_workspace_id, true) }}"', template, name)
            self.assertIn('inventory_group = "{{ inventory_group }}"', template, name)
            self.assertIn('inventory_ip    = "{{ ip }}"', template, name)
            self.assertNotIn("provision_pve_templates[host.provision.clone].name", template, name)
            # PVE VM name = full inventory hostname (FQDN), quoted HCL map key.
            self.assertIn('"{{ host.hostname }}" = {', template, name)
            self.assertNotIn("host.hostname.split('.')[0]", template, name)
            main = (STACKS / name / "main.tf.j2").read_text(encoding="utf-8")
            self.assertIn("manage_dns_a_records", main, name)

    def test_proxmox_vm_module_gates_dns_a_records(self) -> None:
        module = (REPO_ROOT / "modules" / "proxmox_vm" / "main.tf").read_text(encoding="utf-8")
        variables = (REPO_ROOT / "modules" / "proxmox_vm" / "variables.tf").read_text(encoding="utf-8")
        self.assertIn('resource "dns_a_record_set" "vms"', module)
        self.assertIn("var.manage_dns_a_records ? var.vms : {}", module)
        self.assertIn('name      = split(".", each.key)[0]', module)
        self.assertIn("manage_dns_a_records", variables)
        catalog = (REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_defaults.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("provision_dns_tf_manage_a_records: false", catalog)

    def test_proxmox_vm_module_sets_pve_desc_once(self) -> None:
        module = (REPO_ROOT / "modules" / "proxmox_vm" / "main.tf").read_text(encoding="utf-8")
        variables = (REPO_ROOT / "modules" / "proxmox_vm" / "variables.tf").read_text(encoding="utf-8")
        self.assertIn('desc = join("\\n", [', module)
        self.assertIn('"### Provision"', module)
        self.assertIn(
            'format("- **created:** %s", formatdate("YYYY-MM-DD\'T\'HH:mm:ssZ", timestamp()))',
            module,
        )
        self.assertIn('format("- **cluster:** `%s`", each.value.cluster_id)', module)
        self.assertIn('format("- **group:** `%s`", each.value.inventory_group)', module)
        self.assertIn('format("- **ip:** `%s`", each.value.inventory_ip)', module)
        self.assertIn('format("- **clone:** `%s`", coalesce(each.value.clone, "-"))', module)
        self.assertIn('"- **full_clone:** %s (%s)"', module)
        self.assertIn("ignore_changes = [desc]", module)
        self.assertIn("cluster_id", variables)
        self.assertIn("inventory_group", variables)
        self.assertIn("inventory_ip", variables)

    def test_provision_playbook_uses_stack_maps_group_vars(self) -> None:
        playbook = (REPO_ROOT / "playbooks" / "provision_nodes.yaml").read_text(encoding="utf-8")
        maps = (
            REPO_ROOT / "playbooks" / "group_vars" / "all" / "provision_stack_maps.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("provision_inventory_group_map_k8s", playbook)
        self.assertIn("provision_inventory_group_map_' ~ provision_stack", maps)
        self.assertIn("provision_tf_module_map_' ~ provision_stack", maps)

    def test_provision_playbook_waits_for_ssh_after_tf_apply(self) -> None:
        playbook = (REPO_ROOT / "playbooks" / "provision_nodes.yaml").read_text(encoding="utf-8")
        wait_block = playbook.split("Wait for SSH on provisioned nodes after terraform apply", 1)[1]
        self.assertIn("provision_wait_ssh", wait_block)
        self.assertIn("wait_for_connection", wait_block)
        self.assertIn("hosts: localhost", wait_block)
        self.assertIn("provision_inventory_group_map.keys()", wait_block)
        self.assertIn("delegate_to", wait_block)
        self.assertNotIn("pgsql_etcd_cluster", wait_block)
        apply_block = playbook.split("- role: 10_tf_apply", 1)[1]
        wait_after_apply = apply_block.split("Wait for SSH on provisioned nodes after terraform apply", 1)[1]
        self.assertNotIn("11_tf_state_push", wait_after_apply.split("- hosts: localhost", 1)[0])
        self.assertIn("provision_mode in ['apply', 'recreate']", wait_block)

    def test_validate_documents_jenkins_stack(self) -> None:
        validate = (
            REPO_ROOT / "roles" / "00_validate_provision" / "tasks" / "main.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("jenkins", validate)
        self.assertIn("provision_inventory_group_map_' ~ provision_stack", validate)

    def test_gitlab_runner_example_files_exist(self) -> None:
        example_dir = EXAMPLES / "gitlab_runner"
        self.assertTrue((example_dir / "hosts.example.yml").is_file())
        self.assertTrue((example_dir / "provision.example.yml").is_file())
        self.assertTrue((example_dir / "README.md").is_file())
        provision = yaml.safe_load(
            (example_dir / "provision.example.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(provision["provision_stack"], "gitlab_runner")
        inv_map = provision["provision_inventory_group_map_gitlab_runner"]
        tf_map = provision["provision_tf_module_map_gitlab_runner"]
        self.assertEqual(set(inv_map.keys()), {"gitlab_runners"})
        self.assertEqual(set(inv_map.values()), set(tf_map.keys()))

    def test_postgresql_example_files_exist(self) -> None:
        example_dir = EXAMPLES / "postgresql"
        self.assertTrue((example_dir / "hosts.example.yml").is_file())
        self.assertTrue((example_dir / "provision.example.yml").is_file())
        self.assertTrue((example_dir / "README.md").is_file())

    def test_kafka_example_files_exist(self) -> None:
        example_dir = EXAMPLES / "kafka"
        self.assertTrue((example_dir / "hosts.example.yml").is_file())
        self.assertTrue((example_dir / "provision.example.yml").is_file())
        self.assertTrue((example_dir / "README.md").is_file())
        provision = yaml.safe_load(
            (example_dir / "provision.example.yml").read_text(encoding="utf-8")
        )
        self.assertEqual(provision["provision_stack"], "kafka")
        inv_map = provision["provision_inventory_group_map_kafka"]
        tf_map = provision["provision_tf_module_map_kafka"]
        self.assertEqual(set(inv_map.keys()), {"kafka_controllers", "kafka_brokers"})
        self.assertEqual(set(inv_map.values()), set(tf_map.keys()))
        hosts = yaml.safe_load(
            (example_dir / "hosts.example.yml").read_text(encoding="utf-8")
        )
        children = hosts["all"]["children"]["kafka"]["children"]
        self.assertIn("kafka_controllers", children)
        self.assertIn("kafka_brokers", children)

    def test_postgresql_example_maps_three_tf_modules(self) -> None:
        provision = yaml.safe_load(
            (EXAMPLES / "postgresql" / "provision.example.yml").read_text(encoding="utf-8")
        )
        inv_map = provision["provision_inventory_group_map_postgresql"]
        tf_map = provision["provision_tf_module_map_postgresql"]
        self.assertEqual(
            set(inv_map.keys()),
            {"pgsql_etcd_cluster", "pgsql_cluster", "pgsql_lbs"},
        )
        self.assertEqual(len(tf_map), 3)
        self.assertEqual(set(inv_map.values()), set(tf_map.keys()))

    def test_postgresql_example_hosts_nested_under_parent(self) -> None:
        hosts = yaml.safe_load(
            (EXAMPLES / "postgresql" / "hosts.example.yml").read_text(encoding="utf-8")
        )
        children = hosts["all"]["children"]["postgresql"]["children"]
        self.assertIn("pgsql_etcd_cluster", children)
        self.assertIn("pgsql_cluster", children)
        self.assertIn("pgsql_lbs", children)
        for group in children.values():
            self.assertGreater(len(group["hosts"]), 0)
            host = next(iter(group["hosts"].values()))
            self.assertEqual(host["provision"]["clone"], "ubuntu-noble")
            self.assertRegex(str(host["provision"]["disks"][0]["size"]), r"^\d+$")

    def test_build_provision_inventory_index_flattens_nested_children(self) -> None:
        task = (
            REPO_ROOT
            / "roles"
            / "00_validate_provision"
            / "tasks"
            / "build_provision_inventory_index.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn("Merge nested inventory group children", task)
        self.assertIn("item.value.children is defined", task)


if __name__ == "__main__":
    unittest.main()
