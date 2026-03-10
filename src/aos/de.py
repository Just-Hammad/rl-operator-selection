"""Differential evolution with a pluggable operator-selection policy.

Two design choices worth stating, because both affect results and both are usually
left unreported:

**Synchronous generations.** Trial vectors for a generation are all built from the
frozen current population and replacement is applied at the end of the generation.
This is textbook DE. Credit, however, is delivered to the policy *immediately* as
each trial is evaluated -- the policy should not wait a whole generation for feedback
it already has.

**The policy costs zero function evaluations.** Every policy here learns from
evaluations the search was going to make anyway, so the AOS overhead is wall-clock
only, never budget. Wall-clock is measured and reported so the cost is still visible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from .credit import raw_credit
from .operators import (
    MIN_POPULATION,
    N_OPERATORS,
    OPERATORS,
    MutationContext,
    binomial_crossover,
    repair_midpoint,
)
from .policies import Policy
from .problems import BudgetExhausted, TrackedProblem


@dataclass(frozen=True)
class DEConfig:
    NP: int = 50
    F: float = 0.5
    CR: float = 0.9
    p_best: float = 0.11
    use_archive: bool = True
    credit_scheme: str = "improvement"
    n_phase_bins: int = 20  # resolution of the operator-usage-over-time record

    def __post_init__(self) -> None:
        if self.NP < MIN_POPULATION:
            raise ValueError(f"NP must be >= {MIN_POPULATION} for DE/rand/2")


@dataclass
class RunResult:
    best_error: float
    evaluations: int
    wall_time: float
    generations: int
    trace_evals: list[int] = field(default_factory=list)
    trace_error: list[float] = field(default_factory=list)
    #: (n_phase_bins, N_OPERATORS) -- how often each operator was *selected*, by
    #: normalised budget. This is the figure that shows whether adaptation happened.
    selection_hist: np.ndarray | None = None
    #: (n_phase_bins, N_OPERATORS) -- how often each selection *improved* the parent.
    success_hist: np.ndarray | None = None


def run_de(
    problem: TrackedProblem,
    policy: Policy,
    cfg: DEConfig,
    rng: np.random.Generator,
) -> RunResult:
    """Run DE under ``policy`` until the problem's budget is exhausted."""
    t0 = time.perf_counter()
    d = problem.dim
    lb, ub = problem.lb, problem.ub

    sel_hist = np.zeros((cfg.n_phase_bins, N_OPERATORS), dtype=np.int64)
    suc_hist = np.zeros((cfg.n_phase_bins, N_OPERATORS), dtype=np.int64)
    budget = problem.budget

    def phase_bin() -> int:
        frac = problem.evaluations / budget
        return min(cfg.n_phase_bins - 1, int(frac * cfg.n_phase_bins))

    pop = rng.uniform(lb, ub, size=(cfg.NP, d))
    fit = np.full(cfg.NP, np.inf)
    generations = 0
    archive: list[np.ndarray] = []

    try:
        for i in range(cfg.NP):
            fit[i] = problem(pop[i])

        while True:
            generations += 1
            arch = np.asarray(archive) if (cfg.use_archive and archive) else None
            # Frozen view of the generation -- trials are built from these, not from
            # partially-updated state.
            gen_pop, gen_fit = pop.copy(), fit.copy()
            order = np.argsort(gen_fit, kind="stable")
            pending: list[tuple[int, np.ndarray, float]] = []

            for i in range(cfg.NP):
                k = policy.select(rng)
                ctx = MutationContext(
                    pop=gen_pop,
                    fit=gen_fit,
                    i=i,
                    F=cfg.F,
                    rng=rng,
                    archive=arch,
                    p=cfg.p_best,
                    _order=order,
                )
                v = OPERATORS[k](ctx)
                u = binomial_crossover(gen_pop[i], v, cfg.CR, rng)
                u = repair_midpoint(u, gen_pop[i], lb, ub)

                b = phase_bin()
                f_u = problem(u)  # raises BudgetExhausted at the limit

                credit = raw_credit(gen_fit[i], f_u, cfg.credit_scheme)
                policy.update(k, credit)

                sel_hist[b, k] += 1
                if f_u <= gen_fit[i]:
                    suc_hist[b, k] += 1
                    pending.append((i, u, f_u))

            for i, u, f_u in pending:
                if cfg.use_archive:
                    archive.append(pop[i].copy())
                pop[i], fit[i] = u, f_u
            if cfg.use_archive and len(archive) > cfg.NP:
                keep = rng.choice(len(archive), size=cfg.NP, replace=False)
                archive = [archive[j] for j in keep]

    except BudgetExhausted:
        # The budget is the budget. A partial generation is a valid stopping point --
        # best-so-far is tracked per evaluation, so nothing is lost.
        pass

    problem.finalise()
    return RunResult(
        best_error=float(problem.best_error),
        evaluations=problem.evaluations,
        wall_time=time.perf_counter() - t0,
        generations=generations,
        trace_evals=list(problem.trace_evals),
        trace_error=list(problem.trace_error),
        selection_hist=sel_hist,
        success_hist=suc_hist,
    )
