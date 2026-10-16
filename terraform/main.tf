# Root module: one resource group, then two child modules.
#   module.network -> VNet, subnet, NSG (+ subnet association)
#   module.compute -> public IP, NIC, Ubuntu VM bootstrapped by cloud-init

locals {
  common_tags = merge(var.tags, { environment = var.environment })
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.prefix}-${var.environment}-rg"
  location = var.location
  tags     = local.common_tags
}

module "network" {
  source = "./modules/network"

  prefix              = "${var.prefix}-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  vnet_cidr           = var.vnet_cidr
  subnet_cidr         = var.subnet_cidr
  ssh_source_cidr     = var.ssh_source_cidr
  tags                = local.common_tags
}

module "compute" {
  source = "./modules/compute"

  prefix              = "${var.prefix}-${var.environment}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = module.network.subnet_id
  vm_size             = var.vm_size
  admin_username      = var.admin_username
  ssh_public_key      = file(pathexpand(var.public_key_path))
  tags                = local.common_tags
}
