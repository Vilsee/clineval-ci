# One-off configuration that creates the Azure Storage account used for remote state.
# It deliberately uses local state itself (chicken-and-egg). Run it once, then point the
# main configuration's backend at the storage account it creates.

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "location" {
  description = "Azure region for the state storage."
  type        = string
  default     = "centralindia"
}

variable "prefix" {
  description = "Prefix (lowercase letters and digits only) for the storage account."
  type        = string
  default     = "clineval"
}

resource "random_string" "suffix" {
  length  = 6
  upper   = false
  special = false
}

resource "azurerm_resource_group" "state" {
  name     = "${var.prefix}-tfstate-rg"
  location = var.location
}

resource "azurerm_storage_account" "state" {
  name                     = "${var.prefix}tf${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.state.name
  location                 = azurerm_resource_group.state.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"

  blob_properties {
    versioning_enabled = true
  }
}

resource "azurerm_storage_container" "state" {
  name                  = "tfstate"
  storage_account_name  = azurerm_storage_account.state.name
  container_access_type = "private"
}

output "storage_account_name" {
  description = "Paste this into backend.tf (storage_account_name)."
  value       = azurerm_storage_account.state.name
}

output "resource_group_name" {
  value = azurerm_resource_group.state.name
}
