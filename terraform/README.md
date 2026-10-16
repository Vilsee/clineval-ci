# Terraform: Azure infrastructure for ClinEval-CI

Provisions everything the Jenkins pipeline deploys to: a resource group, virtual network, subnet,
network security group, public IP, network interface and an Ubuntu 22.04 VM running nginx and a
systemd service (installed by cloud-init).

## Layout

```
terraform/
  versions.tf               provider + Terraform version constraints
  main.tf                   root module: resource group + calls the two modules
  variables.tf              inputs with validation (prefix, environment, CIDRs, VM size, ...)
  outputs.tf                public_ip, ssh_command, app_url, resource_group_name
  terraform.tfvars.example  copy to terraform.tfvars
  backend.tf.example        remote-state backend (Azure Blob Storage)
  modules/
    network/                VNet, subnet, NSG (dynamic rules), subnet association
    compute/                public IP, NIC, VM, cloud-init.yaml
  bootstrap/                one-off config that creates the remote-state storage account
```

## Design choices

| Concern | Choice |
|---|---|
| Modularity | `network` and `compute` modules with typed, documented inputs and outputs; the root only wires them together |
| Variables | Every tunable is a variable; `prefix` and `environment` validated; CIDRs and VM size configurable |
| Outputs | `public_ip` feeds the Jenkins `azure-vm-ip` credential; `ssh_command` and `app_url` for convenience |
| NSG rules | Built with a `dynamic` block from a map, so extra ports are added through `inbound_rules`, not copy-paste |
| State | Local by default; optional Azure Blob remote state (versioned, private container) created by `bootstrap/` |
| Secrets | No keys in code; the SSH public key is read from a file path; `terraform.tfvars` and state are git-ignored |
| Naming and tags | `<prefix>-<environment>-<resource>` plus common tags on everything |

## Usage

```powershell
az login
ssh-keygen -t ed25519 -f "$HOME\.ssh\azure_clineval" -N '""'

cd terraform
Copy-Item terraform.tfvars.example terraform.tfvars    # edit if needed
terraform init
terraform fmt -recursive
terraform validate
terraform plan -out tfplan
terraform apply tfplan
terraform output public_ip
```

Commit the generated `.terraform.lock.hcl` so provider versions are pinned for everyone.

## Optional: remote state

```powershell
cd bootstrap
terraform init
terraform apply
terraform output storage_account_name
cd ..
Copy-Item backend.tf.example backend.tf     # paste the storage account name into it
terraform init -migrate-state
```

## Tear down

```powershell
terraform destroy
```
(The `bootstrap/` storage account is separate; destroy it from its own folder if you created it.)

## Status

Written to match the azurerm 3.x provider. Syntax is parse-checked; run `terraform validate` and
`terraform plan` on your machine before the first `apply`.
