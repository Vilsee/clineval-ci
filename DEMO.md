# Demo runbook (about 10 minutes)

Open these tabs before you start: the Vercel URL `/demo`, Jenkins (`http://localhost:8080/job/clineval-ci/`),
the GitHub repo, and a terminal in the project folder. Press **T** on `/demo` to start the timer.

| Time | Rubric item | What to show | What to say |
|---|---|---|---|
| 0:00 | Intro | Landing page `/`, then flip the v1 / v2 switch in the hero | "A merge gate for clinical AI agents. A bad change flips the verdict from allowed to blocked." |
| 0:45 | Terraform | `/demo#terraform`: KPIs, `main.tf`, the two modules, `terraform validate` screenshot | "Eight Azure resources in two modules, typed variables, outputs, optional remote state. Validated locally; applying needs a subscription." |
| 2:30 | CI/CD (Jenkins) | Real Jenkins: Stage View with Checkout, Build, Unit Tests, Terraform Validate, Eval Gate, Deploy, Smoke Test | "Poll SCM watches GitHub every two minutes. Every stage is automated." |
| 3:30 | CI/CD live demo A | Edit the landing headline, `git commit`, `git push`; watch Jenkins start by itself; refresh the app | "No manual build. The change is live after the pipeline passes." |
| 5:00 | CI/CD live demo B | Set `ACTIVE_VERSION = "v2"`, push; build goes red at Eval Gate; open `gate-report.md` | "Seven critical safety findings. The deploy stage never ran, so production is untouched." Revert and push. |
| 7:00 | Deployment | Vercel URL health card, local container `:8001`, Azure card (honest status) | "Same app, three targets. The Azure stage is built and skipped until a subscription exists." |
| 8:00 | Certification | `/demo#cert` | Course, completion, certificate. |
| 8:30 | Documentation | `/demo#docs` architecture diagram, README, `/docs` API reference | "Everything is in one repository." |
| 9:30 | Questions | | See the answers below. |

## If something fails

| Problem | Fallback |
|---|---|
| Jenkins is slow or down | On `/demo`, press **S** (or Push commit) to run the same gate live, and show the real screenshots |
| App on `:8000` is down | Open Jenkins, Build with Parameters, Build. Or use `http://localhost:8001` or the Vercel URL |
| No internet | Pages still work; fonts fall back and the 3D scenes stay blank. Press the **3D** button to switch them off |
| Laptop is slow | Switch 3D off on every page before you start |
| Vercel shows empty runs | Open `/app` and click **Demo: v1 then v2** (serverless data is temporary by design) |

## Likely questions

1. **Why Terraform?** Repeatable, reviewable in Git, destroyed with one command.
2. **What does the gate add beyond unit tests?** It tests behaviour (safety rules and tool use) with confidence intervals, and one critical failure blocks the merge.
3. **Why is Azure not deployed?** Subscription access is pending. The Terraform validates, the cloud-init and the pipeline's Azure stage are ready.
4. **Poll SCM or webhook?** Polling works behind NAT; a webhook is instant but needs Jenkins to be reachable (ngrok).
5. **Is it clinically valid?** No. Synthetic data and a rule-based demo agent; passing the gate is not clinical evidence.
