"""Génère les figures du rapport (schémas + courbes calculées à partir de la config du TP)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = "figures/"
C = {"blue": "#2563eb", "green": "#16a34a", "orange": "#ea580c", "purple": "#7c3aed", "gray": "#475569", "red": "#dc2626"}


def box(ax, x, y, w, h, text, color, fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=color, ec="none", alpha=0.92))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="white", fontsize=fs, weight="bold")


def arrow(ax, p1, p2, color="#334155", style="-|>"):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=12, color=color, lw=1.4))


# ---- 1. Pipeline CI/CD ----
fig, ax = plt.subplots(figsize=(11, 3.2)); ax.axis("off"); ax.set_xlim(0, 11); ax.set_ylim(0, 3)
steps = [("Lint +\nTests\n(cov ≥ 85 %)", C["blue"]), ("SonarQube\nQuality Gate", C["blue"]),
         ("Docker\nBuild", C["gray"]), ("Trivy\nCRITICAL = fail", C["red"]),
         ("Push\nGHCR", C["gray"]), ("Bump tag\nGit (GitOps)", C["purple"]), ("ArgoCD\nsync", C["green"])]
for i, (t, c) in enumerate(steps):
    x = 0.1 + i * 1.55
    box(ax, x, 1.2, 1.3, 1.1, t, c, 8)
    if i < len(steps) - 1:
        arrow(ax, (x + 1.32, 1.75), (x + 1.55, 1.75))
box(ax, 8.75, 0.15, 2.2, 0.7, "Gatekeeper : rejet\nlatest / sans resources", C["orange"], 8)
arrow(ax, (10.2, 1.2), (10.2, 0.87), C["orange"])
ax.text(5, 2.75, "Pipeline CI/CD : chaque étape est bloquante", ha="center", fontsize=12, weight="bold")
fig.savefig(OUT + "pipeline.png", dpi=170, bbox_inches="tight"); plt.close(fig)

# ---- 2. Architecture ----
fig, ax = plt.subplots(figsize=(11, 5.6)); ax.axis("off"); ax.set_xlim(0, 11); ax.set_ylim(0, 5.6)
box(ax, 0.2, 2.3, 1.7, 1.0, "k6\n(charge)", C["gray"])
box(ax, 2.6, 2.1, 2.4, 1.4, "payment-api (x2)\nFastAPI + OTel\n/metrics /checkout /flaky", C["blue"], 8)
box(ax, 6.0, 4.3, 2.0, 0.8, "Prometheus", C["orange"])
box(ax, 6.0, 3.0, 2.0, 0.8, "OTel Collector", C["purple"])
box(ax, 6.0, 1.7, 2.0, 0.8, "Alloy (logs)", C["gray"])
box(ax, 8.7, 3.0, 2.0, 0.8, "Tempo\n(traces)", C["purple"])
box(ax, 8.7, 1.7, 2.0, 0.8, "Loki\n(logs JSON)", C["green"])
box(ax, 8.7, 4.3, 2.0, 0.8, "Alertmanager", C["red"])
box(ax, 5.9, 0.2, 4.8, 0.9, "Grafana (lit Prometheus, Loki, Tempo)\nRED, Error Budget, burn rate ; Loki ⇄ Tempo via trace_id", C["blue"])
box(ax, 2.6, 4.3, 2.4, 0.8, "Gatekeeper (admission)", C["red"])
box(ax, 2.6, 0.3, 2.4, 0.8, "ArgoCD  ⟵  Git (Helm)", C["green"])
arrow(ax, (1.9, 2.8), (2.6, 2.8)); arrow(ax, (5.0, 3.2), (6.0, 4.6)); arrow(ax, (5.0, 2.8), (6.0, 3.4))
arrow(ax, (5.0, 2.4), (6.0, 2.1)); arrow(ax, (8.0, 3.4), (8.7, 3.4)); arrow(ax, (8.0, 2.1), (8.7, 2.1))
arrow(ax, (8.0, 4.7), (8.7, 4.7)); arrow(ax, (3.8, 4.3), (3.8, 3.5)); arrow(ax, (3.8, 1.1), (3.8, 2.1))
ax.text(5.5, 5.4, "Architecture globale", ha="center", fontsize=12, weight="bold")
ax.text(5.28, 4.0, "scrape", fontsize=7, color=C["gray"], rotation=55, ha="center")
fig.savefig(OUT + "architecture.png", dpi=170, bbox_inches="tight"); plt.close(fig)

# ---- 3. Profil de charge k6 (calculé depuis k6/load-test.js) ----
def prof(start, stages):
    t, v, pts = start, 0, [(start, 0)]
    for d, tgt in stages:
        t += d; pts.append((t, tgt))
    return pts
ramp = prof(0, [(120, 100), (60, 100), (30, 0)])
stress = prof(240, [(60, 500), (300, 500), (30, 0)])
spike = prof(660, [(5, 1500), (30, 1500), (5, 0)])
fig, ax = plt.subplots(figsize=(10, 3.8))
for pts, lab, col in [(ramp, "Ramp-up 0→100 VU", C["blue"]), (stress, "Stress 500 VU", C["orange"]), (spike, "Spike 1500 VU / 30 s", C["red"])]:
    ax.plot([p[0] / 60 for p in pts], [p[1] for p in pts], color=col, lw=2.2, label=lab)
    ax.fill_between([p[0] / 60 for p in pts], [p[1] for p in pts], alpha=0.12, color=col)
ax.set_xlabel("Temps (min)"); ax.set_ylabel("VU"); ax.set_title("Profil de charge k6 (3 scénarios enchaînés)", weight="bold")
ax.grid(alpha=0.3); ax.legend(loc="upper left")
fig.savefig(OUT + "k6_profile.png", dpi=170, bbox_inches="tight"); plt.close(fig)

# ---- 4. Burn rate / error budget (calcul exact) ----
budget = 0.005; window_h = 720
fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.9))
br = [x / 2 for x in range(2, 81)]
a.plot(br, [window_h / x for x in br], color=C["blue"], lw=2)
for x, col, lab in [(14.4, C["red"], "critical : 14,4 → 50 h"), (6, C["orange"], "warning : 6 → 120 h"), (1, C["green"], "burn 1 → 720 h")]:
    a.scatter([x], [window_h / x], color=col, zorder=3, s=45); a.annotate(lab, (x, window_h / x), textcoords="offset points", xytext=(8, 8), fontsize=8, color=col)
a.set_yscale("log"); a.set_ylim(10, 2000); a.set_xlim(0, 42); a.set_xlabel("Burn rate"); a.set_ylabel("Temps avant épuisement du budget (h)")
a.set_title("Durée de vie du budget (fenêtre 30 j)", weight="bold", fontsize=10); a.grid(alpha=0.3, which="both")
b.plot(br, [100 * x * budget for x in br], color=C["purple"], lw=2)
for x, col in [(14.4, C["red"]), (6, C["orange"]), (1, C["green"])]:
    b.scatter([x], [100 * x * budget], color=col, zorder=3, s=45)
    b.annotate(f"{100*x*budget:.1f} %", (x, 100 * x * budget), textcoords="offset points", xytext=(8, 6), fontsize=8, color=col)
b.set_ylim(-1.5, 21); b.set_xlabel("Burn rate"); b.set_ylabel("Taux d'erreurs correspondant (%)")
b.set_title("Seuils d'alerte = burn rate × 0,5 %", weight="bold", fontsize=10); b.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT + "burn_rate.png", dpi=170, bbox_inches="tight"); plt.close(fig)

# ---- Placeholders captures ----
shots = {1: "Échec de la Quality Gate SonarQube sur une PR non conforme",
         2: "Rejet du manifeste non conforme par OPA Gatekeeper",
         3: "Dashboard Grafana RED + Error Budget pendant le test de charge",
         4: "Alerte ErrorBudgetBurnCritical en Firing (Prometheus / Alertmanager)"}
for n, t in shots.items():
    fig, ax = plt.subplots(figsize=(10, 4.6)); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0.01, 0.02), 0.98, 0.96, boxstyle="round,pad=0.0,rounding_size=0.02",
                                fc="#f1f5f9", ec="#94a3b8", lw=2, ls="--"))
    ax.text(0.5, 0.58, f"CAPTURE {n} À INSÉRER", ha="center", fontsize=22, weight="bold", color="#64748b")
    ax.text(0.5, 0.40, t, ha="center", fontsize=12, color="#475569")
    ax.text(0.5, 0.26, f"Placez votre PNG dans report/screenshots/shot-{n}.png puis relancez build_report.py", ha="center", fontsize=9, color="#94a3b8")
    fig.savefig(OUT + f"placeholder-{n}.png", dpi=130, bbox_inches="tight"); plt.close(fig)
print("figures ok")
