# Kafka KRaft HA — provision stack example

VM provisioning for `atlas-kafka` (no TF in the kafka repo).
Scheme B: dedicated controllers + brokers. No ZooKeeper. No L4 VIP.

## Standalone

```bash
INVENTORY=examples/kafka/hosts.example.yml \
  EXTRA_VARS_FILE=examples/kafka/provision.example.yml \
  ./run.sh provision --tags 00_validate_provision
```

Fill secrets via `group_vars/all/atlas-compute-provision.yml` or `examples/secrets.example.yml`.

## Maps excerpt

```yaml
provision_stack: kafka

provision_inventory_group_map_kafka:
  kafka_controllers: kafka_controller_node
  kafka_brokers: kafka_broker_node

provision_tf_module_map_kafka:
  kafka_controller_node: proxmox_kafka_controller
  kafka_broker_node: proxmox_kafka_broker
```

## Inventory notes

Parent group `kafka` is optional for nesting; provision flattens `all.children.*.children`.
`provision.clone` is the PVE template name (Terraform clone source). Optional
`provision_pve_templates` is a soft allowlist of those names; omit it when golden
templates already exist on PVE (default standalone catalog still lists `ubuntu-noble`).

See `hosts.example.yml` and `provision.example.yml` in this directory.
