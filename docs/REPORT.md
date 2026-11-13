# Rapport SRE — payment-api

> Les sections « Résultats » sont à remplir avec VOS captures et mesures : elles dépendent de votre exécution.

## 1. Contrats de service
| SLI | SLO | Budget (30 j) |
|---|---|---|
| Disponibilité : req. avec status < 500 / total | 99,5 % | 0,5 % = 3 h 36 min d'indisponibilité équivalente |
| Latence : req. < 200 ms / total | 95 % (p95 ≤ 200 ms) | 5 % de req. lentes |

Seuils d'alerte : critical = 14,4 × 0,005 = **7,2 %** d'erreurs ; warning = 6 × 0,005 = **3 %**.

## 2. Quality Gate SonarQube
- Gate `tp2-gate` : couverture nouveau code ≥ 85 %, duplication ≤ 3 %, hotspots 100 % révisés.
- **Capture 1** : PR non conforme (ex. fonction sans test ou hotspot non révisé) → job `test-quality` en échec : *[insérer]*

## 3. OPA Gatekeeper
- Commande : `kubectl apply -f k8s/gatekeeper/test/non-compliant-deployment.yaml`
- **Capture 2** : message de rejet de l'API server (`admission webhook "validation.gatekeeper.sh" denied the request`, tag `latest` + resources manquantes) : *[insérer]*

## 4. Test de charge k6
Commande : `k6 run -e FLAKY_SHARE=0.30 k6/load-test.js`
| Scénario | Résultat observé (à remplir) |
|---|---|
| Ramp-up 0→100 VU | RPS / p95 / % erreurs : |
| Stress 500 VU | |
| Spike 1500 VU / 30 s | |

Attendu (hypothèse, à confirmer) : avec 30 % de `/flaky` à 30 % d'erreur, ≈ 9 % d'erreurs globales > 7,2 % ⇒ burn rate ≈ 18 > 14,4 ⇒ alerte critical après 2 min. Avec `FLAKY_SHARE=0.05` ⇒ ≈ 1,5 % (burn 3) : aucune alerte, mais le budget se consomme. Aux paliers 500 et 1500 VU, une saturation CPU des 2 réplicas peut faire dépasser 200 ms en p95 même sans erreurs (SLO latence).

## 5. Analyse d'incident simulé
- **Capture 3** : dashboard Grafana (Rate / Errors / Duration / jauge Error Budget / burn rate) pendant le test : *[insérer]*
- **Capture 4** : alerte `ErrorBudgetBurnCritical` en *Firing* (Prometheus → Alerts) + notification Alertmanager : *[insérer]*
- Chronologie : T0 début du stress → T+? burn 1 h franchit 14,4 → T+? alerte pending→firing → réception.
- Corrélation : depuis un log ERROR dans Loki, clic sur `trace_id` → trace Tempo (*[capture]*).
- Budget restant après test : ___ % ; décision (gel des déploiements si < 25 %, par ex.).
- Actions correctives proposées : réduire le taux d'erreur de `/flaky` (retry/circuit breaker), HPA sur CPU, augmenter les limites, rate limiting au pic.
