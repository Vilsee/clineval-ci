variable "prefix" {
  description = "Short name prefix used for every resource."
  type        = string
  default     = "clineval"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.prefix))
    error_message = "prefix must be 2-21 characters: lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod). Becomes part of every resource name."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging or prod."
  }
}

variable "location" {
  description = "Azure region. Change it if the VM size is unavailable in your subscription."
  type        = string
  default     = "centralindia"
}

variable "vnet_cidr" {
  description = "Address space of the virtual network."
  type        = string
  default     = "10.10.0.0/16"
}

variable "subnet_cidr" {
  description = "Address range of the application subnet (must sit inside vnet_cidr)."
  type        = string
  default     = "10.10.1.0/24"
}

variable "vm_size" {
  description = "VM size."
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  description = "Admin user on the VM (Jenkins deploys as this user)."
  type        = string
  default     = "azureuser"
}

variable "public_key_path" {
  description = "Path to the SSH public key that Jenkins uses to deploy."
  type        = string
  default     = "~/.ssh/azure_clineval.pub"
}

variable "ssh_source_cidr" {
  description = "Source CIDR allowed to SSH to the VM. '*' is fine for a short demo; restrict it afterwards."
  type        = string
  default     = "*"
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default = {
    project = "clineval-ci"
    managed = "terraform"
  }
}
