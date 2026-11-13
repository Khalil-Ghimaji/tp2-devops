#!/usr/bin/env bash
set -euo pipefail
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
helm repo update
kubectl create ns observability --dry-run=client -o yaml | kubectl apply -f -
# Secret Slack (jamais commité) :
kubectl -n observability create secret generic slack-webhook --from-literal=url="${SLACK_WEBHOOK_URL:?}" --dry-run=client -o yaml | kubectl apply -f -
helm upgrade -i kps prometheus-community/kube-prometheus-stack -n observability -f observability/prometheus-values.yaml
helm upgrade -i loki grafana/loki -n observability --set deploymentMode=SingleBinary --set loki.auth_enabled=false \
  --set loki.commonConfig.replication_factor=1 --set loki.storage.type=filesystem --set singleBinary.replicas=1 \
  --set loki.schemaConfig.configs[0].from=2024-01-01 --set loki.schemaConfig.configs[0].store=tsdb \
  --set loki.schemaConfig.configs[0].object_store=filesystem --set loki.schemaConfig.configs[0].schema=v13 \
  --set loki.schemaConfig.configs[0].index.prefix=index_ --set loki.schemaConfig.configs[0].index.period=24h
helm upgrade -i tempo grafana/tempo -n observability
helm upgrade -i alloy grafana/alloy -n observability -f observability/alloy-values.yaml   # logs pods -> Loki
helm upgrade -i otel-collector open-telemetry/opentelemetry-collector -n observability -f observability/otel-collector.yaml
kubectl apply -f observability/prometheusrule-slo.yaml
kubectl -n observability create configmap sre-dashboard --from-file=observability/grafana/dashboards/sre-red.json \
  --dry-run=client -o yaml | kubectl label --local -f - grafana_dashboard=1 -o yaml | kubectl -n observability apply -f -
