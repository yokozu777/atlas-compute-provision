# Rename-smoke — inventory group rename contract

This stack keeps `provision_stack: jenkins` and the TF module name `proxmox_jslaves`,
but renames the **inventory group** from `jslave` to `my_build_agents`.

```bash
INVENTORY=examples/rename_smoke/hosts.example.yml \
  EXTRA_VARS_FILE=examples/rename_smoke/maps.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

When renaming groups, update **together**:

1. Inventory group name(s) in `hosts` / `inventory.yml`
2. Keys of `provision_inventory_group_map_<stack>`
3. Optional `provision_wait_hosts` (and any orchestrator `--limit` lists)

Do **not** rename TF map values / module names unless you also change `stacks/<stack>/`
templates — those names are the Terraform variable / module contract.
