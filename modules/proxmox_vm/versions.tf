terraform {
  required_providers {
    proxmox = {
      source = "telmate/proxmox"
    }
    dns = {
      source = "hashicorp/dns"
    }
  }
}
