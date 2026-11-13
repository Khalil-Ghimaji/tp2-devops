# TP2 — CD, Quality/Security Gates & SRE (payment-api)

Microservice FastAPI + pipeline CI/CD + Gatekeeper + observabilité OTel + SLO/burn-rate.

## Arborescence
| Chemin | Rôle |
|---|---|
| `app/`, `tests/`, `pytest.ini` | Microservice, tests (couverture ≥ 85 % imposée, rapports Cobertura `coverage.xml` + `coverage.lcov`) |
| `sonar-project.properties`, `sonar/create_quality_gate.sh` | Quality Gate : new_coverage < 85, duplication > 3 %, hotspots non révisés (<100 %) |
| `.github/workflows/ci.yml` | Lint+Test → Sonar+Gate → Build → Trivy (CRITICAL=fail) → Push → bump GitOps |
| `k8s/gatekeeper/` | 2 ConstraintTemplates Rego (tag `latest`, requests/limits) + Constraints + manifeste de test non conforme |
| `charts/payment-api/`, `argocd/application.yaml` | Helm + Application ArgoCD (sync auto) |
| `observability/` | Prometheus (scrape annotations), règles SLI/SLO/burn-rate, Alertmanager, OTel Collector, Loki, Tempo, Alloy, dashboard Grafana RED |
| `k6/load-test.js` | Ramp-up 100 VU, stress 500 VU, spike 1500 VU / 30 s |
| `docs/REPORT.md` | Rapport SRE (à compléter avec vos captures et mesures) |

## Exécution pas à pas
```bash
# 1. Tests locaux
pip install -r requirements-dev.txt && pytest          # échoue si couverture < 85 %
uvicorn app.main:app --port 8000                       # /metrics /checkout /flaky

# 2. Cluster + Gatekeeper
kind create cluster --name tp2
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts
helm install gatekeeper gatekeeper/gatekeeper -n gatekeeper-system --create-namespace
kubectl create ns payment
kubectl apply -f k8s/gatekeeper/templates/ && sleep 5 && kubectl apply -f k8s/gatekeeper/constraints/
kubectl apply -f k8s/gatekeeper/test/non-compliant-deployment.yaml    # => REJET attendu (capture !)

# 3. SonarQube (docker run -d -p 9000:9000 sonarqube:community), puis :
SONAR_URL=http://localhost:9000 SONAR_TOKEN=... ./sonar/create_quality_gate.sh
#    Secrets GitHub : SONAR_TOKEN, SONAR_HOST_URL (SonarCloud ou URL exposée au runner)

# 4. ArgoCD
kubectl create ns argocd && kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
#    éditer OWNER/REPO dans argocd/application.yaml et values.yaml, puis : kubectl apply -f argocd/application.yaml

# 5. Observabilité
SLACK_WEBHOOK_URL=https://hooks.slack.com/... ./observability/install.sh

# 6. Charge (30 % de /flaky pour déclencher le burn-rate critique)
kubectl -n payment port-forward svc/payment-api 8000:8000 &
k6 run -e FLAKY_SHARE=0.30 k6/load-test.js
```

## Points de conception
- **Gatekeeper** cible Pod *et* Deployment/StatefulSet/DaemonSet : le rejet est visible dès l'`apply` du Deployment (sans cela, seul le ReplicaSet échouerait silencieusement). Le tag absent est traité comme `latest`.
- **Métriques RED** exposées par `prometheus_client` (buckets incluant 0.2 s pour l'SLO de latence) ; **traces** via OTel SDK → Collector → Tempo ; **logs JSON** avec `trace_id` → Loki, lien Loki→Tempo via *derived field* et Tempo→Loki via `tracesToLogsV2`.
- **Burn rate** : budget = 1 − 0.995 = 0.005 ; 30 j = 720 h.
  2 % en 1 h ⇒ 0.02×720/1 = **14.4** ; 5 % en 6 h ⇒ 0.05×720/6 = **6**. Multi-fenêtre : 1 h ∧ 5 min (critical), 6 h ∧ 30 min (warning).
- Secrets : Slack via Secret K8s, jetons Sonar via GitHub Secrets ; rien en clair dans git.
