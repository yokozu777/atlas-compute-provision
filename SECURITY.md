# Security

## Reporting

If you discover a security issue in this repository, please open a private report with the
maintainers (do not file a public issue with exploit details or credentials).

## Secrets in this repo

Do **not** commit:

- Proxmox API tokens / SSH passwords (`provision_proxmox_token_secret`, `provision_pve_ssh_password`)
- DNS TSIG / RFC2136 secrets (`provision_dns_key_secret` and related)
- Terraform remote-state git credentials (`gitea_host`, deploy keys, HTTPS tokens)
- SSH private keys used for provision / wait-SSH
- deprecated monolithic `secrets.yml` / `*.vault` / live `*.tfvars`
- live inventory with production hosts (`inventory.yml`, local `hosts`)
- terraform state blobs (`*.tfstate`, `.terraform/`)

Prefer `group_vars/all/atlas-compute-provision.secrets.yml` with Ansible Vault (trackable; do **not** gitignore). Standalone operators may also use `EXTRA_VARS_FILE` / `examples/secrets.example.yml` **outside** the tree. A monolithic `secrets.yml` is deprecated and must not hold live credentials in git.

Prefer environment / external secret stores in production.

Tracked examples intentionally use inert placeholders only (`CHANGEME` in
`group_vars/all/atlas-compute-provision.yml` and `examples/secrets.example.yml`). Set
`provision_enforce_live_secrets: true` before a live apply so validate rejects
leftover placeholders.

## Git history note (pre-publish)

Tracked product defaults previously used the org lab DNS suffix `mxhash.com`:

- `vars-build.yml` — `dns_domain_suffix: mxhash.com` (introduced with the file in `3738c82`)
- `README.md` — public Gitea URL `gitea.mxhash.com` (from `4694296`)
- `examples/jenkins/README.md` — sample hostname `*.dev-mxhash.com`

Working-tree defaults and examples now use neutral `example.com` values. Org lab overlays
belong in the orchestrator inventory, not in this repository’s defaults. The historical
blobs remain reachable until history is rewritten.

No embedded Gitea HTTPS credentials or lab passwords (`Welcomeback*`) were found in reachable
product history of this repository. Still assume any historical org hostname blobs are
undesirable on a public remote.

The root `Jenkinsfile` was an org-coupled Jenkins pipeline (site job names, Cyrillic operator
messages). It is no longer part of the product path; a scrubbed sample may live under
`examples/internal/` for reference only.

Product sources (`roles/`, `playbooks/`, `group_vars/`, `stacks/`, `modules/`, examples,
inventory example, runner) must stay free of org hostnames, lab credentials, and
non-English operator-facing copy.

Guardrails: `scripts/check-no-hardcoded-domains.sh`, `tests/test_compute_provision_layout.py`
(fingerprint + Cyrillic + secret-material + orchestrator-path scans), and `./tests/run_ci.sh`
/ `.github/workflows/ci.yml`.

Before making this repository public:

1. Confirm no live secrets were ever pushed to remotes (rotate anything that might have been).
2. Rewrite history (`git filter-repo` / BFG) to purge org-hostname blobs, or publish from a
   fresh orphan branch that contains only the cleaned tree.
3. Assume historical blobs remain reachable until remotes are rewritten / force-replaced.
