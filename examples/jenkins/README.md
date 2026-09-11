# Jenkins build agents — provision stack example

VM provisioning for `atlas-jenkins-agent` (no TF in the jenkins-agent repo).

Default standalone path uses `group_vars/all/atlas-compute-provision.yml` (stack `jenkins`) + `inventory-example.yml`.

## Switch / overlay

```bash
cp inventory-example.yml inventory.yml   # or use examples/jenkins/hosts.example.yml
# edit group_vars/all/atlas-compute-provision.yml secrets (or EXTRA_VARS_FILE=examples/secrets.example.yml)
./run.sh provision --tags 00_validate_provision
```

Stack-only overlay (optional):

```bash
EXTRA_VARS_FILE=examples/jenkins/provision.example.yml ./run.sh provision --tags 00_validate_provision
```

## Inventory excerpt

```yaml
all:
  children:
    jslave:
      hosts:
        192.168.1.50:
          hostname: jslave01.example.com
          provision:
            vmid: "5200"
            sockets: 1
            cores: 8
            memory: 16384
            numa: false
            clone: ubuntu-noble
            disks:
              - size: "100G"
                slot: 0
                storage: local-lvm
```

Agent install (`03_install_jslave`) lives in **atlas-jenkins-agent** after OS bootstrap.
