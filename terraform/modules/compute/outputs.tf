output "public_ip" {
  description = "Public IP address of the VM."
  value       = azurerm_public_ip.pip.ip_address
}

output "private_ip" {
  description = "Private IP address of the VM."
  value       = azurerm_network_interface.nic.private_ip_address
}

output "vm_name" {
  description = "Name of the virtual machine."
  value       = azurerm_linux_virtual_machine.vm.name
}
