"""Construit REPORT.pdf + REPORT.md. Les captures réelles (screenshots/shot-N.png) remplacent automatiquement les emplacements."""
import os, re
import matplotlib
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, CondPageBreak, SimpleDocTemplate, Spacer, Table, TableStyle)
from PIL import Image as PILImage

fd = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
pdfmetrics.registerFont(TTFont("DV", os.path.join(fd, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("DV-B", os.path.join(fd, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("DV-M", os.path.join(fd, "DejaVuSansMono.ttf")))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV", boldItalic="DV-B")

AUTHOR = os.getenv("REPORT_AUTHOR", "[Nom Prénom]")
TODO = "[À COMPLÉTER]"

SHOTS = {
 1: "Quality Gate SonarQube en échec sur une PR non conforme (couverture du nouveau code < 85 %)",
 2: "Rejet par OPA Gatekeeper du Deployment non conforme (tag latest, resources absentes)",
 3: "Dashboard Grafana RED + jauge Error Budget pendant le test de charge k6",
 4: "Alerte ErrorBudgetBurnCritical à l'état Firing dans Prometheus / Alertmanager",
}
HOW = {
 1: "GitHub → Pull request → onglet Checks → job test-quality en rouge (ou page SonarQube du projet : Quality Gate « Failed »).",
 2: "Terminal : kubectl apply -f k8s/gatekeeper/test/non-compliant-deployment.yaml (message « denied the request »).",
 3: "Grafana → payment-api — SRE (RED), plage « Last 30 minutes », pendant ou juste après le test.",
 4: "Prometheus → Alerts (état FIRING) et/ou Alertmanager (port 9093) montrant l'alerte.",
}

B = []
h1 = lambda t: B.append(("h1", t)); h2 = lambda t: B.append(("h2", t)); p = lambda t: B.append(("p", t))
bl = lambda l: B.append(("bl", l)); tb = lambda r, w=None: B.append(("tb", r, w))
fig = lambda f, c: B.append(("fig", f, c)); shot = lambda n: B.append(("shot", n))

# ================= CONTENU =================
h1("1. Contexte et objectifs")
p("Ce rapport documente la mise en œuvre d'une chaîne de livraison continue sécurisée pour le microservice **payment-api** (FastAPI), "
  "avec barrières de qualité (SonarQube), politiques d'admission Kubernetes (OPA Gatekeeper), déploiement GitOps (ArgoCD), "
  "observabilité OpenTelemetry (Prometheus, Loki, Tempo, Grafana) et pilotage SRE par SLO et Error Budget.")
fig("architecture.png", "Figure 1 — Architecture globale (schéma de conception)")

h1("2. Microservice et tests")
p("Le service expose `/products`, `/checkout` (traitement lent simulé, 50–150 ms), `/flaky` (erreurs 503 intermittentes, taux configurable "
  "via `FLAKY_ERROR_RATE`), `/health` et `/metrics` (format Prometheus). Les tests couvrent les cas nominaux et aux limites "
  "(quantités 0, 1, 100, 101, produit ou devise invalides, succès/échec de `/flaky`, métriques, format des logs JSON).")
tb([["Élément", "Valeur"],
    ["Seuil de couverture imposé", "≥ 85 % (pytest `--cov-fail-under=85`)"],
    ["Couverture mesurée", TODO],
    ["Rapports générés", "`coverage.xml` (Cobertura) et `coverage.lcov`"]], [6, 10])

h1("3. Contrats de qualité et de sécurité")
h2("3.1 Quality Gate SonarQube")
tb([["Condition (nouveau code)", "Seuil bloquant"],
    ["Couverture", "< 85 %"], ["Duplication de lignes", "> 3 %"], ["Security Hotspots révisés", "< 100 % (tout hotspot non révisé bloque)"]], [8, 8])
p("L'étape d'analyse du pipeline utilise `sonar.qualitygate.wait=true` : si la Quality Gate échoue, le job échoue et la PR ne peut pas être fusionnée.")
shot(1)
h2("3.2 Politiques OPA Gatekeeper")
tb([["Contrainte", "Template Rego", "Effet"],
    ["Interdire le tag latest", "K8sDisallowLatest", "Rejette `:latest` et les images sans tag (latest implicite)"],
    ["requests/limits obligatoires", "K8sRequiredResources", "Exige resources.requests et limits (cpu, memory) par conteneur"]], [4.5, 4.5, 7])
p("Les contraintes ciblent Pod, Deployment, StatefulSet et DaemonSet dans le namespace `payment` : le rejet survient dès l'`apply` du Deployment.")
shot(2)

h1("4. Pipeline CI/CD et GitOps")
fig("pipeline.png", "Figure 2 — Étapes bloquantes du pipeline (GitHub Actions) et déploiement ArgoCD")
bl(["Lint (ruff) et tests avec couverture minimale.", "Analyse SonarQube et attente de la Quality Gate.",
    "Build Docker, scan Trivy (sévérité CRITICAL ⇒ échec), push vers GHCR uniquement sur `main`.",
    "Mise à jour du tag d'image dans `values.yaml` : ArgoCD synchronise automatiquement (sync auto, prune, selfHeal).",
    "Secrets : `SONAR_TOKEN`, `SONAR_HOST_URL` (GitHub Secrets) ; webhook Slack (Secret Kubernetes) — aucun secret dans Git."])
tb([["Constat", "Résultat"], ["Pipeline `main` de bout en bout", TODO], ["Application ArgoCD", "Synced / Healthy : " + TODO]], [8, 8])

h1("5. Observabilité")
bl(["**Métriques** : `http_requests_total` et `http_request_duration_seconds` (buckets incluant 0,2 s), scrapées via les annotations `prometheus.io/*`.",
    "**Traces** : SDK OpenTelemetry → OTel Collector (OTLP) → Tempo ; span métier `process_payment`.",
    "**Logs** : JSON structurés avec `trace_id` et `span_id`, collectés par Alloy vers Loki.",
    "**Corrélation** : *derived field* Loki → Tempo (clic sur `trace_id`) et `tracesToLogsV2` Tempo → Loki."])
tb([["Vérification", "Résultat"], ["Cibles Prometheus UP (job annotated-pods)", TODO],
    ["Navigation log → trace fonctionnelle", TODO]], [8, 8])

h1("6. Ingénierie SRE")
h2("6.1 SLI / SLO")
tb([["Indicateur (SLI)", "Objectif (SLO)", "Budget d'erreur / 30 jours"],
    ["Disponibilité : requêtes avec status < 500", "99,5 %", "0,5 % ≈ 3 h 36 min"],
    ["Latence : requêtes < 200 ms", "95 % (p95 ≤ 200 ms)", "5 % de requêtes lentes"]], [6.5, 4.5, 5])
h2("6.2 Alerting sur le burn rate")
p("Burn rate = taux d'erreurs observé ÷ budget (0,005). Sur 30 jours (720 h) : **2 % du budget en 1 h** ⇒ 0,02 × 720 / 1 = **14,4** ; "
  "**5 % du budget en 6 h** ⇒ 0,05 × 720 / 6 = **6**. Chaque alerte combine une fenêtre longue et une fenêtre courte (multi-window) pour "
  "limiter les faux positifs et accélérer la résolution.")
tb([["Alerte", "Condition PromQL", "Seuil d'erreurs", "Sévérité / canal"],
    ["ErrorBudgetBurnCritical", "erreurs 1 h > 14,4×0,005 et 5 min > 14,4×0,005 (for 2m)", "7,2 %", "critical → Page"],
    ["ErrorBudgetBurnWarning", "erreurs 6 h > 6×0,005 et 30 min > 6×0,005 (for 15m)", "3 %", "warning → Slack"]], [4.8, 6.0, 2.3, 2.9])
fig("burn_rate.png", "Figure 3 — Durée de vie du budget et seuils d'erreurs associés (calcul exact, fenêtre 30 jours)")
h2("6.3 Test de charge k6")
fig("k6_profile.png", "Figure 4 — Profil de charge défini dans k6/load-test.js (ramp-up, stress, spike)")
p("Commande : `k6 run -e FLAKY_SHARE=0.30 k6/load-test.js`. Seuils k6 : `http_req_failed < 0,5 %` et `p(95) < 200 ms`. "
  "Hypothèse de travail : avec 30 % du trafic sur `/flaky` (30 % d'erreurs), le taux d'erreurs global est d'environ 9 %, soit un burn rate d'environ 18 (> 14,4) : l'alerte critical doit se déclencher.")
tb([["Scénario", "RPS", "p95 (ms)", "% erreurs", "Seuils k6"],
    ["Ramp-up 0→100 VU", TODO, TODO, TODO, TODO], ["Stress 500 VU", TODO, TODO, TODO, TODO], ["Spike 1500 VU / 30 s", TODO, TODO, TODO, TODO]], [4.6, 2.4, 3, 3, 3])

h1("7. Analyse d'incident simulé")
p("Le test de charge simule un incident de fiabilité : la dégradation du taux d'erreurs fait brûler le budget plus vite que prévu.")
shot(3)
shot(4)
tb([["Chronologie", "Heure / observation"],
    ["Début du palier de stress", TODO], ["Burn rate 1 h > 14,4", TODO], ["Alerte critical Pending → Firing", TODO],
    ["Notification reçue (Alertmanager / Slack)", TODO], ["Error Budget restant après le test", TODO + " %"]], [8, 8])
h2("Analyse et actions correctives")
bl(["Cause dominante observée (erreurs `/flaky` ou saturation CPU au pic) : " + TODO,
    "Écart avec l'hypothèse de la section 6.3 et explication : " + TODO,
    "Actions proposées : circuit breaker / retries sur `/flaky`, HPA sur CPU, ajustement des limites, rate limiting lors des pics, "
    "gel des déploiements quand le budget restant passe sous un seuil défini (ex. 25 %)."])
h1("8. Conclusion")
p(TODO + " (synthèse : objectifs atteints, difficultés rencontrées, améliorations possibles).")
# ===========================================

def shot_path(n):
    real = f"screenshots/shot-{n}.png"
    return (real, True) if os.path.exists(real) else (f"figures/placeholder-{n}.png", False)

def inline_pdf(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)
    return re.sub(r"`(.+?)`", r'<font name="DV-M" size="8">\1</font>', t)

ss = getSampleStyleSheet()
base = ParagraphStyle("b", parent=ss["Normal"], fontName="DV", fontSize=9.5, leading=14, spaceAfter=6)
H1 = ParagraphStyle("h1", parent=base, fontName="DV-B", fontSize=15, leading=19, spaceBefore=12, spaceAfter=7, keepWithNext=1, textColor=colors.HexColor("#1e3a8a"))
H2 = ParagraphStyle("h2", parent=base, fontName="DV-B", fontSize=11.5, leading=15, spaceBefore=8, spaceAfter=4, keepWithNext=1, textColor=colors.HexColor("#334155"))
CAP = ParagraphStyle("cap", parent=base, fontSize=8.5, leading=11, textColor=colors.HexColor("#475569"), alignment=1)
CELL = ParagraphStyle("cell", parent=base, fontSize=8.5, leading=11, spaceAfter=0)
CELLH = ParagraphStyle("cellh", parent=CELL, fontName="DV-B", textColor=colors.white)

def img(path, maxw=16.5 * cm):
    w, h = PILImage.open(path).size
    return Image(path, width=maxw, height=maxw * h / w)

story, md = [], []
story += [Spacer(1, 3 * cm), Paragraph("Rapport SRE", ParagraphStyle("t", parent=H1, fontSize=28, leading=34, alignment=1)),
          Paragraph("Continuous Delivery, Quality &amp; Security Gates<br/>et ingénierie SRE avec observabilité cloud-native",
                    ParagraphStyle("st", parent=base, fontSize=13, leading=18, alignment=1, textColor=colors.HexColor("#475569"))),
          Spacer(1, 1 * cm), Paragraph("Projet : <b>payment-api</b> — TP2 DevOps avancé", ParagraphStyle("c", parent=base, alignment=1, fontSize=11)),
          Paragraph("Auteur : " + AUTHOR, ParagraphStyle("c2", parent=base, alignment=1, fontSize=11)), PageBreak()]
md += ["# Rapport SRE — payment-api", "", "*Continuous Delivery, Quality & Security Gates et ingénierie SRE avec observabilité cloud-native*", "", f"Auteur : {AUTHOR}", ""]
sn = 0
for b in B:
    k = b[0]
    if k == "h1": story += [CondPageBreak(8 * cm), Paragraph(b[1], H1)]; md += ["", "## " + b[1], ""]
    elif k == "h2": story.append(Paragraph(b[1], H2)); md += ["", "### " + b[1], ""]
    elif k == "p": story.append(Paragraph(inline_pdf(b[1]), base)); md += [b[1], ""]
    elif k == "bl":
        for it in b[1]: story.append(Paragraph("• " + inline_pdf(it), ParagraphStyle("li", parent=base, leftIndent=12, firstLineIndent=-8, spaceAfter=3)))
        md += ["- " + i for i in b[1]] + [""]
    elif k == "tb":
        rows, w = b[1], b[2]
        data = [[Paragraph(inline_pdf(c), CELLH if r == 0 else CELL) for c in row] for r, row in enumerate(rows)]
        t = Table(data, colWidths=[x * cm for x in w] if w else None, repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                               ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story += [KeepTogether([t, Spacer(1, 8)])]
        md += ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * len(rows[0])] + ["| " + " | ".join(r) + " |" for r in rows[1:]] + [""]
    elif k == "fig":
        story.append(KeepTogether([img("figures/" + b[1]), Paragraph(b[2], CAP), Spacer(1, 8)]))
        md += [f"![{b[2]}](figures/{b[1]})", f"*{b[2]}*", ""]
    elif k == "shot":
        n = b[1]; path, real = shot_path(n)
        cap = f"Capture {n} — {SHOTS[n]}" + ("" if real else "  (emplacement : " + HOW[n] + ")")
        story.append(KeepTogether([img(path, 15.5 * cm), Paragraph(cap, CAP), Spacer(1, 8)]))
        md += [f"![Capture {n}]({path})", f"*Capture {n} — {SHOTS[n]}*", ""]

def footer(c, d):
    c.saveState(); c.setFont("DV", 8); c.setFillColor(colors.HexColor("#94a3b8"))
    c.drawString(2 * cm, 1.2 * cm, "Rapport SRE — payment-api"); c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {d.page}"); c.restoreState()

SimpleDocTemplate("REPORT.pdf", pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                  title="Rapport SRE — payment-api").build(story, onFirstPage=footer, onLaterPages=footer)
open("REPORT.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
missing = [n for n in SHOTS if not shot_path(n)[1]]
print("PDF ok ; captures manquantes :", missing or "aucune")
