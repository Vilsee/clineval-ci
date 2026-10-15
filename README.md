# ClinEval-CI: Automated Deployment with Terraform, Azure and Jenkins

ClinEval-CI is a small web app (FastAPI + dashboard) that runs a **regression gate for clinical AI agents**.
The same project is deployed with a full DevOps pipeline:

```
 Developer ──push──▶ GitHub ──(Poll SCM / webhook)──▶ Jenkins
                                                        │ 1 Checkout
                                                        │ 2 Build (venv + pip)
                                                        │ 3 Unit tests (pytest)
                                                        │ 4 Eval gate  ◀── blocks a regressed agent (exit 1)
                                                        │ 5 Deploy (rsync + ssh)
                                                        ▼
                    Terraform ──provisions──▶ Azure: Resource Group, VNet, Subnet, NSG,
                                              Public IP, NIC, Ubuntu VM (nginx + uvicorn + systemd)
                                                        │ 6 Smoke test (curl /api/health)
                                                        ▼
                                              http://<public-ip>/  (live dashboard)
```

> Disclaimer: synthetic demo data only. Not medical software and not clinically validated.

## What is in the product (v0.2)

| Area | Features |
|---|---|
| **Gate** | Versioned YAML test cases, forbidden-behaviour detectors (phrase, tool, tool-without-confirmation), tool-order checks, repeated trials with seeded randomness |
| **Statistics** | Paired bootstrap confidence intervals, per-tag metrics (safety, triage, medication, general), PASS / WARN / BLOCK verdicts, inconclusive handling for small suites |
| **Policy** | `gate.yaml` (tolerance, confidence, minimum cases, critical blocking, flaky quarantine, token budget), reviewed like code |
| **Flaky quarantine** | Non-safety cases that are flaky in the baseline are reported but cannot block a merge |
| **Waivers** | Case + reason + approver + expiry, in the UI and in `waivers.yaml`; expired waivers are ignored |
| **Cost guard** | Token estimate per trial; warns when the candidate exceeds the configured multiple of baseline |
| **Audit trail** | Hash-chained run history; any edited record is detected and named; one-click evidence bundle |
| **Exports** | Markdown report, JUnit XML (Jenkins and GitHub), JSON, run JSON |
| **Playground** | Send one message to any agent version and see the reply plus every tool call |
| **Case linter** | Validates schema and severities and flags phone, MRN and email patterns before a case is committed |
| **CI** | `Jenkinsfile`, GitHub Actions workflow that comments the report on pull requests, Dockerfile |

## UI design (built with the taste skills)

The UI was designed using the skills installed by `npx skills add Leonxlnx/taste-skill`:

- **Landing page (`/`)** follows `design-taste-frontend` (tasteskill v2): direction dealt by its script (`product-performs`, warm black and gold, Schibsted Grotesk, hero fragment on a notched stage, sentences with switches, call-and-response, question index, tile footer). The hero fragment is real: flip v1 to v2 and it shows the actual gate result from a real run (`python scripts/build_landing_data.py` regenerates the data). The skill's `lint.mjs` reports 0 FAIL and 0 WARN.
- **Dashboard (`/app`)** follows `minimalist-ui` (the taste skill says its v2 is for public pages, not app screens): warm monochrome, Newsreader serif headings, flat bento tiles, `1px #EAEAEA` borders, pastel status badges, no gradients.

Not done: the skill's browser `inspect.mjs` (needs Chrome) and its real-photo sourcing (`assets.mjs` needs network access), so those checks were not run. The landing page uses live interface fragments instead of photographs. Run the inspector yourself once (see the commands below).

## Extra API endpoints

`POST /api/try` (playground) | `POST /api/lint` | `GET/POST/DELETE /api/waivers` | `POST /api/baseline/{id}` | `GET /api/compare/report.md` | `GET /api/compare/junit.xml` | `GET /api/audit` | `GET /api/evidence` | `GET /api/policy` | interactive docs at `/docs`

## Assignment requirement checklist (for your professor)

| Requirement | Where it is done |
|---|---|
| Terraform: Resource Group, VNet, Subnet, NIC, Public IP, VM | `terraform/main.tf` (+ NSG, cloud-init) |
| Terraform config stored in Git | `terraform/` folder in this repo |
| Jenkins installed and configured | `jenkins/` (Docker) , Step 5 |
| Pipeline: checkout, build, deploy | `Jenkinsfile` |
| Simple web app (Python) | `clineval/` (FastAPI + HTML dashboard) |
| GitHub version control | Step 3 |
| Webhook or Poll SCM trigger | `pollSCM('H/2 * * * *')` in `Jenkinsfile`; webhook optional (Step 8) |
| Continuous Deployment on every commit | Step 7 demo |

---

## Step 0: Prerequisites

Install: Git, Python 3.10+, Docker Desktop, Terraform (>= 1.5), Azure CLI, and have a GitHub account and an Azure subscription (student credits are fine).

Check:
```bash
git --version && python3 --version && docker --version && terraform -version && az version
```

## Step 1: Run the project locally first

```bash
cd clineval-ci
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
pytest -q                           # expect: 16 passed
python -m clineval.cli gate         # expect: PASS (exit code 0)
uvicorn clineval.api:app --reload   # open http://127.0.0.1:8000
```
Open `http://127.0.0.1:8000` for the landing page and `http://127.0.0.1:8000/app` for the dashboard. In the dashboard click **Demo: v1 then v2**: v1 becomes the baseline, regressed v2 is compared against it and you get a **Merge blocked** verdict. Then try Compare (confidence-interval bars and Waive buttons), Playground, Cases (linter) and Audit.

**What each file does**

| File | Purpose |
|---|---|
| `suites/triage-core/cases.yaml` | 12 versioned test cases (emergency escalation, medication safety, scope) |
| `clineval/schema.py` | Case schema validation + linter (including a PHI check) |
| `clineval/agent.py` | The agent under test (v1 safe, v2 deliberately regressed) |
| `clineval/judges.py` | Deterministic checks, tool-order checks, forbidden-behaviour detectors |
| `clineval/runner.py` | Runs N trials per case with seeded randomness and records trajectories |
| `clineval/stats.py` | Paired bootstrap confidence intervals + gate policy (PASS/WARN/BLOCK) |
| `clineval/store.py` | SQLite run history |
| `clineval/api.py` | REST API + serves the landing page (`/`) and dashboard (`/app`) |
| `clineval/policy.py`, `gate.yaml`, `waivers.yaml` | Gate policy and approved exceptions |
| `clineval/export.py` | JUnit XML and evidence bundle |
| `clineval/static/index.html`, `app.html` | Landing page and dashboard |
| `.github/workflows/clineval.yml` | PR gate + comment on GitHub |
| `clineval/cli.py` | `lint`, `run`, `baseline`, `gate` (used by Jenkins) |
| `suites/triage-core/baseline.json` | Stored baseline run the gate compares against |

## Step 2: Create the SSH key Jenkins will use

```bash
ssh-keygen -t ed25519 -f ~/.ssh/azure_clineval -N ""
```
Creates `~/.ssh/azure_clineval` (private, for Jenkins) and `.pub` (public, for the VM via Terraform). Never commit the private key.

## Step 3: Push the project to GitHub

1. Create an empty repo on GitHub, for example `clineval-ci` (public is fine).
2. Then:
```bash
git init
git add .
git commit -m "Initial commit: ClinEval-CI with Terraform and Jenkins"
git branch -M main
git remote add origin https://github.com/<your-username>/clineval-ci.git
git push -u origin main
```

## Step 4: Provision Azure infrastructure with Terraform

```bash
az login
az account show                      # confirm the right subscription
cd terraform
terraform init
terraform plan
terraform apply                      # type "yes"
```
Created: resource group, VNet, subnet, public IP, NSG (ports 22 and 80), NIC, Ubuntu 22.04 VM. Cloud-init installs Python, nginx and registers a `clineval` systemd service.

Save the output:
```bash
terraform output public_ip
```
If you get a "SKU not available" error, set another size or region, for example `terraform apply -var location=southindia -var vm_size=Standard_B2s`.

Wait 2 to 3 minutes for cloud-init, then test SSH:
```bash
ssh -i ~/.ssh/azure_clineval azureuser@<PUBLIC_IP> "ls /opt/clineval && systemctl is-enabled clineval"
```

## Step 5: Install and configure Jenkins (Docker)

```bash
cd jenkins
docker compose up -d --build
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```
1. Open http://localhost:8080, paste the password, choose **Install suggested plugins**, create your admin user.
2. The image already contains Python, rsync, ssh and the `git`, `github`, `workflow-aggregator`, `credentials-binding` and `ssh-agent` plugins.

**Add credentials** (Manage Jenkins > Credentials > System > Global > Add Credentials):

| Kind | ID (must match exactly) | Value |
|---|---|---|
| SSH Username with private key | `azure-vm-ssh` | Username `azureuser`; paste the contents of `~/.ssh/azure_clineval` |
| Secret text | `azure-vm-ip` | the public IP from `terraform output public_ip` |

## Step 6: Create the pipeline job

1. **New Item** > name `clineval-ci` > **Pipeline** > OK.
2. Under **Build Triggers** tick **Poll SCM** and enter `H/2 * * * *`.
3. Under **Pipeline** choose **Pipeline script from SCM**, SCM = Git, Repository URL = your GitHub URL, Branch = `*/main`, Script Path = `Jenkinsfile`.
4. Save, then **Build Now** once (this registers the trigger and does the first deployment).

Expected stages, all green: Checkout, Build, Unit Tests, Eval Gate, Deploy to Azure VM, Smoke Test.
Open `http://<PUBLIC_IP>/` to see the live app.

## Step 7: Demonstrate Continuous Deployment (the demo for your professor)

**Demo A: a normal change redeploys automatically**
1. Edit `clineval/static/index.html`, change the subtitle text.
2. `git add . && git commit -m "Update dashboard subtitle" && git push`
3. Within about 2 minutes Jenkins starts a build by itself. Refresh the page at the public IP and the change is live. No manual step.

**Demo B: the eval gate stops a bad change from reaching production**
(JUnit results also appear in the Jenkins build's Test Result tab.)
1. In `clineval/agent.py` set `ACTIVE_VERSION = "v2"` (simulates a bad prompt tweak).
2. `git commit -am "Tweak agent behaviour" && git push`
3. Jenkins fails at the **Eval Gate** stage (red) and **Deploy never runs**. Open the archived `gate-report.md` to show the 7 new critical safety detections and the confidence intervals.
4. Revert to `"v1"`, push again: the pipeline goes green and deploys.

Suggested screenshots for your report: `terraform apply` output, the Azure portal resource list, the Jenkins stage view (green), the failed Eval Gate (red), the dashboard on the public IP.

## Step 8 (optional): GitHub webhook instead of polling

Jenkins is on localhost, so GitHub cannot reach it directly. Use a tunnel:
```bash
ngrok http 8080
```
In GitHub: Repo > Settings > Webhooks > Add webhook, Payload URL `https://<ngrok-id>.ngrok-free.app/github-webhook/`, content type `application/json`, event "Just the push event". In the Jenkins job tick **GitHub hook trigger for GITScm polling**. Builds now start instantly on push.

## Step 9: Clean up (important, avoids Azure charges)

```bash
cd terraform && terraform destroy
docker compose -f ../jenkins/docker-compose.yml down
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Permission denied (publickey)` in Deploy | Re-check the `azure-vm-ssh` credential holds the **private** key and username `azureuser` |
| `rsync: command not found` on the VM | Wait for cloud-init to finish (`cloud-init status --wait` on the VM) |
| Smoke test fails but deploy passed | `ssh` in, run `sudo journalctl -u clineval -n 50` |
| Jenkins cannot find `python3` | Make sure you built the custom image (`docker compose up -d --build`) |
| Terraform "quota" or "SKU" error | Change `location` or `vm_size` |
| Poll SCM never fires | Run **Build Now** once manually; check the Git polling log |
| Port 80 not reachable | NSG rule `allow-http` must exist; check `systemctl status nginx` on the VM |

## Likely viva questions

1. **Why Terraform instead of clicking in the portal?** Infrastructure as code is repeatable, reviewable in Git and destroyable with one command.
2. **What does the eval gate add beyond unit tests?** It tests the agent's behaviour (trajectories and safety rules) and uses confidence intervals, so noise is not mistaken for regression and one critical safety failure blocks the release.
3. **Poll SCM vs webhook?** Polling is simple and works behind NAT but is delayed. Webhooks are instant but need a publicly reachable Jenkins.
4. **How is the deploy made safe?** The gate runs before deploy, and `remote_deploy.sh` health-checks the service after restart.
5. **Security notes?** SSH key auth only, secrets stored in Jenkins credentials, NSG exposes only 22 and 80 (restrict `ssh_source_cidr` for real use), no real patient data.
6. **What would you add for production?** HTTPS, a remote Terraform state backend, a staging slot, and LLM-judge calibration.
