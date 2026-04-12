"""Non-parametric comparison: Friedman -> Holm-corrected Wilcoxon -> Cliff's delta.

**Spine seam.** When ``metaheuristics-bench`` lands, delete this module and import
``mhbench.stats`` instead -- the function names and signatures here are chosen to
match, so the swap is one line in each caller. Until then this is a local copy, and
the tests in ``tests/test_stats.py`` are what guarantee it behaves.

**The level distinction that this literature routinely gets wrong.** Friedman and the
post-hoc Wilcoxon operate on the *problems x algorithms matrix of per-problem
aggregates*. Cliff's delta does not: it is computed *within one problem*, over the
raw per-run values. Computing an effect size on the aggregates answers "does A beat B
on more problems", which the Friedman ranks already told you.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import scikit_posthocs as sp
from scipy.stats import friedmanchisquare

#: Romano et al. cut-points for |delta|.
_MAGNITUDE = ((0.147, "negligible"), (0.33, "small"), (0.474, "medium"))


def friedman_ranks(matrix: pd.DataFrame) -> tuple[float, float, pd.Series]:
    """Friedman test across algorithms, problems as blocks.

    Args:
        matrix: rows = problems, columns = algorithms, values = per-problem aggregate
            (median target error). Lower is better.

    Returns:
        (statistic, p-value, average ranks ascending -- rank 1 is best).
    """
    if matrix.shape[1] < 3:
        raise ValueError("Friedman needs >= 3 algorithms; use Wilcoxon for two")
    stat, p = friedmanchisquare(*[matrix[c].to_numpy() for c in matrix.columns])
    ranks = matrix.rank(axis=1, ascending=True).mean(axis=0)
    return float(stat), float(p), ranks.sort_values()


def posthoc_holm(matrix: pd.DataFrame) -> pd.DataFrame:
    """Pairwise Wilcoxon signed-rank with Holm step-down correction.

    Signed-rank, not rank-sum: problems are paired across algorithms.
    """
    out = sp.posthoc_wilcoxon(
        [matrix[c].to_numpy() for c in matrix.columns], p_adjust="holm"
    )
    out.index = pd.Index(matrix.columns, name="algorithm")
    out.columns = pd.Index(matrix.columns, name="algorithm")
    return out


def cliffs_delta(a, b) -> float:
    """Cliff's delta: stochastic dominance of ``a`` over ``b``.

    Run on RAW RUNS within one problem, never on across-problem aggregates.
    Sign convention: returns +1 when every value in ``a`` exceeds every value in
    ``b``. For minimised error, a *negative* delta means ``a`` is better.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if a.size == 0 or b.size == 0:
        raise ValueError("cliffs_delta needs non-empty samples")
    gt = int((a[:, None] > b[None, :]).sum())
    lt = int((a[:, None] < b[None, :]).sum())
    return (gt - lt) / (a.size * b.size)


def cliffs_magnitude(delta: float) -> str:
    """Romano et al. magnitude label for a Cliff's delta."""
    d = abs(delta)
    for bound, label in _MAGNITUDE:
        if d < bound:
            return label
    return "large"


def control_comparison(matrix: pd.DataFrame, control: str) -> pd.DataFrame:
    """Each algorithm against one control: Wilcoxon signed-rank, Holm over k-1 tests.

    ``posthoc_holm`` corrects across *all* pairs. When the question is "does each
    algorithm beat this one control", all-pairs correction is the wrong family: it
    charges you for comparisons you never intended to make. With 13 algorithms that is
    78 pairs instead of 12, and the resulting loss of power is severe.

    Demšar (2006) is explicit that comparisons with a control should be corrected over
    the k-1 control comparisons only. Both are reported in this study — the all-pairs
    matrix for the full ranking, this for the ablation question.
    """
    from scipy.stats import wilcoxon
    from statsmodels.stats.multitest import multipletests

    others = [c for c in matrix.columns if c != control]
    raw = []
    for c in others:
        a, b = matrix[c].to_numpy(), matrix[control].to_numpy()
        if np.allclose(a, b):
            raw.append(1.0)
            continue
        raw.append(float(wilcoxon(a, b).pvalue))
    reject, adj, _, _ = multipletests(raw, alpha=0.05, method="holm")
    return pd.DataFrame(
        {"p_raw": raw, "p_holm": adj, "significant": reject},
        index=pd.Index(others, name="algorithm"),
    ).sort_values("p_holm")
