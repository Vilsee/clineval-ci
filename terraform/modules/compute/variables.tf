variable "prefix" {
  description = "Name prefix for resources in this module."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group."
  type        = string
}

variable "subnet_id" {
  description = "Subnet the VM's network interface joins."
  type        = string
}

variable "vm_size" {
  description = "VM size."
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  description = "Admin user on the VM."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key" {
  description = "Contents of the SSH public key (not the path)."
  type        = string
}

variable "os_disk_type" {
  description = "Storage type for the OS disk."
  type        = string
  default     = "Standard_LRS"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
