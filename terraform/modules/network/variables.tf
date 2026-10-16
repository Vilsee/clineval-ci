variable "prefix" {
  description = "Name prefix for resources in this module."
  type        = string
}

variable "location" {
  description = "Azure region."
  type        = string
}

variable "resource_group_name" {
  description = "Existing resource group to create the network in."
  type        = string
}

variable "vnet_cidr" {
  description = "Address space of the virtual network."
  type        = string
}

variable "subnet_cidr" {
  description = "Address range of the subnet."
  type        = string
}

variable "ssh_source_cidr" {
  description = "Source CIDR allowed to SSH."
  type        = string
  default     = "*"
}

variable "inbound_rules" {
  description = "Extra inbound NSG rules, keyed by name. Priority must be unique and above 120."
  type = map(object({
    priority = number
    port     = string
    source   = string
  }))
  default = {}
}

variable "tags" {
  description = "Tags applied to every resource."
  type        = map(string)
  default     = {}
}
