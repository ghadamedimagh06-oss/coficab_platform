"""Rendu du modèle en étoile (composante BI) — fidèle au texte du mémoire.

Fait LIVRAISONS + 4 dimensions : Client, Transporteur, Destination, Temps.
Sortie : docs/diagrams/star_schema.png (haute résolution, prêt pour LaTeX).

Usage : python docs/diagrams/render_star_schema.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch

OUT = Path(__file__).resolve().parent / "star_schema.png"

# Palette professionnelle, contrastée (lisible en N&B)
FACT_HEAD = "#1F3A5F"   # fait — bleu nuit
FACT_BODY = "#EAF1FB"
DIM_HEAD = "#2E6E9E"    # dimensions — bleu acier
DIM_BODY = "#F3F8FC"
EDGE = "#23394d"
LINE = "#7A8896"
TXT_DARK = "#1A2A3A"

HEADER_H = 0.62
ROW_H = 0.46
PAD_L = 0.22


def draw_entity(ax, cx, cy, title, rows, width, head_color, body_color, divider_after=None):
    """rows: liste de (texte, tag) avec tag ∈ {'pk','fk','measure',''}."""
    n = len(rows)
    total_h = HEADER_H + n * ROW_H
    left = cx - width / 2
    bottom = cy - total_h / 2
    top = cy + total_h / 2

    # Corps
    ax.add_patch(Rectangle((left, bottom), width, total_h, facecolor=body_color,
                           edgecolor=EDGE, linewidth=1.4, zorder=3))
    # En-tête
    ax.add_patch(Rectangle((left, top - HEADER_H), width, HEADER_H, facecolor=head_color,
                           edgecolor=EDGE, linewidth=1.4, zorder=4))
    ax.text(cx, top - HEADER_H / 2, title, ha="center", va="center",
            color="white", fontsize=12.5, fontweight="bold", zorder=5)

    # Lignes d'attributs
    y = top - HEADER_H - ROW_H / 2
    for i, (name, tag) in enumerate(rows):
        weight = "bold" if tag == "pk" else "normal"
        style = "italic" if tag == "fk" else "normal"
        label = name
        if tag == "pk":
            label = f"{name}   (PK)"
        elif tag == "fk":
            label = f"#  {name}"
        ax.text(left + PAD_L, y, label, ha="left", va="center", fontsize=10.2,
                fontweight=weight, fontstyle=style, color=TXT_DARK, zorder=5)
        y -= ROW_H
        # séparateur FK / mesures dans le fait
        if divider_after is not None and i == divider_after - 1:
            ax.plot([left + 0.08, left + width - 0.08], [y + ROW_H / 2, y + ROW_H / 2],
                    color="#9FB3C8", linewidth=1.0, zorder=5)
    return (cx, cy)


def connect(ax, p_dim, p_fact):
    """Trait dimension → fait avec cardinalité 1 ─< N."""
    ax.add_patch(FancyArrowPatch(p_dim, p_fact, arrowstyle="-", color=LINE,
                                 linewidth=1.6, zorder=1, shrinkA=2, shrinkB=2))
    # libellés de cardinalité
    fx = p_dim[0] + (p_fact[0] - p_dim[0]) * 0.18
    fy = p_dim[1] + (p_fact[1] - p_dim[1]) * 0.18
    nx = p_dim[0] + (p_fact[0] - p_dim[0]) * 0.82
    ny = p_dim[1] + (p_fact[1] - p_dim[1]) * 0.82
    ax.text(fx, fy, "1", fontsize=10, color="#33414f", ha="center", va="center",
            zorder=2, bbox=dict(boxstyle="circle,pad=0.12", fc="white", ec="none"))
    ax.text(nx, ny, "N", fontsize=10, color="#33414f", ha="center", va="center",
            zorder=2, bbox=dict(boxstyle="circle,pad=0.12", fc="white", ec="none"))


fig, ax = plt.subplots(figsize=(13, 11))
ax.set_xlim(0, 17)
ax.set_ylim(-1, 15)
ax.set_aspect("equal")
ax.axis("off")

FX, FY = 8.4, 7.0  # centre du fait

# --- Fait central ---
fait_rows = [
    ("id_client", "fk"), ("id_transporteur", "fk"),
    ("id_destination", "fk"), ("id_temps", "fk"),
    ("date_planifiee", "measure"), ("heure_planifiee", "measure"),
    ("date_effective", "measure"), ("heure_effective", "measure"),
    ("cout", "measure"), ("distance", "measure"),
    ("volume_livre", "measure"), ("otif", "measure"),
]
p_fact = draw_entity(ax, FX, FY, "FAIT_LIVRAISONS", fait_rows, 4.9,
                     FACT_HEAD, FACT_BODY, divider_after=4)

# --- Dimensions (disposition en étoile : haut, droite, bas, gauche) ---
p_temps = draw_entity(ax, FX, 13.2, "DIM_TEMPS", [
    ("id_temps", "pk"), ("date", ""), ("jour", ""),
    ("semaine_iso", ""), ("mois", ""), ("annee", ""),
], 3.7, DIM_HEAD, DIM_BODY)

p_transp = draw_entity(ax, 14.0, 7.0, "DIM_TRANSPORTEUR", [
    ("id_transporteur", "pk"), ("nom", ""), ("type", ""),
    ("capacite_nominale", ""),
], 4.0, DIM_HEAD, DIM_BODY)

p_dest = draw_entity(ax, 8.4, 0.9, "DIM_DESTINATION", [
    ("id_destination", "pk"), ("ville", ""), ("distance_depot_km", ""),
    ("latitude", ""), ("longitude", ""),
], 4.0, DIM_HEAD, DIM_BODY)

p_client = draw_entity(ax, 2.7, 7.0, "DIM_CLIENT", [
    ("id_client", "pk"), ("nom", ""), ("secteur", ""),
    ("fenetre_ouverture", ""), ("fenetre_fermeture", ""),
], 3.9, DIM_HEAD, DIM_BODY)

# --- Liaisons (sous les boîtes) ---
for p_dim in (p_temps, p_transp, p_dest, p_client):
    connect(ax, p_dim, p_fact)

fig.tight_layout(pad=0.4)
fig.savefig(OUT, dpi=300, bbox_inches="tight", pad_inches=0.15, facecolor="white")
print(f"OK -> {OUT}")
