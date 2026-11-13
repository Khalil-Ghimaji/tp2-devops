#!/usr/bin/env bash
# Crée la Quality Gate "tp2-gate" et l'affecte au projet. Usage :
#   SONAR_URL=http://localhost:9000 SONAR_TOKEN=xxx ./sonar/create_quality_gate.sh
set -euo pipefail
A=(-s -u "${SONAR_TOKEN}:")
GATE=tp2-gate
curl "${A[@]}" -X POST "$SONAR_URL/api/qualitygates/create" -d "name=$GATE" >/dev/null || true
add() { curl "${A[@]}" -X POST "$SONAR_URL/api/qualitygates/create_condition" \
  -d "gateName=$GATE" -d "metric=$1" -d "op=$2" -d "error=$3"; echo; }
add new_coverage                    LT 85   # couverture nouveau code < 85 %
add new_duplicated_lines_density    GT 3    # duplication > 3 %
add new_security_hotspots_reviewed  LT 100  # tout hotspot non révisé => échec
curl "${A[@]}" -X POST "$SONAR_URL/api/projects/create" -d "project=payment-api" -d "name=payment-api" >/dev/null || true
curl "${A[@]}" -X POST "$SONAR_URL/api/qualitygates/select" -d "gateName=$GATE" -d "projectKey=payment-api"
