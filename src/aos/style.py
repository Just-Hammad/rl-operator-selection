"""Figure styling.

One palette, one set of rules, applied everywhere, so the figures read as one study
rather than as five separately-made plots.

Colours are the Okabe-Ito colourblind-safe set. The role assignment is deliberate:
**the uniform-random ablation is drawn in heavy black** because it is the null every
other line is being measured against, and it should be the first thing the eye finds.
Fixed operators are thin and grey -- context, not contenders.
"""

from __future__ import annotations

import matplotlib as mpl

from .registry import ABLATION

# Okabe-Ito
OKABE_ITO = {
    "orange": "#E69F00",
    "sky": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "purple": "#CC79A7",
    "black": "#000000",
}

#: Per-algorithm line styling. Anything unlisted falls back to FIXED_STYLE.
ALGORITHM_STYLE: dict[str, dict] = {
    ABLATION: dict(color=OKABE_ITO["black"], lw=2.6, zorder=10),
    "ucb": dict(color=OKABE_ITO["blue"], lw=1.7, zorder=6),
    "thompson": dict(color=OKABE_ITO["green"], lw=1.7, zorder=6),
    "pm": dict(color=OKABE_ITO["orange"], lw=1.7, zorder=6),
    "ap": dict(color=OKABE_ITO["purple"], lw=1.7, zorder=6),
    "success-rate": dict(color=OKABE_ITO["vermillion"], lw=1.7, zorder=6),
    "jade": dict(color=OKABE_ITO["sky"], lw=1.9, ls="--", zorder=7),
    "oracle:best-fixed": dict(color="#555555", lw=1.6, ls="-.", zorder=8),
}
FIXED_STYLE = dict(color="#BBBBBB", lw=0.9, ls=":", zorder=2, alpha=0.9)

#: Sequential fill colours for the five operators in the usage stackplot.
OPERATOR_FILLS = (
    OKABE_ITO["blue"],
    OKABE_ITO["sky"],
    OKABE_ITO["green"],
    OKABE_ITO["orange"],
    OKABE_ITO["vermillion"],
)


def style_for(algorithm: str) -> dict:
    return dict(ALGORITHM_STYLE.get(algorithm, FIXED_STYLE))


def use() -> None:
    """Apply the study-wide matplotlib defaults. Idempotent."""
    mpl.rcParams.update(
        {
            "figure.dpi": 130,
            "savefig.dpi": 200,
            "savefig.bbox": "tight",
            "font.family": "sans-serif",
            "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.titleweight": "bold",
            "axes.labelsize": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.8,
            "axes.grid": True,
            "grid.color": "#DDDDDD",
            "grid.linewidth": 0.6,
            "grid.alpha": 0.9,
            "xtick.color": "#444444",
            "ytick.color": "#444444",
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.frameon": False,
            "legend.fontsize": 7.5,
            "lines.solid_capstyle": "round",
            "figure.constrained_layout.use": False,
        }
    )


def annotate_source(fig, text: str) -> None:
    """Small provenance footer -- what produced the figure, so it survives being
    pasted into a slide without losing its context."""
    fig.text(
        0.995, 0.005, text, ha="right", va="bottom", fontsize=6, color="#888888"
    )
