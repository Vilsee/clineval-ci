output "public_ip" {
  description = "Public IP of the VM (put this into the Jenkins 'azure-vm-ip' credential)"
  value       = azurerm_public_ip.pip.ip_address
}

output "ssh_command" {
  value = "ssh -i ~/.ssh/azure_clineval ${var.admin_username}@${azurerm_public_ip.pip.ip_address}"
}

output "app_url" {
  value = "http://${azurerm_public_ip.pip.ip_address}"
}
