terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.100"
    }
  }

  # Remote state (optional but recommended): run ./bootstrap once, then copy
  # backend.tf.example to backend.tf and run `terraform init -migrate-state`.
}

provider "azurerm" {
  features {}
}
