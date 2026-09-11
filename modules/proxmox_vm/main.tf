resource "proxmox_vm_qemu" "vms" {
  for_each         = var.vms
  os_type          = "cloud-init"
  boot             = "order=scsi0"
  vmid             = each.value.vmid
  name             = each.key
  target_node      = var.proxmox_target_node
  clone            = each.value.clone
  full_clone       = var.vm_full_clone
  # PVE notes: Markdown (CommonMark); set once at create; ignore later drift.
  desc = join("\n", [
    "### Provision",
    format("- **created:** %s", formatdate("YYYY-MM-DD'T'HH:mm:ssZ", timestamp())),
    format("- **cluster:** `%s`", each.value.cluster_id),
    format("- **group:** `%s`", each.value.inventory_group),
    format("- **ip:** `%s`", each.value.inventory_ip),
    format("- **clone:** `%s`", coalesce(each.value.clone, "-")),
    format(
      "- **full_clone:** %s (%s)",
      tostring(var.vm_full_clone),
      var.vm_full_clone ? "full" : "linked",
    ),
  ])
  bios             = "seabios"
  agent            = 1
  automatic_reboot = true
  onboot           = true
  hotplug          = 0
  numa             = each.value.numa
  tablet           = false
  sockets          = each.value.sockets
  cores            = each.value.cores
  memory           = each.value.memory
  scsihw           = "virtio-scsi-single"
  ciuser           = var.vm_ciuser
  cipassword       = var.vm_cipassword
  nameserver       = var.nameserver
  searchdomain     = var.searchdomain
  ipconfig0        = each.value.ip
  sshkeys          = var.ssh_keys

  lifecycle {
    ignore_changes = [desc]
  }

  dynamic "disk" {
    for_each = toset(["cloudinit"])
    content {
      slot    = "ide2"
      type    = "cloudinit"
      storage = var.vm_cloudinit_storage
      backup  = false
    }
  }

  dynamic "disk" {
    for_each = { for idx, disk in each.value.disks : idx => disk }
    content {
      slot               = "scsi${disk.value.slot}"
      type               = "disk"
      storage            = disk.value.storage
      size               = disk.value.size
      cache              = var.vm_disk_cache
      format             = var.vm_disk_format
      backup             = false
      emulatessd         = true
      discard            = true
      iothread           = true
      replicate          = true
      mbps_r_burst       = 0.0
      mbps_r_concurrent  = 0.0
      mbps_wr_burst      = 0.0
      mbps_wr_concurrent = 0.0
      wwn                = lookup(disk.value, "wwn", null)
      serial             = lookup(disk.value, "serial", null)
    }
  }

  serial {
    id   = 0
    type = "socket"
  }

  network {
    id       = 0
    model    = "virtio"
    bridge   = var.vm_network_bridge
    firewall = false
  }
}

# Optional apex A records via RFC2136 (hashicorp/dns). Gated by manage_dns_a_records
# (inventory: provision_dns_tf_manage_a_records). When false, apex A stays with BIND.
# Relative owner name is the first FQDN label (PVE/TF map key is the full hostname).
resource "dns_a_record_set" "vms" {
  for_each = var.manage_dns_a_records ? var.vms : {}

  zone      = var.dns_zone
  name      = split(".", each.key)[0]
  addresses = [split("/", split("=", each.value.ip)[1])[0]]
  ttl       = var.dns_a_ttl
}
