# Minimal k8s validate smoke

```bash
INVENTORY=examples/k8s/hosts.example.yml \
  EXTRA_VARS_FILE=examples/k8s/maps.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

Uses `provision_stack: k8s` (no infra maps).
For infra-enabled layouts, also define `provision_*_map_infra` and an `infra_platform` group.
