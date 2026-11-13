# Step-by-step guide — TP2 (≈ 6 h)

Follow the phases in order. Each phase ends with a **✅ Checkpoint**: don't move on until it passes.
Items marked 📸 are screenshots you need for the report (`docs/REPORT.md`).

## Phase 0 — Prerequisites (≈ 20 min)

Install: `docker`, `kind`, `kubectl`, `helm`, `k6`, `git`, Python 3.12.
You also need a **GitHub repo** (public is simplest) and a **SonarCloud** account (free) *or* a SonarQube you can reach from GitHub's runners.

> ⚠️ A SonarQube running in Docker on your laptop is **not reachable** from GitHub-hosted runners. Use SonarCloud, or a self-hosted runner, or expose it with a tunnel (ngrok / cloudflared).

1. Unzip `tp2-devops.zip`, `cd tp2-devops`, then `git init` and push it to your GitHub repo (`main` branch).
2. Search-and-replace `OWNER/REPO` with your real `owner/repo` (lowercase) in:
   - `charts/payment-api/values.yaml` (`image.repository`, e.g. `ghcr.io/jdoe/tp2/payment-api`)
   - `argocd/application.yaml` (`repoURL`)
3. In GitHub → Settings → Actions → General, set Workflow permissions to **Read and write**.

## Phase 1 — App and unit tests (≈ 30 min)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```
Fix anything that fails (I couldn't run it in my sandbox, so treat this as the first real test).

```bash
uvicorn app.main:app --port 8000
curl localhost:8000/products ; curl localhost:8000/metrics | head
curl -X POST localhost:8000/checkout -H 'Content-Type: application/json' -d '{"product_id":1,"quantity":2}'
for i in $(seq 10); do curl -s -o /dev/null -w "%{http_code} " localhost:8000/flaky; done
```
✅ **Checkpoint:** `pytest` passes with coverage ≥ 85 %, `/metrics` shows `http_requests_total`, `/flaky` returns a mix of 200/503.

## Phase 2 — Cluster and Gatekeeper (≈ 40 min)

```bash
kind create cluster --name tp2
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts && helm repo update
helm install gatekeeper gatekeeper/gatekeeper -n gatekeeper-system --create-namespace
kubectl -n gatekeeper-system rollout status deploy/gatekeeper-controller-manager
kubectl create ns payment
kubectl apply -f k8s/gatekeeper/templates/
sleep 10                      # wait for the CRDs generated from the templates
kubectl apply -f k8s/gatekeeper/constraints/
```
Now try the bad manifest:
```bash
kubectl apply -f k8s/gatekeeper/test/non-compliant-deployment.yaml
```
✅ **Checkpoint:** the apply is **denied** with messages about `:latest` and missing `resources.*`.
📸 **Screenshot #2:** that denial message.

If the templates error out, run `kubectl describe constrainttemplate <name>`: a Rego syntax error shows up in its status.

## Phase 3 — SonarQube / SonarCloud gate (≈ 40 min)

**Option A — SonarCloud (easiest):**
1. Create an organization and import your repo. Generate a token.
2. Add `sonar.organization=<your-org>` to `sonar-project.properties`.
3. In SonarCloud, create a quality gate with the same three conditions as in `sonar/create_quality_gate.sh` (new coverage < 85 %, new duplication > 3 %, new hotspots reviewed < 100 %) and assign it to the project.
4. GitHub → Settings → Secrets → Actions: add `SONAR_TOKEN` and `SONAR_HOST_URL` (`https://sonarcloud.io`).

**Option B — self-hosted SonarQube:**
```bash
docker run -d --name sonarqube -p 9000:9000 sonarqube:community
```
Log in at `localhost:9000` (admin/admin), create a token, then:
```bash
SONAR_URL=http://localhost:9000 SONAR_TOKEN=<token> ./sonar/create_quality_gate.sh
```
Add the two GitHub secrets (the URL must be reachable from the runner, see Phase 0).

✅ **Checkpoint:** nothing to check yet; the first CI run in Phase 4 will prove it.

## Phase 4 — CI pipeline (≈ 45 min)

1. Push to `main`. Watch GitHub → Actions: `test-quality` → `build-scan-push` → `gitops-bump`.
2. After the first push of the image, GitHub → Packages → `payment-api` → Package settings → set visibility to **Public** (otherwise Kubernetes can't pull it without an imagePullSecret).
3. **Make the gate fail on purpose** (for the report):
   ```bash
   git checkout -b feat/untested
   cat >> app/main.py <<'PY'

   def untested_discount(price: float, pct: float) -> float:
       if pct > 50:
           return price * 0.5
       return price * (1 - pct / 100)
   PY
   git commit -am "feat: untested code" && git push -u origin feat/untested
   ```
   Open a PR into `main`.

✅ **Checkpoint:** `main` pipeline is green end to end; the PR is **red** at the Sonar step (new-code coverage < 85 %). Optionally require the check in branch protection.
📸 **Screenshot #1:** the failing PR / Sonar gate. Then close the PR.

Troubleshooting: Trivy fails on a CRITICAL CVE → bump the base image tag in the `Dockerfile` or `requirements.txt` versions; `ignore-unfixed` is already on. `gitops-bump` fails on push → the workflow permissions in Phase 0 step 3.

## Phase 5 — ArgoCD deployment (≈ 30 min)

```bash
git pull   # get the bot's commit that updated the image tag
kubectl create ns argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server
kubectl apply -f argocd/application.yaml
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
kubectl -n argocd port-forward svc/argocd-server 8080:443     # https://localhost:8080 (admin)
```
If the repo is private, add it in ArgoCD (Settings → Repositories) with a token.

✅ **Checkpoint:** the app is **Synced / Healthy**; `kubectl -n payment get pods` shows 2 Running pods (the chart's resources and pinned tag satisfy Gatekeeper).
To show GitOps rejection too: temporarily set `image.tag: latest` in `values.yaml`, push, and watch ArgoCD report the Deployment sync/pods blocked by Gatekeeper (revert afterwards). 📸 optional extra for the report.

## Phase 6 — Observability stack (≈ 45 min)

```bash
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX   # any placeholder URL works for the lab
./observability/install.sh
kubectl -n observability get pods -w
```
Then:
```bash
kubectl -n observability port-forward svc/kps-grafana 3000:80          # user admin, pwd: see below
kubectl -n observability get secret kps-grafana -o jsonpath='{.data.admin-password}' | base64 -d; echo
kubectl -n observability port-forward svc/kps-kube-prometheus-stack-prometheus 9090
```
Generate some traffic, then verify:
- Prometheus → Status → Targets: job `annotated-pods` has your 2 pods **UP**.
- Prometheus → Rules: `payment-api-sli` and `payment-api-burn-rate` are loaded.
- Grafana → Dashboards → **payment-api — SRE (RED)** exists.
- Grafana → Explore → Loki: `{app="payment-api"} | json` shows JSON logs; click a `trace_id` → opens the trace in Tempo.

✅ **Checkpoint:** metrics, logs and traces all visible, and log → trace navigation works.

Troubleshooting: no traces → check `kubectl -n observability logs deploy/otel-collector-opentelemetry-collector` and that the pod env `OTEL_EXPORTER_OTLP_ENDPOINT` points to `otel-collector.observability:4318` (the real service name depends on the chart; adjust `values.yaml` if different). No logs → check the Alloy pod logs. Datasource errors → service names (`loki`, `tempo`) must match `kubectl -n observability get svc`.

## Phase 7 — Load test and incident (≈ 60 min)

> A `kubectl port-forward` can itself become the bottleneck at 500–1500 VU and distort results. If latencies look absurd, run k6 inside the cluster (k6 operator or a Job) with `BASE_URL=http://payment-api.payment:8000`.

1. Open the Grafana dashboard (time range last 30 min, refresh 10 s).
2. Run the test (≈ 12 min total):
   ```bash
   kubectl -n payment port-forward svc/payment-api 8000:8000 &
   k6 run -e FLAKY_SHARE=0.30 k6/load-test.js
   ```
3. While it runs, watch the RED panels, the burn-rate panel, and Prometheus → Alerts.
4. Expected: `ErrorBudgetBurnCritical` goes **Pending → Firing** after the 2-minute `for`; the warning fires later (15 min `for` plus the 6 h window).
5. Optional comparison run with `-e FLAKY_SHARE=0.05` to see a slow burn without alerts.

✅ **Checkpoint:** alert firing in Prometheus and received by Alertmanager (`kubectl -n observability port-forward svc/kps-kube-prometheus-stack-alertmanager 9093`).
📸 **Screenshot #3:** dashboard during/after the test. 📸 **Screenshot #4:** alert firing.
Write down k6's summary numbers (RPS, p95, `http_req_failed`) for each scenario, and the budget remaining afterwards.

## Phase 8 — Write the report (≈ 30 min)

A ready-made report lives in `report/` (PDF + Markdown). To finish it:
1. Save your 4 screenshots as `report/screenshots/shot-1.png` … `shot-4.png` (1 = Sonar fail, 2 = Gatekeeper denial, 3 = Grafana dashboard, 4 = alert firing).
2. In `report/build_report.py`, replace every `TODO` (`[À COMPLÉTER]`) cell with your measured values, and set your name: `REPORT_AUTHOR="Your Name" python3 report/build_report.py` (run it from inside `report/`; needs `pip install reportlab matplotlib pillow`).
3. The script swaps each placeholder for your real screenshot automatically and rewrites `REPORT.pdf` and `REPORT.md`.

Older checklist (what the report must contain):

Open `docs/REPORT.md` and fill in:
- screenshots #1–#4 (and the trace/log correlation capture),
- the k6 results table,
- the incident timeline (start → threshold crossed → alert firing → notification),
- remaining error budget and your decision/corrective actions.
Compare your results with the "Attendu" hypothesis in the report; if they differ, explain why (that is what the SRE analysis is graded on).

Commit and push everything. Submit the repo link plus the report.

## Final checklist
- [ ] `pytest` ≥ 85 % coverage, reports `coverage.xml` / `coverage.lcov`
- [ ] Sonar gate blocks a non-compliant PR 📸
- [ ] Trivy step active (CRITICAL = fail)
- [ ] Gatekeeper rejects the bad manifest 📸
- [ ] ArgoCD app Synced/Healthy
- [ ] Prometheus scrapes annotated pods; Loki + Tempo linked by `trace_id`
- [ ] Dashboard: Rate, Errors (/s and %), p50/p90/p95/p99, Error Budget gauge
- [ ] Burn-rate alerts (14.4 and 6) fire during the load test 📸
- [ ] No secrets committed (Slack URL, tokens)
- [ ] `docs/REPORT.md` completed
