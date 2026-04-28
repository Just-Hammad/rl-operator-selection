"""Tables and figures from a completed experiment.

Final-target error, an ECDF over targets and budgets, and convergence curves -- plus
the two figures specific to this project, operator usage over time and the effect
size against the uniform-random ablation.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .operators import OPERATOR_NAMES
from .problems import PRECISION_FLOOR
from .registry import ABLATION, ADAPTIVE, FIXED
from .stats import (
    cliffs_delta,
    cliffs_magnitude,
    control_comparison,
    friedman_ranks,
    posthoc_holm,
)
from .style import OPERATOR_FILLS, annotate_source, style_for
from .style import use as use_style

#: Log-spaced target errors for the ECDF, the COCO convention.
TARGETS = np.logspace(2, -8, 51)

#: One representative function per BBOB group.
SHOWCASE_FIDS = (1, 6, 10, 15, 20, 24)
BBOB_GROUPS = {
    "separable": range(1, 6),
    "low-conditioning": range(6, 10),
    "high-conditioning": range(10, 15),
    "multimodal-global": range(15, 20),
    "multimodal-weak": range(20, 25),
}

_ORACLE = "oracle:best-fixed"


# --------------------------------------------------------------------------- load


def load(results_dir: str | Path) -> tuple[pd.DataFrame, dict]:
    d = Path(results_dir)
    runs = pd.read_csv(d / "runs.csv", index_col="row_id")
    extra: dict = {}
    for f in sorted(d.glob("traces_d*.npz")):
        dim = int(f.stem.split("_d")[1])
        extra[f"traces_{dim}"] = dict(np.load(f))
    if (d / "selection.npz").exists():
        extra["selection"] = dict(np.load(d / "selection.npz"))
    return runs, extra


# ------------------------------------------------------------------------ tables


def per_problem_matrix(runs: pd.DataFrame, dim: int) -> pd.DataFrame:
    """Problems x algorithms of per-problem median error -- the Friedman input."""
    sub = runs[runs["dim"] == dim]
    m = sub.pivot_table(
        index="fid", columns="algorithm", values="best_error", aggfunc="median"
    )
    return m.sort_index()


def add_hindsight_oracle(runs: pd.DataFrame, dim: int) -> pd.DataFrame:
    """Best fixed operator per problem, chosen after seeing the results.

    Not an algorithm -- an upper bound on what *any* online operator-selection method
    over this pool could achieve, since it is handed the answer. Reported so that the
    adaptive policies are measured against the ceiling and not only against the floor.
    """
    sub = runs[(runs["dim"] == dim) & (runs["algorithm"].isin(FIXED))]
    med = sub.groupby(["fid", "algorithm"])["best_error"].median()
    best = med.groupby("fid").idxmin().map(lambda t: t[1])
    picked = []
    for fid, alg in best.items():
        rows = sub[(sub["fid"] == fid) & (sub["algorithm"] == alg)].copy()
        rows["algorithm"] = _ORACLE
        rows["oracle_choice"] = alg
        picked.append(rows)
    return pd.concat(picked, ignore_index=True)


def ablation_effect_sizes(runs: pd.DataFrame, dim: int, baseline: str = ABLATION) -> pd.DataFrame:
    """Cliff's delta of each algorithm against ``baseline``, per problem, on raw runs.

    Sign convention: error is minimised, so **negative delta means the algorithm beat
    the baseline**.
    """
    sub = runs[runs["dim"] == dim]
    base = sub[sub["algorithm"] == baseline]
    out = []
    for alg, g in sub.groupby("algorithm"):
        if alg == baseline:
            continue
        for fid, gg in g.groupby("fid"):
            b = base[base["fid"] == fid]["best_error"].to_numpy()
            a = gg["best_error"].to_numpy()
            if len(a) == 0 or len(b) == 0:
                continue
            d = cliffs_delta(a, b)
            out.append(
                {
                    "algorithm": alg,
                    "fid": int(fid),
                    "delta": d,
                    "magnitude": cliffs_magnitude(d),
                    "better": d < 0,
                }
            )
    return pd.DataFrame(out)


def ablation_summary(eff: pd.DataFrame) -> pd.DataFrame:
    """Per algorithm: on how many problems it beat the ablation non-negligibly."""
    rows = []
    for alg, g in eff.groupby("algorithm"):
        nn = g[g["magnitude"] != "negligible"]
        rows.append(
            {
                "algorithm": alg,
                "n_problems": len(g),
                "wins_nonneg": int((nn["delta"] < 0).sum()),
                "losses_nonneg": int((nn["delta"] > 0).sum()),
                "negligible": int((g["magnitude"] == "negligible").sum()),
                "median_delta": float(g["delta"].median()),
            }
        )
    return pd.DataFrame(rows).sort_values("median_delta").reset_index(drop=True)


def credit_misalignment(runs: pd.DataFrame, extra: dict, dim: int) -> pd.DataFrame:
    """Per policy: how often its trials succeeded, and how hard it committed.

    The two numbers that separate "the policy failed to learn" from "the policy learned
    the wrong thing". A policy with a *higher* success rate than the ablation has
    demonstrably learned something -- if it also ranks worse, what it learned was a
    proxy that diverges from the objective.
    """
    sel = extra.get("selection")
    if sel is None:
        return pd.DataFrame()
    rid, S, SU = sel["row_id"], sel["selection"], sel["success"]
    rows = []
    for alg in [ABLATION, *ADAPTIVE]:
        want = runs.index[(runs["algorithm"] == alg) & (runs["dim"] == dim)]
        m = np.isin(rid, np.asarray(want))
        if not m.any():
            continue
        s = S[m].sum(axis=(0, 1)).astype(float)
        su = SU[m].sum(axis=(0, 1)).astype(float)
        share = s / s.sum()
        # Normalised entropy: 0 = uniform over operators, 1 = all mass on one.
        ent = -(share * np.log(share + 1e-12)).sum() / np.log(len(share))
        row = {
            "algorithm": alg,
            "trial_success_rate": su.sum() / s.sum(),
            "top_operator": OPERATOR_NAMES[int(np.argmax(share))],
            "top_operator_share": float(share.max()),
            "commitment": float(1 - ent),
        }
        row.update({f"share:{n}": float(v) for n, v in zip(OPERATOR_NAMES, share)})
        rows.append(row)
    return pd.DataFrame(rows).set_index("algorithm")


def commitment_vs_rank(mis: pd.DataFrame, ranks: pd.Series) -> tuple[float, float]:
    """Spearman correlation between how hard a policy commits and how badly it ranks."""
    from scipy.stats import spearmanr

    algs = [a for a in ADAPTIVE if a in mis.index and a in ranks.index]
    if len(algs) < 3:
        return float("nan"), float("nan")
    rho, pv = spearmanr(
        [mis.loc[a, "top_operator_share"] for a in algs], [ranks[a] for a in algs]
    )
    return float(rho), float(pv)


def fig_misalignment(mis: pd.DataFrame, ranks: pd.Series, dim: int, out: Path) -> None:
    """Success rate and commitment against final rank -- the misalignment picture."""
    if mis.empty:
        return
    use_style()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.1))

    algs = [a for a in [ABLATION, *ADAPTIVE] if a in mis.index]
    xs = [mis.loc[a, "trial_success_rate"] for a in algs]
    ys = [ranks.get(a, np.nan) for a in algs]
    for a, x, y in zip(algs, xs, ys):
        st = style_for(a)
        ax1.scatter(x, y, s=95, color=st["color"], zorder=5,
                    edgecolor="white", linewidth=1.2)
        ax1.annotate(a, (x, y), textcoords="offset points", xytext=(7, 4), fontsize=7.5)
    ax1.set_xlabel("fraction of trials that improved the parent")
    ax1.set_ylabel("Friedman rank  (lower = better)")
    ax1.invert_yaxis()
    ax1.set_title("Higher success rate, worse rank")

    xs2 = [mis.loc[a, "top_operator_share"] for a in algs]
    for a, x, y in zip(algs, xs2, ys):
        st = style_for(a)
        ax2.scatter(x, y, s=95, color=st["color"], zorder=5,
                    edgecolor="white", linewidth=1.2)
        ax2.annotate(a, (x, y), textcoords="offset points", xytext=(7, 4), fontsize=7.5)
    rho, pv = commitment_vs_rank(mis, ranks)
    ax2.set_xlabel("share of selections on its most-used operator")
    ax2.invert_yaxis()
    ax2.set_title(
        f"Harder commitment, worse rank   (Spearman ρ={rho:.2f}, p={pv:.3f})"
        if np.isfinite(rho) else "Commitment vs rank"
    )
    fig.suptitle(
        f"Credit misalignment at D={dim}: the policies win the proxy and lose the objective",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    annotate_source(fig, "credit = immediate fitness improvement")
    fig.savefig(out / f"fig_misalignment_d{dim}.png")
    plt.close(fig)


def baseline_sensitivity(runs: pd.DataFrame, dim: int) -> pd.DataFrame:
    """What conclusion would each possible choice of baseline have produced?

    AOS results are conventionally reported against *one* fixed operator, and the
    choice is rarely justified. This re-runs the identical comparison against every
    available baseline and counts how many policies would have been declared winners.

    If the answer depends on which baseline was picked, the baseline was doing the work,
    not the algorithm.
    """
    sub = runs[runs["dim"] == dim]
    matrix = per_problem_matrix(sub, dim)
    rows = []
    for base in [*FIXED, ABLATION]:
        if base not in matrix.columns:
            continue
        cc = control_comparison(matrix, base)
        med = ablation_effect_sizes(runs, dim, baseline=base).groupby("algorithm")[
            "delta"
        ].median()
        better = [a for a in ADAPTIVE if med.get(a, 0.0) < 0]
        sig = [a for a in better if float(cc.loc[a, "p_holm"]) < 0.05]
        rows.append(
            {
                "baseline": base,
                "n_better": len(better),
                "n_significantly_better": len(sig),
                "n_policies": len(ADAPTIVE),
            }
        )
    return pd.DataFrame(rows).set_index("baseline")


# ------------------------------------------------------------------------- ECDF


def ecdf_curve(
    traces: dict, runs: pd.DataFrame, algorithm: str, dim: int
) -> tuple[np.ndarray, np.ndarray]:
    """Fraction of (function, run, target) triples solved within a budget."""
    row_ids = traces["row_id"]
    evals = traces["evals"]
    err = traces["error"]
    want = runs.index[(runs["algorithm"] == algorithm) & (runs["dim"] == dim)]
    mask = np.isin(row_ids, np.asarray(want))
    if not mask.any():
        return evals, np.zeros(len(evals))
    e = err[mask]  # (n_runs, n_points)
    # solved[i, t, p] -> did run i reach target t by grid point p
    reached = e[:, None, :] <= TARGETS[None, :, None]
    hit = np.maximum.accumulate(reached, axis=2)
    return evals, hit.mean(axis=(0, 1))


# ----------------------------------------------------------------------- figures


def fig_ecdf(runs, extra, dim, out: Path) -> None:
    """Empirical runtime distribution: the anytime view, not a single cut-off."""
    traces = extra.get(f"traces_{dim}")
    if traces is None:
        return
    use_style()
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    present = set(runs["algorithm"])
    ymax = 0.0
    for alg in [*FIXED, "jade", *ADAPTIVE, ABLATION]:
        if alg not in present:
            continue
        x, y = ecdf_curve(traces, runs, alg, dim)
        ymax = max(ymax, float(y.max()))
        ax.plot(x, y, label=alg, **style_for(alg))
    ax.set_xscale("log")
    ax.set_xlabel("function evaluations")
    ax.set_ylabel("fraction of (function, run, target) solved")
    # Scale to the data. Under a restricted budget the hardest of the 51 targets are
    # unreachable, so a hard [0, 1] axis compresses the entire result into a corner.
    ax.set_ylim(0, min(1.0, ymax * 1.18))
    ax.set_title(f"Empirical runtime distribution — 24 BBOB functions, D={dim}")
    handles, labels = ax.get_legend_handles_labels()
    keep = [(h, l) for h, l in zip(handles, labels) if not l.startswith("fixed:")]
    keep.append((plt.Line2D([], [], **style_for("fixed:rand/1")), "fixed operators (5)"))
    ax.legend(*zip(*keep), loc="upper left", ncol=2)
    annotate_source(fig, f"{len(TARGETS)} log-spaced targets · 25 runs/function")
    fig.savefig(out / f"fig_ecdf_d{dim}.png")
    plt.close(fig)


def fig_convergence(runs, extra, dim, out: Path) -> None:
    """Median with IQR band on one representative function per BBOB group."""
    traces = extra.get(f"traces_{dim}")
    if traces is None:
        return
    use_style()
    row_ids, evals, err = traces["row_id"], traces["evals"], traces["error"]
    algs = [a for a in [*ADAPTIVE, "jade", ABLATION] if a in set(runs["algorithm"])]
    group_of = {f: g for g, rng_ in BBOB_GROUPS.items() for f in rng_}
    fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.2), sharex=True)
    for ax, fid in zip(axes.ravel(), SHOWCASE_FIDS):
        for alg in algs:
            want = runs.index[
                (runs["algorithm"] == alg) & (runs["dim"] == dim) & (runs["fid"] == fid)
            ]
            mask = np.isin(row_ids, np.asarray(want))
            if not mask.any():
                continue
            e = np.maximum(err[mask], PRECISION_FLOOR)
            st = style_for(alg)
            ax.plot(evals, np.median(e, axis=0), label=alg, **st)
            lo, hi = np.percentile(e, [25, 75], axis=0)
            ax.fill_between(evals, lo, hi, alpha=0.10, color=st["color"], lw=0)
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_title(f"f{fid} · {group_of.get(fid, '')}", fontsize=9)
    for ax in axes[-1]:
        ax.set_xlabel("function evaluations")
    for ax in axes[:, 0]:
        ax.set_ylabel("target error")
    axes[0, 0].legend(loc="lower left")
    fig.suptitle(
        f"Convergence — median with interquartile band, D={dim}",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    annotate_source(fig, "25 runs per function")
    fig.savefig(out / f"fig_convergence_d{dim}.png")
    plt.close(fig)


def fig_operator_usage(runs, extra, dim, out: Path) -> None:
    """Which operator each policy picks, across the run.

    The diagnostic that error numbers cannot give you: a policy whose bands stay flat
    at 1/K is not adapting, however good its final error looks.
    """
    sel = extra.get("selection")
    if sel is None:
        return
    use_style()
    algs = [a for a in [ABLATION, *ADAPTIVE] if a in set(runs["algorithm"])]
    fig, axes = plt.subplots(
        1, len(algs), figsize=(2.5 * len(algs) + 1.6, 3.1), sharey=True
    )
    axes = np.atleast_1d(axes)
    row_ids, S = sel["row_id"], sel["selection"]
    for ax, alg in zip(axes, algs):
        want = runs.index[(runs["algorithm"] == alg) & (runs["dim"] == dim)]
        mask = np.isin(row_ids, np.asarray(want))
        if not mask.any():
            continue
        agg = S[mask].sum(axis=0).astype(float)
        frac = agg / np.maximum(agg.sum(axis=1, keepdims=True), 1)
        x = np.linspace(0, 100, frac.shape[0])
        ax.stackplot(x, frac.T, labels=OPERATOR_NAMES, colors=OPERATOR_FILLS, lw=0)
        ax.axhline(1 / len(OPERATOR_NAMES), color="w", lw=1.0, ls=(0, (3, 3)))
        ax.set_title(alg + ("  (the null)" if alg == ABLATION else ""), fontsize=9)
        ax.set_xlabel("% of budget")
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 1)
        ax.grid(False)
    axes[0].set_ylabel("share of selections")
    axes[-1].legend(loc="center left", bbox_to_anchor=(1.02, 0.5), title="operator")
    fig.suptitle(
        f"Operator usage over the run, D={dim}",
        fontsize=11, fontweight="bold",
    )
    fig.tight_layout()
    annotate_source(fig, "dashed line = uniform share 1/5")
    fig.savefig(out / f"fig_operator_usage_d{dim}.png")
    plt.close(fig)


def fig_ablation(eff: pd.DataFrame, dim: int, out: Path) -> None:
    """The headline: effect size of each algorithm against the uniform ablation."""
    use_style()
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    order = list(eff.groupby("algorithm")["delta"].median().sort_values().index)
    data = [eff[eff["algorithm"] == a]["delta"].to_numpy() for a in order]
    ax.axhspan(-0.147, 0.147, color="#EEEEEE", zorder=0, lw=0)
    bp = ax.boxplot(
        data, tick_labels=order, showmeans=False, patch_artist=True, widths=0.6,
        medianprops=dict(color="black", lw=1.4),
        flierprops=dict(marker="o", ms=2.5, mfc="#999999", mec="none"),
    )
    for patch, alg in zip(bp["boxes"], order):
        st = style_for(alg)
        patch.set(facecolor=st["color"], alpha=0.35, edgecolor=st["color"], lw=1.0)
    ax.axhline(0, color="#444444", lw=1.0)
    ax.set_ylabel(r"Cliff's $\delta$ vs uniform")
    ax.set_title(
        f"Effect size against the uniform-random ablation, D={dim}\n"
        "one point per function · negative favours the algorithm · shaded band = negligible",
        fontsize=9.5,
    )
    ax.tick_params(axis="x", rotation=38)
    for lbl in ax.get_xticklabels():
        lbl.set_horizontalalignment("right")
    ax.grid(True, axis="y")
    ax.grid(False, axis="x")
    fig.tight_layout()
    annotate_source(fig, "computed on raw runs within each function")
    fig.savefig(out / f"fig_ablation_d{dim}.png")
    plt.close(fig)


# ------------------------------------------------------------------------ driver


def _verdict_line(alg: str, summ: pd.Series, rank: float, p_vs_uni: float) -> str:
    d = summ["median_delta"]
    beats = "beats" if d < 0 else "loses to"
    mag = cliffs_magnitude(d)
    sig = "significant" if p_vs_uni < 0.05 else "**not significant**"
    return (
        f"| `{alg}` | {rank:.2f} | {d:+.3f} ({mag}) | "
        f"{int(summ['wins_nonneg'])} / {int(summ['losses_nonneg'])} / "
        f"{int(summ['negligible'])} | "
        f"{p_vs_uni:.3g} | {sig} | {beats} uniform |"
    )


def build_report(results_dir: str | Path, out_dir: str | Path) -> None:
    res = Path(results_dir)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runs, extra = load(res)
    dims = sorted(runs["dim"].unique())

    by_dim: dict[int, pd.Series] = {}
    md: list[str] = [
        "# Results — exp01",
        "",
        "Generated by `python -m aos.cli report`. Every number below is regenerated from "
        "`runs.csv`; nothing here is hand-entered.",
        "",
        f"- **Runs:** {len(runs):,} "
        f"({runs['algorithm'].nunique()} algorithms × {runs['fid'].nunique()} functions × "
        f"{runs['run'].nunique()} runs × {len(dims)} dimensions)",
        f"- **Budget:** {int(runs['evaluations'].max()):,} evaluations at D={max(dims)}, "
        "fixed and hard-enforced",
        "- **Statistics:** Friedman ranks → Holm-corrected pairwise Wilcoxon signed-rank → "
        "Cliff's δ on raw runs",
        "",
    ]

    for dim in dims:
        sub = runs[runs["dim"] == dim]
        oracle = add_hindsight_oracle(runs, dim)
        with_oracle = pd.concat([sub, oracle.drop(columns=["oracle_choice"])], ignore_index=True)

        oracle[["fid", "oracle_choice"]].drop_duplicates().sort_values("fid").to_csv(
            out / f"table_oracle_choice_d{dim}.csv", index=False
        )

        matrix = per_problem_matrix(with_oracle, dim)
        matrix.to_csv(out / f"table_median_error_d{dim}.csv")
        stat, p, ranks = friedman_ranks(matrix)
        ranks.to_csv(out / f"table_friedman_ranks_d{dim}.csv", header=["mean_rank"])
        holm = posthoc_holm(matrix)
        holm.to_csv(out / f"table_holm_d{dim}.csv")

        control = control_comparison(matrix, ABLATION)
        control.to_csv(out / f"table_vs_uniform_holm_control_d{dim}.csv")

        sens = baseline_sensitivity(runs, dim)
        sens.to_csv(out / f"table_baseline_sensitivity_d{dim}.csv")

        mis = credit_misalignment(runs, extra, dim)
        if not mis.empty:
            mis.to_csv(out / f"table_credit_misalignment_d{dim}.csv")

        eff = ablation_effect_sizes(runs, dim)
        eff.to_csv(out / f"table_cliffs_vs_uniform_d{dim}.csv", index=False)
        summ = ablation_summary(eff).set_index("algorithm")
        by_dim[dim] = summ["median_delta"]
        summ.to_csv(out / f"table_ablation_summary_d{dim}.csv")

        overhead = (
            sub.groupby("algorithm")["wall_time"].median().sort_values().rename("median_seconds")
        )
        overhead.to_csv(out / f"table_wallclock_d{dim}.csv")

        fig_ecdf(runs, extra, dim, out)
        fig_convergence(runs, extra, dim, out)
        fig_operator_usage(runs, extra, dim, out)
        fig_ablation(eff, dim, out)
        fig_misalignment(mis, ranks, dim, out)

        uni_rank = float(ranks.get(ABLATION, float("nan")))
        orc_rank = float(ranks.get(_ORACLE, float("nan")))
        md += [
            f"## D = {dim}",
            "",
            f"Friedman across {matrix.shape[1]} algorithms over {matrix.shape[0]} functions: "
            f"χ² = {stat:.1f}, p = {p:.3g}.",
            "",
            f"Uniform-random ablation mean rank **{uni_rank:.2f}**; "
            f"hindsight oracle (upper bound, not an algorithm) **{orc_rank:.2f}**.",
            "",
            "> The oracle column is selected post hoc from the fixed-operator runs, so it is "
            "not statistically independent of them. It is included as a *reference ceiling* — "
            "read its rank, not its p-values.",
            "",
            "### Does the learning beat uniform random selection?",
            "",
            "Cliff's δ computed per function on the raw runs; negative favours the algorithm. "
            "Win/loss counts exclude negligible effects (|δ| < 0.147). The p-value is a "
            "Wilcoxon signed-rank test against uniform across the 24 functions, Holm-corrected "
            "over the 12 control comparisons — **not** over all 78 pairs, which would be the "
            "wrong family for this question (Demšar 2006).",
            "",
            "| algorithm | Friedman rank | median δ vs uniform | win/loss/negligible | "
            "Holm p vs uniform | significance | verdict |",
            "|---|---|---|---|---|---|---|",
        ]
        for alg in ADAPTIVE:
            if alg not in summ.index or alg not in ranks.index:
                continue
            pv = float(control.loc[alg, "p_holm"]) if alg in control.index else float("nan")
            md.append(_verdict_line(alg, summ.loc[alg], float(ranks[alg]), pv))
        md += [
            "",
            "### The baseline decides the conclusion",
            "",
            "The identical comparison, re-run against every available baseline. AOS results "
            "are conventionally reported against *one* fixed operator, chosen without "
            "justification. If the verdict moves with that choice, the baseline was doing the "
            "work.",
            "",
            "| baseline | policies better | significantly better |",
            "|---|---|---|",
            *[
                f"| `{b}` | {int(r['n_better'])} / {int(r['n_policies'])} | "
                f"{int(r['n_significantly_better'])} / {int(r['n_policies'])} |"
                for b, r in sens.iterrows()
            ],
            "",
            "### Full ranking",
            "",
            "| algorithm | mean rank |",
            "|---|---|",
            *[f"| `{a}` | {r:.2f} |" for a, r in ranks.items()],
            "",
            "### Wall-clock cost",
            "",
            "The policies spend no function evaluations — they learn from evaluations the "
            "search makes anyway — so the overhead is wall-clock only.",
            "",
            "| algorithm | median seconds/run |",
            "|---|---|",
            *[f"| `{a}` | {v:.2f} |" for a, v in overhead.items()],
            "",
            *(
                [
                    "### Why: the policies optimise a proxy that diverges from the objective",
                    "",
                    "Credit is immediate fitness improvement, so a policy is rewarded for "
                    "operators that improve the parent *often* — not for operators that reach a "
                    "low final error. These two come apart, and the table shows how far.",
                    "",
                    "| algorithm | trials that improved | most-used operator | its share | commitment | Friedman rank |",
                    "|---|---|---|---|---|---|",
                    *[
                        f"| `{a}` | {mis.loc[a, 'trial_success_rate']:.1%} | "
                        f"`{mis.loc[a, 'top_operator']}` | "
                        f"{mis.loc[a, 'top_operator_share']:.1%} | "
                        f"{mis.loc[a, 'commitment']:.3f} | "
                        f"{ranks.get(a, float('nan')):.2f} |"
                        for a in [ABLATION, *ADAPTIVE]
                        if a in mis.index
                    ],
                    "",
                    (
                        "Spearman correlation between how hard a policy commits to one operator "
                        f"and how badly it ranks: **ρ = {commitment_vs_rank(mis, ranks)[0]:.2f}, "
                        f"p = {commitment_vs_rank(mis, ranks)[1]:.3f}**."
                    ),
                    "",
                    f"See `fig_misalignment_d{dim}.png`.",
                    "",
                ]
                if not mis.empty
                else []
            ),
            "### Figures",
            "",
            f"- `fig_ecdf_d{dim}.png` — empirical runtime distribution over "
            f"{len(TARGETS)} targets",
            f"- `fig_convergence_d{dim}.png` — median ± IQR on one function per BBOB group",
            f"- `fig_operator_usage_d{dim}.png` — **is the policy actually adapting?**",
            f"- `fig_ablation_d{dim}.png` — effect size against uniform",
            f"- `fig_misalignment_d{dim}.png` — success rate and commitment against rank",
            "",
        ]

    if len(by_dim) > 1:
        cross = pd.DataFrame(by_dim).reindex([a for a in ADAPTIVE if a in by_dim[dims[0]].index])
        cross.to_csv(out / "table_delta_by_dimension.csv")
        lo, hi = min(dims), max(dims)
        md += [
            "## Does the advantage survive higher dimension?",
            "",
            "Median Cliff's δ against the uniform ablation, per dimension. Negative favours "
            "the policy. AOS gains are widely reported to shrink as dimension rises; this "
            "table is where that shows up or does not.",
            "",
            f"| algorithm | δ at D={lo} | δ at D={hi} | change |",
            "|---|---|---|---|",
        ]
        for alg, row in cross.iterrows():
            a, b = float(row[lo]), float(row[hi])
            arrow = "worse" if b > a else "better"
            md.append(f"| `{alg}` | {a:+.3f} | {b:+.3f} | {b - a:+.3f} ({arrow} at D={hi}) |")
        md.append("")

    (out / "RESULTS.md").write_text("\n".join(md))
    print(f"wrote {out}/RESULTS.md and {len(list(out.glob('*.csv')))} tables, "
          f"{len(list(out.glob('*.png')))} figures")
