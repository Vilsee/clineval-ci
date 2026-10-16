output "resource_group_name" {
  description = "Resource group that holds everything."
  value       = azurerm_resource_group.rg.name
}

output "public_ip" {
  description = "Public IP of the VM. Put this into the Jenkins 'azure-vm-ip' credential."
  value       = module.compute.public_ip
}

output "ssh_command" {
  description = "Ready-to-use SSH command."
  value       = "ssh -i ~/.ssh/azure_clineval ${var.admin_username}@${module.compute.public_ip}"
}

output "app_url" {
  description = "URL of the deployed application (nginx on port 80)."
  value       = "http://${module.compute.public_ip}"
}
