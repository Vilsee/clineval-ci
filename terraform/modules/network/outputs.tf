output "vnet_name" {
  description = "Name of the virtual network."
  value       = azurerm_virtual_network.vnet.name
}

output "subnet_id" {
  description = "ID of the application subnet."
  value       = azurerm_subnet.subnet.id
}

output "nsg_id" {
  description = "ID of the network security group."
  value       = azurerm_network_security_group.nsg.id
}
