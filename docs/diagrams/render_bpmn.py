"""Rendu BPMN comparatif (AS-IS vs TO-BE) — fidèle au texte du mémoire.

Processus actuel : 6 étapes manuelles  vs  processus cible : 2 actions
utilisateur + traitement automatique de la plateforme.
Sortie : docs/diagrams/bpmn.png (haute résolution, prêt pour LaTeX).

Usage : python docs/diagrams/render_bpmn.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, FancyArrowPatch, Rectangle

OUT = Path(__file__).resolve().parent / "bpmn.png"

# Palette
MAN_FILL, MAN_EDGE = "#FBE7CC", "#C07A22"      # tâche manuelle / action utilisateur
AUTO_FILL, AUTO_EDGE = "#E3EFFA", "#2E6E9E"    # étape automatique (plateforme)
EXT_FILL, EXT_EDGE = "#ECEFF2", "#6B7785"      # acteur externe (chauffeur)
START_FILL, START_EDGE = "#DDEFD8", "#4F8A4F"
END_FILL, END_EDGE = "#F7DCDC", "#B04A4A"
SEQ = "#3A4A5A"
TXT = "#1B2A38"


def task(ax, cx, cy, w, h, title, actor, fill, edge, badge=None, fs=9.6):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.12",
                 facecolor=fill, edgecolor=edge, linewidth=1.6, zorder=4))
    ax.text(cx, cy + (0.34 if actor else 0), title, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=TXT, zorder=5, linespacing=1.25)
    if actor:
        ax.text(cx, cy - h / 2 + 0.36, actor, ha="center", va="center",
                fontsize=8.4, fontstyle="italic", color="#4A5A68", zorder=5)
    if badge is not None:
        bx, by = cx - w / 2 + 0.05, cy + h / 2 - 0.05
        ax.add_patch(Circle((bx, by), 0.36, facecolor=edge, edgecolor="white",
                            linewidth=1.2, zorder=6))
        ax.text(bx, by, str(badge), ha="center", va="center", color="white",
                fontsize=10, fontweight="bold", zorder=7)


def subprocess(ax, cx, cy, w, h, title, bullets):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.12",
                 facecolor=AUTO_FILL, edgecolor=AUTO_EDGE, linewidth=1.8, zorder=4))
    ax.text(cx, cy + h / 2 - 0.45, title, ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=AUTO_EDGE, zorder=5)
    ax.text(cx, cy + h / 2 - 0.95, "(automatique — sans intervention)", ha="center",
            va="center", fontsize=8.2, fontstyle="italic", color="#4A5A68", zorder=5)
    y = cy + h / 2 - 1.55
    for b in bullets:
        ax.text(cx - w / 2 + 0.55, y, "•  " + b, ha="left", va="center",
                fontsize=9.0, color=TXT, zorder=5)
        y -= 0.5
    # marqueur sous-processus réduit (carré +)
    mx, my = cx, cy - h / 2 + 0.34
    ax.add_patch(Rectangle((mx - 0.22, my - 0.22), 0.44, 0.44, facecolor="white",
                           edgecolor=AUTO_EDGE, linewidth=1.2, zorder=6))
    ax.plot([mx - 0.13, mx + 0.13], [my, my], color=AUTO_EDGE, linewidth=1.2, zorder=7)
    ax.plot([mx, mx], [my - 0.13, my + 0.13], color=AUTO_EDGE, linewidth=1.2, zorder=7)


def event(ax, cx, cy, kind):
    if kind == "start":
        ax.add_patch(Circle((cx, cy), 0.55, facecolor=START_FILL,
                            edgecolor=START_EDGE, linewidth=2.0, zorder=4))
    else:
        ax.add_patch(Circle((cx, cy), 0.55, facecolor=END_FILL,
                            edgecolor=END_EDGE, linewidth=3.4, zorder=4))


def seq(ax, x0, x1, y, y1=None):
    y1 = y if y1 is None else y1
    ax.add_patch(FancyArrowPatch((x0, y), (x1, y1), arrowstyle="-|>",
                 mutation_scale=16, color=SEQ, linewidth=1.7, zorder=3))


def message(ax, p0, p1, label):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=14,
                 color="#6B7785", linewidth=1.5, linestyle=(0, (5, 3)), zorder=3))
    ax.text((p0[0] + p1[0]) / 2 + 0.25, (p0[1] + p1[1]) / 2, label, ha="left",
            va="center", fontsize=8.4, fontstyle="italic", color="#54616E", zorder=5)


fig, ax = plt.subplots(figsize=(16, 9.7))
ax.set_xlim(0, 38)
ax.set_ylim(0, 23)
ax.set_aspect("equal")
ax.axis("off")

# ============================ AS-IS ============================
ay = 18.6
ax.text(0.4, 21.9, "PROCESSUS ACTUEL", fontsize=14, fontweight="bold", color="#8A4B12")
ax.text(0.4, 21.1, "6 étapes manuelles", fontsize=10.5, fontstyle="italic", color="#6B5030")

event(ax, 1.6, ay, "start")
as_tasks = [
    ("Réception\ndes besoins\n(e-mail + EDI)", "Chargé Client"),
    ("Consolidation\nmanuelle (Excel)", "Chargé Client"),
    ("Construction\ndes tournées\n+ vérif. créneaux", "Resp. Transport"),
    ("Impression &\nremise feuilles\nde route", "Resp. Transport"),
    ("Suivi par appels\ntéléphoniques", "Resp. Transport"),
    ("Mise à jour\nmanuelle OTIF", "Resp. Transport"),
]
W, H, PITCH, X0 = 4.9, 3.3, 5.45, 5.2
prev_r = 2.15
for i, (title, actor) in enumerate(as_tasks):
    cx = X0 + i * PITCH
    seq(ax, prev_r, cx - W / 2, ay)
    task(ax, cx, ay, W, H, title, actor, MAN_FILL, MAN_EDGE, badge=i + 1, fs=9.2)
    prev_r = cx + W / 2
seq(ax, prev_r, 35.05, ay)
event(ax, 35.6, ay, "end")

ax.text(18.6, 15.6,
        "Planification 15–21 min     |     latence aléa non détecté ≈ 1 h     |     ressaisie 12–18 %",
        ha="center", fontsize=9.8, color="#8A4B12",
        bbox=dict(boxstyle="round,pad=0.45", fc="#FBF1E2", ec="#C07A22", lw=1.0))

# séparateur
ax.plot([0.4, 37.6], [14.4, 14.4], color="#C9CED4", linewidth=1.0, linestyle=(0, (6, 4)))

# ============================ TO-BE ============================
ty = 9.6
ax.text(0.4, 13.5, "PROCESSUS CIBLE", fontsize=14, fontweight="bold", color="#1F5C86")
ax.text(0.4, 12.7, "2 actions utilisateur + automatisation", fontsize=10.5,
        fontstyle="italic", color="#2E6E9E")

event(ax, 1.6, ty, "start")
task(ax, 6.1, ty, 5.0, 3.0, "Déposer le fichier\nExcel (dossier partagé)",
     "Chargé Client — Action 1", MAN_FILL, MAN_EDGE, badge=1, fs=9.6)
subprocess(ax, 15.0, ty, 9.2, 4.2, "Traitement plateforme", [
    "Détection Watchdog (< 1 s)",
    "Validation Pydantic",
    "Optimisation OR-Tools (VRPTW)",
    "Calcul des KPI",
    "Mise à jour du tableau de bord",
])
task(ax, 24.3, ty, 5.0, 3.0, "Consulter & valider\nle plan généré",
     "Resp. Transport — Action 2", MAN_FILL, MAN_EDGE, badge=2, fs=9.6)
task(ax, 30.7, ty, 4.6, 3.0, "Envoi SMS\nrécapitulatif (J+1)",
     "automatique", AUTO_FILL, AUTO_EDGE, fs=9.6)
event(ax, 34.4, ty, "end")

seq(ax, 2.15, 3.6, ty)
seq(ax, 8.6, 10.4, ty)
seq(ax, 19.6, 21.8, ty)
seq(ax, 26.8, 28.4, ty)
seq(ax, 33.0, 33.85, ty)

# boucle d'ajustement glisser-déposer sur l'action 2
ax.add_patch(FancyArrowPatch((25.5, ty + 1.6), (23.1, ty + 1.6),
             arrowstyle="-|>", mutation_scale=13, color="#C07A22", linewidth=1.4,
             connectionstyle="arc3,rad=-0.85", zorder=5))
ax.text(24.3, ty + 2.7, "ajustement glisser-déposer\n(optionnel)", ha="center",
        va="center", fontsize=8.0, fontstyle="italic", color="#8A4B12", zorder=5)

# acteur externe : chauffeur (flux de message SMS)
task(ax, 30.7, 5.0, 4.6, 1.8, "Chauffeur", "", EXT_FILL, EXT_EDGE)
message(ax, (30.7, ty - 1.5), (30.7, 5.95), "SMS tournée J+1")

ax.text(14.5, 3.0,
        "Planification < 3 min     |     détection des anomalies < 30 s     |     0 erreur de ressaisie",
        ha="center", fontsize=9.8, color="#1F5C86",
        bbox=dict(boxstyle="round,pad=0.45", fc="#E8F1FA", ec="#2E6E9E", lw=1.0))

# ============================ Légende ============================
def swatch(x, fill, edge, label):
    ax.add_patch(FancyBboxPatch((x, 1.0), 0.6, 0.5,
                 boxstyle="round,pad=0.02,rounding_size=0.08",
                 facecolor=fill, edgecolor=edge, linewidth=1.3))
    ax.text(x + 0.85, 1.25, label, ha="left", va="center", fontsize=8.8, color=TXT)

swatch(0.6, MAN_FILL, MAN_EDGE, "Action utilisateur (manuel)")
swatch(11.0, AUTO_FILL, AUTO_EDGE, "Étape automatique (plateforme)")
ax.add_patch(Circle((22.4, 1.25), 0.28, facecolor=START_FILL, edgecolor=START_EDGE, lw=2))
ax.add_patch(Circle((23.1, 1.25), 0.28, facecolor=END_FILL, edgecolor=END_EDGE, lw=3))
ax.text(23.6, 1.25, "Événement début / fin", ha="left", va="center", fontsize=8.8, color=TXT)
ax.add_patch(FancyArrowPatch((31.4, 1.25), (32.6, 1.25), arrowstyle="-|>",
             mutation_scale=12, color="#6B7785", linewidth=1.4, linestyle=(0, (5, 3))))
ax.text(32.8, 1.25, "Flux de message (SMS)", ha="left", va="center", fontsize=8.8, color=TXT)

fig.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.18, facecolor="white")
print(f"OK -> {OUT}")
