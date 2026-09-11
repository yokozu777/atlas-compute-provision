# Infra platform provision example

Uses `provision_stack: infra` with `infra_platform` → `proxmox_infra_node`.

```bash
INVENTORY=examples/infra/hosts.example.yml \
  EXTRA_VARS_FILE=examples/infra/provision.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

Orchestrator leaf: init from the `infra_edge` cluster template (see orchestrator `docs/stacks/infra-edge.md`).
