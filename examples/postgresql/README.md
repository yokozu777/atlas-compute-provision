# PostgreSQL HA cluster — provision stack example

VM provisioning for `atlas-postgresql` (no TF in the postgresql repo).

## Standalone

```bash
INVENTORY=examples/postgresql/hosts.example.yml \
  EXTRA_VARS_FILE=examples/postgresql/provision.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

Fill secrets via `group_vars/all/atlas-compute-provision.yml` or `examples/secrets.example.yml`.

## Maps excerpt

```yaml
provision_stack: postgresql

provision_inventory_group_map_postgresql:
  pgsql_etcd_cluster: pgsql_etcd_node
  pgsql_cluster: pgsql_cluster_node
  pgsql_lbs: pgsql_lbs_node

provision_tf_module_map_postgresql:
  pgsql_etcd_node: proxmox_pgsql_etcd
  pgsql_cluster_node: proxmox_pgsql_cluster
  pgsql_lbs_node: proxmox_pgsql_lbs
```

## Inventory notes

Parent group `postgresql` is optional for nesting; stack groups may also be listed
directly under `all`. Provision resolves both layouts via `provision_inventory_groups_index`
(flattening any `all.children.*.children` nesting).

`provision.clone` is the PVE template name (Terraform clone source). Optional
`provision_pve_templates` is a soft allowlist of those names; omit it when golden
templates already exist on PVE (default standalone catalog still lists `ubuntu-noble`).

Cluster install (Patroni, PgBouncer, HAProxy) lives in **atlas-postgresql** after OS bootstrap.
