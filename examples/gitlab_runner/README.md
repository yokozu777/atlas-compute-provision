# GitLab runners — provision stack example

VM provisioning for `atlas-gitlab-runner` (no TF in the gitlab-runner repo).

## Switch / overlay

```bash
cp examples/gitlab_runner/hosts.example.yml inventory.yml
# edit group_vars/all/atlas-compute-provision.yml secrets (or EXTRA_VARS_FILE=examples/secrets.example.yml)
EXTRA_VARS_FILE=examples/gitlab_runner/provision.example.yml ./run.sh provision --tags 00_validate_provision
```

## Inventory excerpt

```yaml
all:
  children:
    gitlab_runners:
      hosts:
        192.168.1.50:
          hostname: runner01.example.com
          provision:
            vmid: "5300"
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

Runner install (`03_install_runner`) lives in **atlas-gitlab-runner** after OS bootstrap.
