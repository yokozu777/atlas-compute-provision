variable "vms" {
  description = "VM configurations"
  type = map(object({
    vmid             = string
    sockets          = number
    cores            = number
    memory           = number
    ip               = string
    numa             = bool
    clone            = optional(string)
    cluster_id       = string
    inventory_group  = string
    inventory_ip     = string
    disks = list(object({
      size    = number
      slot    = number
      storage = string
      wwn     = optional(string)
      serial  = optional(string)
    }))
  }))
}

variable "proxmox_target_node" {
  type = string
}

variable "dns_zone" {
  type = string
}

variable "manage_dns_a_records" {
  description = "When true, create/update apex A records via Terraform RFC2136 after VM create"
  type        = bool
  default     = false
}

variable "dns_a_ttl" {
  description = "TTL for Terraform-managed DNS A records"
  type        = number
  default     = 300
}

variable "nameserver" {
  type = string
}

variable "searchdomain" {
  type = string
}

variable "vm_full_clone" {
  type = bool
}

variable "vm_cloudinit_storage" {
  type = string
}

variable "vm_disk_cache" {
  type = string
}

variable "vm_disk_format" {
  type = string
}

variable "vm_network_bridge" {
  type = string
}

variable "vm_ciuser" {
  type = string
}

variable "vm_cipassword" {
  type      = string
  sensitive = true
}

variable "ssh_keys" {
  type = string
}
