variable "prefix" {
  description = "Name prefix for all resources"
  type        = string
  default     = "clineval"
}

variable "location" {
  description = "Azure region (change if the VM size is unavailable in your subscription)"
  type        = string
  default     = "centralindia"
}

variable "vm_size" {
  description = "VM size"
  type        = string
  default     = "Standard_B1s"
}

variable "admin_username" {
  type    = string
  default = "azureuser"
}

variable "public_key_path" {
  description = "Path to the SSH public key that Jenkins will use to deploy"
  type        = string
  default     = "~/.ssh/azure_clineval.pub"
}

variable "ssh_source_cidr" {
  description = "Source CIDR allowed to SSH. '*' is fine for a short demo; restrict it afterwards."
  type        = string
  default     = "*"
}

variable "tags" {
  type = map(string)
  default = {
    project = "clineval-ci"
    managed = "terraform"
  }
}
